// frontend\src\features\decisions\data\useDecisionRun.ts
import { useCallback, useEffect, useState } from "react";
import {
  fetchAnomalyEvidence,
  fetchEscalations,
  fetchExecutions,
  fetchNotifications,
  fetchShadowRecords,
  type ApiAnomalyDecisionRow,
  type ApiDbAnomaly,
  type ApiDecision,
  type ApiEscalationRow,
  type ApiExecutionRow,
  type ApiNotificationEntry,
  type ApiShadowRow,
} from "@/lib/api";
import { buildDecisionRun } from "../lib/runModel";
import type { DecisionRun } from "../types";

export interface DecisionRunState {
  run: DecisionRun | null;
  loading: boolean;
  /** Non-null only when every side-table call failed — a partial graph is still useful. */
  error: string | null;
  refresh: () => void;
}

/** Resolve to `fallback` instead of throwing: the graph tolerates a missing table. */
/**
 * Loads everything the run graph needs for one decision.
 *
 * Only the side tables the outcome actually writes are requested — an
 * AUTO_EXECUTE decision never queries escalations, and a HUMAN_LOOP decision
 * never queries executions. Notifications and the anomaly row are always
 * fetched (they exist for every decision).
 */
export function useDecisionRun(
  decision: ApiDecision | null,
  opts?: { pollMs?: number },
): DecisionRunState {
  const pollMs = opts?.pollMs ?? 0;
  const decisionId = decision?.decision_id ?? null;
  const [run, setRun] = useState<DecisionRun | null>(null);
  const [loading, setLoading] = useState(Boolean(decision));
  const [error, setError] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  const refresh = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    if (!decision || !decisionId) {
      setRun(null);
      setLoading(false);
      setError(null);
      return;
    }

    let alive = true;
    const outcome = String(decision.policy?.outcome ?? "").toUpperCase();

    const load = async () => {
      let failures = 0;
      const counted = async <T,>(promise: Promise<T>, fallback: T): Promise<T> => {
        try {
          return await promise;
        } catch {
          failures += 1;
          return fallback;
        }
      };

      const [executions, escalations, shadows, notifications, evidence] =
        await Promise.all([
          // Fetched for every outcome: an approved HUMAN_LOOP decision also
          // produces an execution row, and the graph has to show it.
          counted<ApiExecutionRow[]>(
            fetchExecutions(100, decision.service_id),
            [],
          ),
          counted<ApiEscalationRow[]>(
            outcome === "HUMAN_LOOP"
              ? fetchEscalations({ limit: 100 })
              : Promise.resolve<ApiEscalationRow[]>([]),
            [],
          ),
          counted<ApiShadowRow[]>(
            outcome === "SHADOW_MODE"
              ? fetchShadowRecords(100)
              : Promise.resolve<ApiShadowRow[]>([]),
            [],
          ),
          counted<ApiNotificationEntry[]>(fetchNotifications(200), []),
          counted<{ anomaly: ApiDbAnomaly } | null>(
            fetchAnomalyEvidence(decision.anomaly_id),
            null,
          ),
        ]);

      if (!alive) return;

      const anomaly: ApiDbAnomaly | ApiAnomalyDecisionRow | null =
        evidence?.anomaly ?? null;

      setRun(
        buildDecisionRun({
          decision,
          anomaly,
          executions,
          escalations,
          shadows,
          notifications,
        }),
      );
      setError(failures >= 5 ? "Could not reach the decision engine" : null);
      setLoading(false);
    };

    void load();

    if (pollMs <= 0) {
      return () => {
        alive = false;
      };
    }

    const id = window.setInterval(() => void load(), pollMs);
    return () => {
      alive = false;
      window.clearInterval(id);
    };
  }, [decision, decisionId, pollMs, nonce]);

  return { run, loading, error, refresh };
}
