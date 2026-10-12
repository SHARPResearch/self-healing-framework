import { useEffect, useState } from "react";
import { fetchAnomalyEvidence, type ApiEvidenceBundle } from "@/lib/api";

/**
 * Polls the evidence bundle for an anomaly every `pollMs` while mounted.
 * Set `pollMs = 0` to disable polling (load once).
 */
export function useAnomalyEvidence(anomalyId: string | null, pollMs = 5000) {
  const [data, setData] = useState<ApiEvidenceBundle | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!anomalyId) {
      setData(null);
      return;
    }

    let alive = true;
    setLoading(true);

    const load = async () => {
      try {
        const bundle = await fetchAnomalyEvidence(anomalyId);
        if (!alive) return;
        setData(bundle);
        setError(null);
      } catch (err: any) {
        if (!alive) return;
        setError(String(err.message ?? err));
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
  }, [anomalyId, pollMs]);

  return { data, loading, error };
}
