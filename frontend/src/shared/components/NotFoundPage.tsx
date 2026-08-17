import { Link, useLocation } from "react-router-dom";
import { ArrowLeft, SearchX } from "lucide-react";
import { Button } from "@/components/ui/button";

export function NotFoundPage() {
  const { pathname } = useLocation();

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-background px-6 text-center text-foreground">
      <SearchX className="size-9 text-muted-foreground" />
      <p className="font-display text-5xl tracking-tight">404</p>
      <div className="space-y-1">
        <h1 className="text-lg font-semibold">Page not found</h1>
        <p className="max-w-sm text-sm text-muted-foreground">
          Nothing is routed at <span className="font-mono text-foreground">{pathname}</span>.
        </p>
      </div>
      <div className="mt-2 flex flex-wrap items-center justify-center gap-2">
        <Button asChild>
          <Link to="/dashboard">
            <ArrowLeft className="mr-2 size-4" />
            Back to dashboard
          </Link>
        </Button>
        <Button asChild variant="ghost">
          <Link to="/">Go to home page</Link>
        </Button>
      </div>
    </div>
  );
}
