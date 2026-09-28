import { CheckCircle2, CircleAlert } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";

interface Integration {
  id: string;
  name: string;
  description: string;
  endpoint: string;
  connected: boolean;
}

const INTEGRATIONS: Integration[] = [
  {
    id: "prometheus",
    name: "Prometheus",
    description: "Scrapes container and HTTP metrics every 15s.",
    endpoint: "http://prometheus.monitoring.svc:9090",
    connected: true,
  },
  {
    id: "redis",
    name: "Redis Streams",
    description: "Carries anomaly and action receipt events between services.",
    endpoint: "redis://redis.selfheal-system.svc:6379",
    connected: true,
  },
  {
    id: "mlflow",
    name: "MLflow",
    description: "Model registry, experiment tracking and rollback snapshots.",
    endpoint: "http://mlflow.selfheal-system.svc:5000",
    connected: true,
  },
  {
    id: "timescale",
    name: "TimescaleDB",
    description: "Metric event hypertable and pgvector embeddings.",
    endpoint: "postgres://timescale.selfheal-system.svc:5432/selfheal",
    connected: true,
  },
  {
    id: "kubernetes",
    name: "Kubernetes API",
    description: "Scales deployments, restarts pods, reads upstream annotations.",
    endpoint: "https://kubernetes.default.svc",
    connected: true,
  },
  {
    id: "yarp",
    name: "YARP admin API",
    description: "Traffic weight control, bound to localhost only.",
    endpoint: "http://127.0.0.1:5001/admin",
    connected: false,
  },
];

export function IntegrationsTab() {
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h3 className="text-base font-semibold">Integrations</h3>
        <p className="text-sm text-muted-foreground">
          Where SHARP reads telemetry from and where it dispatches actions to.
        </p>
      </div>

      <div className="space-y-3">
        {INTEGRATIONS.map((integration) => (
          <div key={integration.id} className="space-y-3 rounded-xl border border-border/60 p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <h4 className="text-sm font-medium">{integration.name}</h4>
                  {integration.connected ? (
                    <span className="flex items-center gap-1 text-xs text-status-healthy">
                      <CheckCircle2 className="size-3.5" />
                      Connected
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 text-xs text-status-degrade">
                      <CircleAlert className="size-3.5" />
                      Not reachable
                    </span>
                  )}
                </div>
                <p className="mt-0.5 text-xs text-muted-foreground">{integration.description}</p>
              </div>
              <Button variant="outline" size="sm">
                Test
              </Button>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor={`${integration.id}-endpoint`} className="text-xs">
                Endpoint
              </Label>
              <Input
                id={`${integration.id}-endpoint`}
                defaultValue={integration.endpoint}
                className="font-mono text-xs"
              />
            </div>
          </div>
        ))}
      </div>

      <Button size="sm">Save integrations</Button>
    </div>
  );
}
