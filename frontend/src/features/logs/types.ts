export type LogLevel = "debug" | "info" | "warn" | "error";
export type LogSource = "container" | "app" | "lifecycle";

/** One line, as served by GET /api/logs and streamed as a `log` WebSocket message. */
export interface LogLine {
  id: string;
  time: string;
  /** Display name: a container ("Redis"), "ml-backend", or a monitored service id. */
  service: string;
  serviceId: string | null;
  source: LogSource;
  level: LogLevel;
  message: string;
  attrs: Record<string, unknown>;
}

export interface LogPage {
  lines: LogLine[];
  hasMore: boolean;
}

export interface LogHistogramBucket {
  time: string;
  info: number;
  warn: number;
  error: number;
}

export interface LogHistogram {
  bucketSeconds: number;
  buckets: LogHistogramBucket[];
}

export interface LogServiceSummary {
  service: string;
  source: LogSource;
  count: number;
}

export interface LogRange {
  id: string;
  label: string;
  seconds: number;
}

export const LOG_RANGES: LogRange[] = [
  { id: "5m", label: "Last 5 minutes", seconds: 5 * 60 },
  { id: "30m", label: "Last 30 minutes", seconds: 30 * 60 },
  { id: "1h", label: "Last hour", seconds: 3600 },
  { id: "6h", label: "Last 6 hours", seconds: 6 * 3600 },
  { id: "1d", label: "Last day", seconds: 86400 },
  { id: "7d", label: "Last week", seconds: 7 * 86400 },
];
