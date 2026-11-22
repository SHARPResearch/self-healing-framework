import { PlugZap } from "lucide-react";
import { AppShell } from "@/shared/layout/AppShell";
import { selectOpenQueries, useLiveStore } from "@/shared/store/liveStore";
import { useShallow } from "zustand/react/shallow";
import { CadalExplainer } from "./components/CadalExplainer";
import { DecisionLog } from "./components/DecisionLog";
import { DemoControls } from "./components/DemoControls";
import { LifecycleFeed } from "./components/LifecycleFeed";
import { OperatorQueryCard } from "./components/OperatorQueryCard";
import { ServiceLifecycleCard } from "./components/ServiceLifecycleCard";
import { TelemetryEvidence } from "./components/TelemetryEvidence";

/**
 * Component 2 live: CADAL (change-aware, drift-attributed lifecycle) running in services/ml-backend,
 * on a replay of real SMD telemetry or on the live Online Boutique (then with its raw telemetry).
 * Live only; there is deliberately no mock fallback here, since a simulated lifecycle would
 * misrepresent what the research component does.
 */
export function ModelLifecyclePage() {
  const ready = useLiveStore((s) => s.ready);
  const status = useLiveStore((s) => s.status);
  const services = useLiveStore(useShallow((s) => s.serviceOrder.map((id) => s.services[id]).filter(Boolean)));
  const queries = useLiveStore(useShallow(selectOpenQueries));
  const live = useLiveStore((s) => s.health?.mode === "prometheus");

  return (
    <AppShell pageTitle="Model lifecycle">
      <div className="space-y-6">
        <div>
          <h2 className="text-base font-semibold">Dynamic model updating</h2>
          <p className="text-sm text-muted-foreground">
            One smoothed PCA detector per service with a POT threshold. CADAL decides when a model may
            change, and asks the operator only when the evidence cannot decide without labels.
          </p>
        </div>

        {!ready ? (
          <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed border-border/60 px-6 py-16 text-center">
            <PlugZap className="size-8 text-muted-foreground" />
            <p className="text-sm font-medium">
              {status === "connecting" ? "Connecting to ml-backend…" : "ml-backend is not running"}
            </p>
            <p className="max-w-md text-xs text-muted-foreground">
              This page shows the live lifecycle only. Start the stack with{" "}
              <span className="font-mono">docker compose -f infrastructure/local/docker-compose.demo.yml up -d</span>{" "}
              and <span className="font-mono">uv run uvicorn app.main:app --port 8002</span> in{" "}
              <span className="font-mono">services/ml-backend</span>, or deploy it into the cluster with{" "}
              <span className="font-mono">infrastructure/online-boutique/deploy-sharp.ps1</span>. It reconnects
              automatically.
            </p>
          </div>
        ) : (
          <>
            <DemoControls />
            <CadalExplainer />

            {queries.length > 0 && (
              <div className="space-y-3">
                {queries.map((q) => (
                  <OperatorQueryCard key={q.queryId} query={q} />
                ))}
              </div>
            )}

            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
              {services.map((s) => (
                <ServiceLifecycleCard key={s.serviceId} service={s} />
              ))}
            </div>

            {live && <TelemetryEvidence />}

            <div className="grid grid-cols-1 gap-4 xl:grid-cols-[2fr_3fr]">
              <LifecycleFeed />
              <DecisionLog />
            </div>
          </>
        )}
      </div>
    </AppShell>
  );
}
