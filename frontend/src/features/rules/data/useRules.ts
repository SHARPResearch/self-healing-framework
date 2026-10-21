import { useCallback, useEffect, useState } from "react";
import { fetchRules, type ApiRule, type RuleListFilter } from "@/lib/api";

export function useRules(filter: RuleListFilter = "all", pollMs = 10000) {
  const [rules, setRules] = useState<ApiRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  const refetch = useCallback(() => setTick((n) => n + 1), []);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const list = await fetchRules(filter);
        if (!alive) return;
        setRules(list);
        setError(null);
      } catch (e: unknown) {
        if (!alive) return;
        setError(String((e as Error)?.message ?? e));
      } finally {
        if (alive) setLoading(false);
      }
    };
    load();
    if (pollMs > 0) {
      const id = setInterval(load, pollMs);
      return () => {
        alive = false;
        clearInterval(id);
      };
    }
    return () => {
      alive = false;
    };
  }, [filter, pollMs, tick]);

  return { rules, loading, error, refetch };
}

/** All rules regardless of tab — used to compute per-tab counts. */
export function useAllRules(pollMs = 10000) {
  return useRules("all", pollMs);
}
