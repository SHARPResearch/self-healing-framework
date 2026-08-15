import { Link } from "react-router-dom";
import { Activity } from "lucide-react";
import { Button } from "@/components/ui/button";

/**
 * Placeholder only -- real authentication is out of scope for this pass.
 * Exists so routing distinguishes the public/pre-login area from
 * DashboardPage (the actual deliverable, the page that loads after login).
 */
export function LoginStubPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 bg-background px-4 text-center">
      <div className="flex items-center gap-2">
        <div className="flex size-9 items-center justify-center rounded-md bg-primary text-primary-foreground">
          <Activity className="size-5" />
        </div>
        <span className="text-lg font-semibold tracking-tight">SHARP</span>
      </div>
      <div className="space-y-1">
        <h1 className="text-xl font-semibold">Sign in</h1>
        <p className="text-sm text-muted-foreground">
          Authentication isn't built yet -- continue to preview the dashboard.
        </p>
      </div>
      <Button asChild>
        <Link to="/dashboard">Continue to dashboard</Link>
      </Button>
    </div>
  );
}
