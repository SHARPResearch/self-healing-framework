import type { LogLine } from "../types";

/**
 * The filter box grammar, kept identical to services/ml-backend `parse_log_filter` so a line that
 * arrives over the WebSocket is kept or dropped exactly as the server would have returned it:
 * free text (case-insensitive substring) plus `service:`, `level:` and `source:` terms.
 */
export interface LogFilter {
  text: string[];
  service: string[];
  level: string[];
  source: string[];
}

const KEYS = ["service", "level", "source"] as const;

export function parseFilter(query: string): LogFilter {
  const out: LogFilter = { text: [], service: [], level: [], source: [] };
  for (const token of query.split(/\s+/).filter(Boolean)) {
    const i = token.indexOf(":");
    const key = i > 0 ? token.slice(0, i).toLowerCase().replace(/^@/, "") : "";
    const value = i > 0 ? token.slice(i + 1) : "";
    if (value && (KEYS as readonly string[]).includes(key)) {
      out[key as (typeof KEYS)[number]].push(value.toLowerCase());
    } else {
      out.text.push(token);
    }
  }
  return out;
}

export function matches(line: LogLine, filter: LogFilter): boolean {
  if (filter.service.length) {
    const names = [line.service.toLowerCase(), (line.serviceId ?? "").toLowerCase()];
    if (!filter.service.some((s) => names.includes(s))) return false;
  }
  if (filter.level.length && !filter.level.includes(line.level)) return false;
  if (filter.source.length && !filter.source.includes(line.source)) return false;
  const hay = `${line.message} ${line.service}`.toLowerCase();
  return filter.text.every((t) => hay.includes(t.toLowerCase()));
}

/** Add or remove a `key:value` term, keeping the rest of the query as typed. */
export function toggleTerm(query: string, key: "service" | "level" | "source", value: string): string {
  const term = `${key}:${value}`;
  const tokens = query.split(/\s+/).filter(Boolean);
  const has = tokens.some((t) => t.toLowerCase() === term.toLowerCase());
  const next = has ? tokens.filter((t) => t.toLowerCase() !== term.toLowerCase()) : [...tokens, term];
  return next.join(" ");
}

export function hasTerm(query: string, key: string, value: string): boolean {
  const term = `${key}:${value}`.toLowerCase();
  return query.split(/\s+/).some((t) => t.toLowerCase() === term);
}
