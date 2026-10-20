import { useCallback, useEffect, useState } from "react";
import { fetchRuleAudit, type ApiRuleAuditEntry } from "@/lib/api";

export function useRuleAudit(ruleId: string | null, pollMs = 15000) {
  const [entries, setEntries] = useState<ApiRuleAuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  const refetch = useCallback(() => setTick((n) => n + 1), []);

  useEffect(() => {
    if (!ruleId) {
      setEntries([]);
      setLoading(false);
      return;
    }
    let alive = true;
    const load = async () => {
      try {
        const list = await fetchRuleAudit(ruleId);
        if (!alive) return;
        setEntries(list);
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
  }, [ruleId, pollMs, tick]);

  return { entries, loading, error, refetch };
}
