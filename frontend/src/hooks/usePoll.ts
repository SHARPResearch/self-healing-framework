// frontend\src\hooks\usePoll.ts
import { useCallback, useEffect, useRef, useState } from "react";

export interface PollResult<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

/**
 * Fetch-on-mount with optional re-polling. Used by the decision-engine
 * screens (escalations, shadow, executions) which are not part of the
 * ml-backend WebSocket stream and therefore refresh on an interval instead.
 *
 * `key` re-runs the loader when it changes (filters, ids); `refresh()` forces
 * a one-off reload.
 */
export function usePoll<T>(
  loader: () => Promise<T>,
  options: { pollMs?: number; key?: string } = {},
): PollResult<T> {
  const { pollMs = 0, key = "" } = options;
  const loaderRef = useRef(loader);
  loaderRef.current = loader;

  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  const refresh = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    let alive = true;

    const run = async () => {
      try {
        const result = await loaderRef.current();
        if (!alive) return;
        setData(result);
        setError(null);
      } catch (e) {
        if (!alive) return;
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (alive) setLoading(false);
      }
    };

    setLoading(true);
    void run();

    if (pollMs <= 0) {
      return () => {
        alive = false;
      };
    }

    const id = window.setInterval(() => void run(), pollMs);
    return () => {
      alive = false;
      window.clearInterval(id);
    };
  }, [key, pollMs, nonce]);

  return { data, loading, error, refresh };
}
