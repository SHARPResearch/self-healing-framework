import { useEffect, useState } from "react";
import { fetchDecisions, type ApiDecision } from "@/lib/api";

export function useDecisions(pollMs = 5000) {
  const [items, setItems] = useState<ApiDecision[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const list = await fetchDecisions(200);
        if (!alive) return;
        setItems(list);
        setError(null);
      } catch (e: any) {
        if (!alive) return;
        setError(String(e.message ?? e));
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
  }, [pollMs]);

  return { items, loading, error };
}
