"""
Email notifier.

Sends a plain + HTML email when (a) a new anomaly/incident opens, and
(b) a decision is made for an anomaly. Every attempt is logged to the
`notifications` table so "what was the user told?" has a single source
of truth.

Transport: aiosmtplib over STARTTLS (default) or SSL. Credentials come
from the environment (SMTP_*). If SMTP_PASSWORD is empty the notifier
runs in DRY-RUN mode: it logs the email and records a SKIPPED row rather
than failing — so the pipeline never breaks just because mail isn't set up.

The master switch and per-event toggles are runtime-editable; they are
read from the `settings` singleton at send time so a change takes effect
immediately.
"""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from html import escape
from pathlib import Path

from app.config import settings
from app.persistence.postgres import postgres_store

log = logging.getLogger(__name__)

_SYSTEM_NAME = "SHARP — Automated Recovery Framework"
_SYSTEM_SHORT = "SHARP"
_LOGO_CID = "sharp-favicon"
_LOGO_PATH = Path(__file__).with_name("sharp-favicon.png")

# Brand palette (aligned with the frontend)
_BG = "#0f172a"
_SURFACE = "#f1f5f9"
_BORDER = "#e2e8f0"
_TEXT = "#0f172a"
_MUTED = "#64748b"
_OK = "#22c55e"
_WARN = "#f59e0b"
_ALERT = "#f43f5e"


def _notif_id() -> str:
    now = datetime.now(timezone.utc)
    return f"NTF-{now.strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}"


def _fmt(value, digits: int = 2) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return str(value)


def _fmt_ts(value) -> str:
    if value is None:
        return "—"
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return str(value)


def _severity_color(sev: str) -> str:
    s = (sev or "").upper()
    if s in ("CRITICAL", "HIGH", "SEV1", "SEV2"):
        return _ALERT
    if s in ("MEDIUM", "WARN", "WARNING", "SEV3"):
        return _WARN
    return _OK


def _outcome_color(outcome: str) -> str:
    o = (outcome or "").upper()
    if o in ("ALLOW", "APPROVED", "OK", "PASS"):
        return _OK
    if "WARN" in o or "REVIEW" in o or "UNVALIDATED" in o:
        return _WARN
    return _ALERT


# ─────────────────────────────────────────────────────────────────────
# Templates
# ─────────────────────────────────────────────────────────────────────
def _anomaly_subject(anomaly: dict) -> str:
    svc = anomaly.get("service_name") or anomaly.get("service_id") or "service"
    sev = (anomaly.get("severity") or "unknown").upper()
    return f"[SHARP] Anomaly detected: {svc} ({sev})"


def _anomaly_body(anomaly: dict) -> tuple[str, str]:
    svc = anomaly.get("service_name") or anomaly.get("service_id") or "—"
    sid = anomaly.get("service_id") or "—"
    sev = (anomaly.get("severity") or "unknown").upper()
    metric = anomaly.get("metric") or "—"
    actual = _fmt(anomaly.get("actual_value"))
    expected = _fmt(anomaly.get("expected_value"))
    score = _fmt(anomaly.get("anomaly_score"), 3)
    detected = _fmt_ts(anomaly.get("detected_at") or datetime.now(timezone.utc))
    accent = _severity_color(sev)

    text = (
        f"{_SYSTEM_NAME}\n"
        f"ANOMALY DETECTED\n"
        f"{'-' * 46}\n\n"
        f"A new anomaly has been identified and is being evaluated by the decision engine.\n\n"
        f"Service        : {svc} ({sid})\n"
        f"Severity       : {sev}\n"
        f"Metric         : {metric}\n"
        f"Observed value : {actual}\n"
        f"Expected value : {expected}\n"
        f"Anomaly score  : {score}\n"
        f"Anomaly ID     : {anomaly.get('id', '—')}\n"
        f"Detected at    : {detected}\n\n"
        f"This is an automated notification from {_SYSTEM_NAME}.\n"
        f"Please do not reply to this email."
    )

    html = _email_shell(
        title="Anomaly detected",
        subtitle_html=(
            f"{escape(sev)} severity · <strong>{escape(str(svc))}</strong>"
        ),
        summary=(
            "A new anomaly has been identified and is being evaluated by the "
            "decision engine."
        ),
        accent=accent,
        preheader=f"{sev} anomaly on {svc}: {metric} = {actual} (expected {expected}).",
        rows=[
            ("Service", f"{svc} ({sid})"),
            ("Severity", sev),
            ("Metric", metric),
            ("Observed value", actual),
            ("Expected value", expected),
            ("Anomaly score", score),
            ("Anomaly ID", str(anomaly.get("id", "—"))),
            ("Detected at", detected),
        ],
        footer_note="Automated detection alert from the SHARP pipeline.",
    )
    return text, html


def _decision_subject(decision: dict, anomaly: dict | None) -> str:
    svc = (anomaly or {}).get("service_name") or decision.get("service_id") or "service"
    action = decision.get("action") or "NOOP"
    return f"[SHARP] Recovery decision: {action} on {svc}"


def _decision_body(decision: dict, anomaly: dict | None) -> tuple[str, str]:
    svc = (anomaly or {}).get("service_name") or decision.get("service_id") or "—"
    action = decision.get("action") or "NOOP"
    conf = decision.get("confidence") or {}
    sev = (decision.get("severity") or {})
    policy = (decision.get("policy") or {})
    outcome = policy.get("outcome") or "UNVALIDATED"
    reason = policy.get("reason") or "—"
    params = decision.get("action_params") or {}

    final_conf = _fmt(conf.get("final"), 3)
    eff_sev = _fmt(sev.get("effective_severity"), 3)
    blast = _fmt(decision.get("blast_factor"), 2)
    rule_id = decision.get("rule_id") or "—"
    rule_ver = decision.get("rule_version") or "—"
    accent = _outcome_color(outcome)

    text = (
        f"{_SYSTEM_NAME}\n"
        f"RECOVERY DECISION\n"
        f"{'-' * 46}\n\n"
        f"The decision engine has completed its policy evaluation.\n\n"
        f"Service           : {svc} ({decision.get('service_id', '—')})\n"
        f"Action            : {action}\n"
        f"Action parameters : {params}\n"
        f"Policy outcome    : {outcome} ({reason})\n"
        f"Final confidence  : {final_conf}\n"
        f"Effective severity: {eff_sev}\n"
        f"Blast factor      : {blast}\n"
        f"Rule              : {rule_id} v{rule_ver}\n"
        f"Anomaly ID        : {decision.get('anomaly_id', '—')}\n"
        f"Decision ID       : {decision.get('decision_id', '—')}\n\n"
        f"This is an automated notification from {_SYSTEM_NAME}.\n"
        f"Please do not reply to this email."
    )

    html = _email_shell(
        title=f"Recovery decision: {escape(str(action))}",
        subtitle_html=(
            f"Policy evaluation completed for <strong>{escape(str(svc))}</strong>"
        ),
        summary="The decision engine has completed its policy evaluation.",
        accent=accent,
        preheader=f"Decision: {action} on {svc} (outcome: {outcome}).",
        rows=[
            ("Service", f"{svc} ({decision.get('service_id', '—')})"),
            ("Action", action),
            ("Action parameters", str(params)),
            ("Policy outcome", f"{outcome} — {reason}"),
            ("Final confidence", final_conf),
            ("Effective severity", eff_sev),
            ("Blast factor", blast),
            ("Rule", f"{rule_id} v{rule_ver}"),
            ("Anomaly ID", str(decision.get("anomaly_id", "—"))),
            ("Decision ID", str(decision.get("decision_id", "—"))),
        ],
        footer_note="Automated decision notification from the SHARP decision engine.",
    )
    return text, html


def _email_shell(
    *,
    title: str,
    subtitle_html: str,
    summary: str,
    accent: str,
    preheader: str,
    rows: list[tuple[str, str]],
    footer_note: str,
) -> str:
    details = "".join(_row(label, value) for label, value in rows)
    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="x-apple-disable-message-reformatting">
<title>{escape(title)}</title>
</head>
<body style="margin:0;padding:0;background:{_SURFACE};-webkit-text-size-adjust:100%">
  <!-- preheader: hidden preview text -->
  <div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent">
    {escape(preheader)}
  </div>

  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
         style="background:{_SURFACE};padding:24px 12px">
    <tr><td align="center">
      <table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0"
             style="max-width:600px;width:100%;background:#ffffff;border:1px solid {_BORDER};
                    border-radius:12px;overflow:hidden;
                    font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;
                    color:{_TEXT}">

        <!-- Header -->
        <tr><td style="background:{_BG};padding:20px 28px">
          <table role="presentation" cellpadding="0" cellspacing="0" border="0">
            <tr>
              <td style="vertical-align:middle;padding-right:12px">
                <img src="cid:{_LOGO_CID}" width="40" height="40" alt="{_SYSTEM_SHORT}"
                     style="display:block;border:0;border-radius:8px">
              </td>
              <td style="vertical-align:middle;color:#ffffff">
                <div style="font-size:16px;font-weight:700;letter-spacing:.4px">
                  {escape(_SYSTEM_SHORT)}
                </div>
                <div style="font-size:11px;color:#94a3b8;letter-spacing:.4px;text-transform:uppercase">
                  Automated Recovery Framework
                </div>
              </td>
            </tr>
          </table>
        </td></tr>

        <!-- Body -->
        <tr><td style="padding:28px">
          <h1 style="margin:0 0 6px;font-size:22px;line-height:1.3;color:{_TEXT}">{escape(title)}</h1>
          <p style="margin:0 0 20px;font-size:14px;line-height:1.5;color:{_MUTED}">{subtitle_html}</p>
          <div style="margin:0 0 20px;padding:12px 14px;background:{_SURFACE};
                      border-left:4px solid {accent};border-radius:4px;
                      font-size:14px;line-height:1.5;color:#334155">
            {escape(summary)}
          </div>
          <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%"
                 style="border-collapse:collapse">
            {details}
          </table>
          <p style="margin:24px 0 0;font-size:12px;line-height:1.6;color:{_MUTED}">
            This is an automated operational alert. Please do not reply to this email.
          </p>
        </td></tr>

        <!-- Footer -->
        <tr><td style="padding:16px 28px;border-top:1px solid {_BORDER};
                       font-size:11px;line-height:1.6;color:{_MUTED}">
          {escape(_SYSTEM_NAME)} · {escape(footer_note)}
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def _row(label: str, value: str) -> str:
    return (
        f'<tr style="border-bottom:1px solid {_BORDER}">'
        f'<td style="padding:10px 12px 10px 0;color:{_MUTED};font-size:13px;'
        f'vertical-align:top;width:38%">{escape(str(label))}</td>'
        f'<td style="padding:10px 0;color:{_TEXT};font-size:13px;line-height:1.5;'
        f'vertical-align:top;word-break:break-word;'
        f'font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace">'
        f'{escape(str(value))}</td>'
        f'</tr>'
    )


# ─────────────────────────────────────────────────────────────────────
# Send
# ─────────────────────────────────────────────────────────────────────
def _load_logo() -> bytes | None:
    """Read the inline logo lazily; return None if unavailable (never raise)."""
    try:
        return _LOGO_PATH.read_bytes()
    except OSError as e:
        log.warning("Inline logo unavailable (%s): %s — sending without logo", _LOGO_PATH, e)
        return None


async def _send(recipient: str, subject: str, text: str, html: str) -> tuple[bool, str | None]:
    """
    Send one email. Returns (sent, error). DRY-RUN when SMTP_PASSWORD is
    empty → logs and returns (False, "smtp_not_configured").
    """
    if not settings.SMTP_PASSWORD or not settings.SMTP_USER:
        log.warning(
            "Email DRY-RUN (SMTP not configured) → to=%s subject=%r",
            recipient, subject,
        )
        return False, "smtp_not_configured"

    try:
        import aiosmtplib
    except ImportError:
        log.error("aiosmtplib is not installed — cannot send email")
        return False, "aiosmtplib_missing"

    msg = EmailMessage()
    msg["From"] = formataddr((_SYSTEM_SHORT, settings.SMTP_FROM or settings.SMTP_USER))
    msg["To"] = recipient
    msg["Subject"] = subject
    msg["Message-ID"] = make_msgid(domain="sharp.local")
    msg["Auto-Submitted"] = "auto-generated"
    msg["X-Auto-Response-Suppress"] = "All"
    msg.set_content(text)

    # Build the HTML part, keep a direct handle on it, attach the inline logo
    # *before* adding it to the message so we never rely on payload[-1].
    html_part = EmailMessage()
    html_part.set_content(html, subtype="html")
    logo = _load_logo()
    if logo is not None:
        html_part.add_related(
            logo,
            maintype="image",
            subtype="png",
            cid=_LOGO_CID,          # no angle brackets — add_related adds them
            filename="sharp-favicon.png",
            disposition="inline",
        )
    msg.add_alternative(html_part)

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            start_tls=settings.SMTP_USE_TLS,
            timeout=20,
        )
        return True, None
    except Exception as e:
        log.exception("Email send failed (to=%s): %s", recipient, e)
        return False, str(e)


async def _deliver(
    kind: str,
    subject: str,
    text: str,
    html: str,
    *,
    anomaly_id: str | None = None,
    decision_id: str | None = None,
    service_id: str | None = None,
) -> None:
    """Send + always log a notification row."""
    recipient = getattr(settings, "NOTIFY_RECIPIENT", "") or settings.SMTP_FROM
    nid = _notif_id()
    sent, error = await _send(recipient, subject, text, html)

    await postgres_store.save_notification({
        "id": nid,
        "kind": kind,
        "anomaly_id": anomaly_id,
        "decision_id": decision_id,
        "service_id": service_id,
        "recipient": recipient,
        "sender": settings.SMTP_FROM or settings.SMTP_USER,
        "subject": subject,
        "body": text,
        "status": "SENT" if sent else ("FAILED" if error and error != "smtp_not_configured" else "SKIPPED"),
        "error": error,
        "sent_at": datetime.now(timezone.utc) if sent else None,
    })


def _enabled(kind: str) -> bool:
    if not getattr(settings, "NOTIFY_ENABLED", True):
        return False
    if kind == "ANOMALY_DETECTED":
        return bool(getattr(settings, "NOTIFY_ON_ANOMALY", True))
    if kind == "DECISION_MADE":
        return bool(getattr(settings, "NOTIFY_ON_DECISION", True))
    return True


async def notify_anomaly_detected(anomaly: dict) -> None:
    """Email the operator that a new anomaly/incident opened."""
    if not _enabled("ANOMALY_DETECTED"):
        return
    try:
        text, html = _anomaly_body(anomaly)
        await _deliver(
            "ANOMALY_DETECTED",
            _anomaly_subject(anomaly),
            text,
            html,
            anomaly_id=anomaly.get("id"),
            service_id=anomaly.get("service_id"),
        )
    except Exception:
        log.exception("notify_anomaly_detected failed")


async def notify_decision_made(decision: dict, anomaly: dict | None = None) -> None:
    """Email the operator the decision (action) chosen for an anomaly."""
    if not _enabled("DECISION_MADE"):
        return
    try:
        text, html = _decision_body(decision, anomaly)
        await _deliver(
            "DECISION_MADE",
            _decision_subject(decision, anomaly),
            text,
            html,
            anomaly_id=decision.get("anomaly_id"),
            decision_id=decision.get("decision_id"),
            service_id=decision.get("service_id"),
        )
    except Exception:
        log.exception("notify_decision_made failed")