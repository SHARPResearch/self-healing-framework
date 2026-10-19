import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/mlBackend";
import { subscribeToMessages, useLiveConnection } from "@/hooks/useLiveConnection";
import type { LiveMessage } from "@/features/lifecycle/types";
import { matches, parseFilter } from "../lib/filter";
import type { LogHistogram, LogLine, LogServiceSummary } from "../types";

const PAGE = 1000;
const OLDER_PAGE = 500;
const MAX_LINES = 5000;
const FLUSH_MS = 200;
const HISTOGRAM_MS = 4000;
const SERVICES_MS = 15000;

const byTime = (a: LogLine, b: LogLine) => (a.time < b.time ? -1 : a.time > b.time ? 1 : a.id < b.id ? -1 : 1);

function merge(current: LogLine[], incoming: LogLine[]): LogLine[] {
  const seen = new Set(current.map((l) => l.id));
  const fresh = incoming.filter((l) => !seen.has(l.id));
  if (!fresh.length) return current;
  const all = [...current, ...fresh].sort(byTime);
  return all.length > MAX_LINES ? all.slice(all.length - MAX_LINES) : all;
}

interface Options {
  query: string;
  rangeSeconds: number;
  live: boolean;
}

/**
 * The Logs page's data: the newest PAGE lines matching `query` within the range, older pages on
 * demand, the level histogram, the service list, and (when `live`) lines pushed over /ws/events
 * that match the same filter. Server and client filters share one grammar, see lib/filter.ts.
 */
export function useLogStream({ query, rangeSeconds, live }: Options) {
  useLiveConnection();
  const [lines, setLines] = useState<LogLine[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [histogram, setHistogram] = useState<LogHistogram | null>(null);
  const [services, setServices] = useState<LogServiceSummary[]>([]);
  const [debounced, setDebounced] = useState(query);
  const buffer = useRef<LogLine[]>([]);
  const request = useRef(0);

  useEffect(() => {
    const t = window.setTimeout(() => setDebounced(query), 250);
    return () => window.clearTimeout(t);
  }, [query]);

  const since = useCallback(() => new Date(Date.now() - rangeSeconds * 1000).toISOString(), [rangeSeconds]);

  const load = useCallback(async () => {
    const id = ++request.current;
    setLoading(true);
    try {
      const page = await api.logs({ q: debounced, since: since(), limit: PAGE });
      if (id !== request.current) return;
      buffer.current = [];
      setLines(page.lines);
      setHasMore(page.hasMore);
      setError(null);
    } catch (e) {
      if (id === request.current) setError(e instanceof Error ? e.message : String(e));
    } finally {
      if (id === request.current) setLoading(false);
    }
  }, [debounced, since]);

  useEffect(() => {
    load();
  }, [load]);

  const loadOlder = useCallback(async () => {
    if (loadingOlder || !hasMore || !lines.length) return;
    setLoadingOlder(true);
    try {
      const page = await api.logs({ q: debounced, since: since(), before: lines[0].time, limit: OLDER_PAGE });
      setLines((cur) => merge(cur, page.lines));
      setHasMore(page.hasMore);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoadingOlder(false);
    }
  }, [loadingOlder, hasMore, lines, debounced, since]);

  // histogram: refetch on filter or range change, and keep it fresh while tailing
  useEffect(() => {
    let cancelled = false;
    const run = () =>
      api
        .logsHistogram({ q: debounced, since: since(), until: new Date().toISOString() })
        .then((h) => !cancelled && setHistogram(h))
        .catch(() => undefined);
    run();
    if (!live) return () => void (cancelled = true);
    const t = window.setInterval(run, HISTOGRAM_MS);
    return () => {
      cancelled = true;
      window.clearInterval(t);
    };
  }, [debounced, since, live]);

  useEffect(() => {
    let cancelled = false;
    const run = () =>
      api
        .logsServices()
        .then((s) => !cancelled && setServices(s))
        .catch(() => undefined);
    run();
    const t = window.setInterval(run, SERVICES_MS);
    return () => {
      cancelled = true;
      window.clearInterval(t);
    };
  }, []);

  // a demo reset wipes the lifecycle lines: start over from what the server now has
  useEffect(() => subscribeToMessages("demo_reset", () => void load()), [load]);

  // live tail
  useEffect(() => {
    if (!live) return;
    const filter = parseFilter(debounced);
    const off = subscribeToMessages("log", (msg: LiveMessage) => {
      const line = msg.data as unknown as LogLine;
      if (matches(line, filter)) buffer.current.push(line);
    });
    const t = window.setInterval(() => {
      if (!buffer.current.length) return;
      const batch = buffer.current;
      buffer.current = [];
      setLines((cur) => merge(cur, batch));
    }, FLUSH_MS);
    return () => {
      off();
      window.clearInterval(t);
    };
  }, [live, debounced]);

  return { lines, hasMore, loading, loadingOlder, error, histogram, services, loadOlder, reload: load };
}
