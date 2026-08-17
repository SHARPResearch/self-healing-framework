import type { ReactNode } from "react";
import { Link } from "react-router-dom";

interface AuthLayoutProps {
  title: string;
  subtitle: string;
  children: ReactNode;
  footer: ReactNode;
}

/**
 * Split-panel shell shared by sign in, sign up and forgot password. Left panel
 * carries the brand and the same closed-loop framing the marketing page uses;
 * right panel is the form. Left panel collapses away below lg.
 */
export function AuthLayout({ title, subtitle, children, footer }: AuthLayoutProps) {
  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <aside className="relative hidden w-1/2 flex-col justify-between overflow-hidden border-r border-border bg-card p-10 lg:flex">
        <div
          aria-hidden="true"
          className="animate-blob-drift pointer-events-none absolute -top-32 -left-24 size-96 rounded-full bg-status-healthy/10 blur-[120px]"
        />
        <div
          aria-hidden="true"
          className="animate-blob-drift pointer-events-none absolute -right-24 -bottom-32 size-96 rounded-full bg-status-warn/10 blur-[120px]"
        />

        <Link to="/" className="relative flex items-center gap-2">
          <div className="flex size-8 items-center justify-center rounded-md bg-primary">
            <img src="/favicon.svg" alt="" className="size-5" />
          </div>
          <span className="text-base font-semibold tracking-tight">SHARP</span>
        </Link>

        <div className="relative space-y-4">
          <p className="font-display text-2xl leading-snug tracking-tight">
            Predict the failure.
            <br />
            Fix it before anyone notices.
          </p>
          <p className="max-w-md text-sm text-muted-foreground">
            SHARP watches every Kubernetes service, scores anomalies as telemetry streams in, and
            runs graduated remediation automatically. No batch retraining, no restart scripts.
          </p>
        </div>

        <p className="relative text-xs text-muted-foreground">
          self-healing-framework &bull; SHARPResearch
        </p>
      </aside>

      <main className="flex w-full flex-col justify-center px-6 py-12 lg:w-1/2 lg:px-16">
        <div className="mx-auto w-full max-w-sm">
          <Link to="/" className="mb-8 flex items-center gap-2 lg:hidden">
            <div className="flex size-8 items-center justify-center rounded-md bg-primary">
              <img src="/favicon.svg" alt="" className="size-5" />
            </div>
            <span className="text-base font-semibold tracking-tight">SHARP</span>
          </Link>

          <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
          <p className="mt-1.5 mb-8 text-sm text-muted-foreground">{subtitle}</p>

          {children}

          <div className="mt-8 text-center text-sm text-muted-foreground">{footer}</div>
        </div>
      </main>
    </div>
  );
}
