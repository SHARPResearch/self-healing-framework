import { create } from "zustand";
import { services } from "@/features/dashboard/data/mockData";
import type { IncidentEntry } from "@/features/dashboard/types";
import { rankActions, type PolicyAction } from "../lib/policyActions";
import type { Severity } from "../types";

export interface PolicyEvaluation {
  id: string;
  serviceId: string;
  serviceName: string;
  serviceStatus: Severity;
  status: "evaluating" | "ready" | "executed";
  actions: PolicyAction[];
}

interface RemediationState {
  evaluation: PolicyEvaluation | null;
  liveIncidents: IncidentEntry[];
  recoveryActionsDelta: number;
  serviceOverrides: Record<string, Severity>;
  simulateAnomaly: (serviceId: string) => void;
  executeAction: () => void;
  dismiss: () => void;
}

let liveIncidentCounter = 0;

/**
 * Backs the "simulate anomaly -> RL policy evaluation -> execute remediation"
 * demo flow shared between the Dashboard and Incidents pages, same
 * create/set shape as notificationStore.ts so the header bell and this
 * banner never disagree about shared state.
 */
export const useRemediationStore = create<RemediationState>((set, get) => ({
  evaluation: null,
  liveIncidents: [],
  recoveryActionsDelta: 0,
  serviceOverrides: {},

  simulateAnomaly: (serviceId) => {
    const service = services.find((s) => s.serviceId === serviceId);
    if (!service) return;

    const id = `eval-${serviceId}-${Date.now()}`;
    set({
      evaluation: {
        id,
        serviceId,
        serviceName: service.displayName,
        serviceStatus: service.status,
        status: "evaluating",
        actions: [],
      },
    });

    setTimeout(() => {
      const current = get().evaluation;
      if (current?.id !== id) return; // superseded by a newer simulation
      set({ evaluation: { ...current, status: "ready", actions: rankActions(service) } });
    }, 1200);
  },

  executeAction: () => {
    const evaluation = get().evaluation;
    if (!evaluation || evaluation.status !== "ready") return;

    const topAction = evaluation.actions[0];
    liveIncidentCounter += 1;
    const incident: IncidentEntry = {
      id: `live-${liveIncidentCounter}`,
      serviceId: evaluation.serviceId,
      serviceName: evaluation.serviceName,
      severity: evaluation.serviceStatus,
      actionType: topAction.label,
      executor: "decision-engine",
      timestamp: new Date().toISOString(),
      details: `Simulated RL policy evaluation selected "${topAction.label}" (confidence ${Math.round(topAction.confidence * 100)}%).`,
    };

    set((state) => ({
      evaluation: { ...evaluation, status: "executed" },
      liveIncidents: [incident, ...state.liveIncidents],
      recoveryActionsDelta: state.recoveryActionsDelta + 1,
      serviceOverrides: { ...state.serviceOverrides, [evaluation.serviceId]: "watch" },
    }));

    setTimeout(() => {
      set((state) => (state.evaluation?.id === evaluation.id ? { evaluation: null } : state));
    }, 3500);
  },

  dismiss: () => set({ evaluation: null }),
}));
