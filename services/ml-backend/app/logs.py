"""
logs.py — the platform's log stream for the Logs page (Railway-style: time, service, message).

Three sources feed one LogHub:
  container   `docker logs -f` of the demo stack's containers (TimescaleDB, Redis), so the page shows
              what the databases themselves print (checkpoints, RDB saves, connections)
  app         this backend's own Python logging (startup, store and bus warnings, errors)
  lifecycle   one line per meaningful event of each monitored service: alarms raised and cleared,
              quarantines, decisions, operator queries, model transitions, demo injections

Lines are buffered and written to TimescaleDB (`service_logs`) in batches by the replay loop, and
published on the bus as `log` messages for live tail. Python logging can fire on any thread (the
asynchronous lifecycle decisions run on worker threads), so the hub only appends to a thread-safe
deque there; everything async happens in `drain()` on the event loop.
"""

import hashlib
import logging
import re
import shutil
import subprocess
import threading
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

LEVELS = ("debug", "info", "warn", "error")
_TS = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(\.\d+)?Z\s?(.*)$")


def log_id(time: datetime, service: str, message: str) -> str:
    """Stable id, so a line seen live and again in a query is recognised as the same line."""
    return hashlib.sha1(f"{time.isoformat()}|{service}|{message}".encode()).hexdigest()[:16]


def make_line(service: str, message: str, level: str = "info", source: str = "lifecycle",
              service_id: Optional[str] = None, attrs: Optional[dict] = None,
              time: Optional[datetime] = None) -> dict:
    time = time or datetime.now(timezone.utc)
    return {"id": log_id(time, service, message), "time": time, "service": service,
            "service_id": service_id, "source": source, "level": level if level in LEVELS else "info",
            "message": message, "attrs": attrs or {}}


def public(line: dict) -> dict:
    """JSON shape served by the API and the WebSocket."""
    return {"id": line["id"], "time": line["time"].isoformat(), "service": line["service"],
            "serviceId": line.get("service_id"), "source": line["source"], "level": line["level"],
            "message": line["message"], "attrs": line.get("attrs") or {}}


def parse_docker_line(raw: str) -> tuple[Optional[datetime], str]:
    """`docker logs --timestamps` prefixes RFC 3339 nanosecond timestamps; keep microseconds."""
    m = _TS.match(raw)
    if not m:
        return None, raw
    frac = (m.group(2) or ".0")[1:7].ljust(6, "0")
    t = datetime.strptime(f"{m.group(1)}.{frac}", "%Y-%m-%dT%H:%M:%S.%f").replace(tzinfo=timezone.utc)
    return t, m.group(3)


def container_level(message: str) -> str:
    """Postgres tags severity in the line; Redis marks warnings with '#'."""
    if re.search(r"\b(ERROR|FATAL|PANIC):", message):
        return "error"
    if re.search(r"\bWARNING:", message) or re.search(r"^\d+:[A-Z] .* # ", message):
        return "warn"
    return "info"


class LogCapture(logging.Handler):
    """Python logging → hub. Thread safe: only appends to the hub's deque."""

    def __init__(self, hub: "LogHub"):
        super().__init__(level=logging.INFO)
        self.hub = hub

    def emit(self, record: logging.LogRecord) -> None:
        if record.name.startswith("uvicorn.access") and not self.hub.http_access:
            return
        level = ("error" if record.levelno >= logging.ERROR else
                 "warn" if record.levelno >= logging.WARNING else "info")
        try:
            message = f"{record.name}: {record.getMessage()}"
        except Exception:  # noqa: BLE001 - a bad format string must not break logging
            message = f"{record.name}: {record.msg}"
        self.hub.add(make_line("ml-backend", message, level, source="app",
                               time=datetime.fromtimestamp(record.created, timezone.utc)))


class LogHub:
    def __init__(self, http_access: bool = False):
        self.http_access = http_access
        self._incoming: deque = deque(maxlen=20000)
        self._threads: list[threading.Thread] = []
        self._procs: list[subprocess.Popen] = []
        self._stopping = threading.Event()
        self.handler = LogCapture(self)

    def add(self, line: dict) -> None:
        self._incoming.append(line)

    def take(self) -> list[dict]:
        out = []
        while self._incoming:
            out.append(self._incoming.popleft())
        return out

    def start(self) -> None:
        """(Re)arm after a stop, e.g. when a test client restarts the app lifespan."""
        self._stopping.clear()
        self.install()

    def install(self) -> None:
        for name in ("app", "uvicorn.error", "uvicorn.access"):
            lg = logging.getLogger(name)
            if self.handler not in lg.handlers:
                lg.addHandler(self.handler)

    def uninstall(self) -> None:
        for name in ("app", "uvicorn.error", "uvicorn.access"):
            logging.getLogger(name).removeHandler(self.handler)

    # -- containers --------------------------------------------------------------------------------
    def follow_containers(self, containers: dict[str, str], since: dict[str, datetime]) -> None:
        """
        One daemon thread per container running `docker logs -f`. Threads rather than asyncio
        subprocesses: on Windows those need the Proactor loop, which uvicorn --reload replaces.
        `since` holds each service's newest stored line, so a restart resumes without duplicates.
        """
        if not containers:
            return
        if shutil.which("docker") is None:
            logger.warning("logs: docker CLI not found, container logs are off")
            return
        for service, container in containers.items():
            t = threading.Thread(target=self._follow, args=(service, container, since.get(service)),
                                 name=f"logs-{service}", daemon=True)
            t.start()
            self._threads.append(t)

    def _follow(self, service: str, container: str, resume: Optional[datetime]) -> None:
        backoff = 2.0
        start = resume or datetime.now(timezone.utc) - timedelta(hours=1)
        while not self._stopping.is_set():
            args = ["docker", "logs", "-f", "--timestamps", "--since",
                    start.strftime("%Y-%m-%dT%H:%M:%S.%fZ"), container]
            try:
                proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                self._procs.append(proc)
                for raw in proc.stdout:
                    if self._stopping.is_set():
                        break
                    text = raw.decode("utf-8", errors="replace").rstrip()
                    t, message = parse_docker_line(text)
                    if t is None:
                        if text:               # docker's own messages (no such container ...)
                            logger.warning("logs: %s: %s", container, text)
                        continue
                    if t <= start:             # --since is inclusive: skip what is already stored
                        continue
                    start = t
                    if not message.strip():    # docker passes blank lines through
                        continue
                    self.add(make_line(service, message, container_level(message),
                                       source="container", attrs={"container": container}, time=t))
                proc.wait()
                backoff = 2.0 if proc.returncode == 0 else min(backoff * 2, 60.0)
            except Exception as exc:  # noqa: BLE001
                logger.warning("logs: following %s failed (%s)", container, exc)
                backoff = min(backoff * 2, 60.0)
            self._stopping.wait(backoff)

    def stop(self) -> None:
        self._stopping.set()
        for proc in self._procs:
            if proc.poll() is None:
                proc.kill()
        self._procs.clear()
        self.uninstall()


class AlarmLog:
    """
    Turns a service's per-event alarm flag into two log lines per episode instead of one per event.
    An episode starts at its first alarming event, but is only logged ("raised") once it has
    MIN_ALARMS alarming events: a calibrated detector alarms on about 1% of normal events, and a
    line for every such blip would bury the real ones. It ends ("cleared") after QUIET events
    without an alarm, and only logged episodes get a "cleared" line.
    """

    QUIET = 30
    MIN_ALARMS = 8

    def __init__(self):
        self.open = False
        self.raised = False
        self.since_alarm = self.QUIET
        self.started_step = 0
        self.peak = 0.0
        self.alarms = 0

    def update(self, step: int, alarm: bool, score: float) -> Optional[tuple[str, dict]]:
        if alarm:
            self.since_alarm = 0
            if not self.open:
                self.open, self.raised, self.started_step, self.peak, self.alarms = True, False, step, score, 1
            else:
                self.peak = max(self.peak, score)
                self.alarms += 1
            if not self.raised and self.alarms >= self.MIN_ALARMS:
                self.raised = True
                return "raised", {"step": step, "since_step": self.started_step, "score": round(self.peak, 4)}
            return None
        self.since_alarm += 1
        if self.open and self.since_alarm >= self.QUIET:
            was_logged, self.open, self.raised = self.raised, False, False
            if was_logged:
                return "cleared", {"from_step": self.started_step, "to_step": step - self.QUIET,
                                   "peak": round(self.peak, 4), "alarming_events": self.alarms}
        return None
