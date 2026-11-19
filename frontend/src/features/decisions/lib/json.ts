// frontend\src\features\decisions\lib\json.ts
//
// asyncpg returns JSONB columns as text unless a type codec is installed, and
// the decision engine does not install one — so `escalations.notifications`,
// `escalations.response`, `shadow_records.simulated_outcome` and
// `execution_log.detail` all arrive as strings over HTTP. Everything that
// reads a JSONB column goes through here so a future codec change can't break
// the UI in the other direction either.

/** Parse a possibly-encoded JSON column, falling back instead of throwing. */
export function asJson<T>(value: unknown, fallback: T): T {
  if (value === null || value === undefined) return fallback;
  if (typeof value === "string") {
    try {
      return JSON.parse(value) as T;
    } catch {
      return fallback;
    }
  }
  return value as T;
}

/** Pretty-print a maybe-encoded JSON column for display. */
export function prettyJson(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string") {
    try {
      return JSON.stringify(JSON.parse(value), null, 2);
    } catch {
      return value;
    }
  }
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}
