import { Lock, ShieldCheck } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

interface SecurityItem {
  surface: string;
  control: string;
}

/** Read only summary of the security posture documented in Doc1 §7. */
const ITEMS: SecurityItem[] = [
  {
    surface: "Service to service traffic",
    control: "mTLS via Istio, certificates issued by cert-manager",
  },
  {
    surface: "Redis Streams",
    control: "AUTH plus TLS, per consumer group ACLs",
  },
  {
    surface: "MLflow artifacts",
    control: "MinIO backed storage with IAM style bucket policies",
  },
  {
    surface: "TimescaleDB",
    control: "Connection string held in a Kubernetes Secret, never in an image",
  },
  {
    surface: "YARP admin API",
    control: "Bound to localhost only, not exposed through the ingress",
  },
  {
    surface: "LLM API keys",
    control: "Kubernetes Secrets mounted as environment variables",
  },
  {
    surface: "Decision engine service account",
    control: "Minimal RBAC: get and patch Deployments, delete Pods, create Events",
  },
  {
    surface: "React dashboard",
    control: "JWT auth, WebSocket connections carry the bearer token",
  },
];

export function SecurityTab() {
  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <h3 className="flex items-center gap-2 text-base font-semibold">
          <ShieldCheck className="size-4" />
          Security posture
        </h3>
        <p className="text-sm text-muted-foreground">
          Read only. These are enforced in the cluster, not from this page.
        </p>
      </div>

      <div className="rounded-xl border border-border/60">
        {ITEMS.map((item) => (
          <div
            key={item.surface}
            className="flex flex-col gap-1 border-b border-border/60 p-3 last:border-0 sm:flex-row sm:items-center sm:justify-between sm:gap-4"
          >
            <span className="text-sm font-medium">{item.surface}</span>
            <span className="text-sm text-muted-foreground sm:text-right">{item.control}</span>
          </div>
        ))}
      </div>

      <Alert>
        <Lock className="size-4" />
        <AlertTitle>Authentication is not wired up in this build</AlertTitle>
        <AlertDescription>
          The sign in flow is UI only. The JWT and RBAC controls listed above describe the intended
          deployment, not what this demo enforces.
        </AlertDescription>
      </Alert>
    </div>
  );
}
