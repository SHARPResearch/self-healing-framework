import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AUTH_ENABLED, signIn } from "@/lib/auth";
import { AuthLayout } from "./components/AuthLayout";
import { FormError } from "./components/FormError";
import { PasswordField } from "./components/PasswordField";

/**
 * Email and password sign in (Better Auth, services/auth). With auth off (no VITE_AUTH=on) the
 * dashboard has no accounts, so submitting just opens it.
 */
export function LoginPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const next = params.get("next") || "/dashboard";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!AUTH_ENABLED) {
      navigate(next);
      return;
    }
    setPending(true);
    setError(null);
    const { error: err } = await signIn.email({ email, password, rememberMe: remember });
    setPending(false);
    if (err) {
      setError(err.message ?? "Could not sign in");
      return;
    }
    navigate(next, { replace: true });
  };

  return (
    <AuthLayout
      title="Sign in"
      subtitle="Welcome back. Pick up where the cluster left off."
      footer={
        <>
          Don't have an account?{" "}
          <Link to={`/signup${params.toString() ? `?${params}` : ""}`} className="font-medium text-foreground hover:underline">
            Create one
          </Link>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            type="email"
            required={AUTH_ENABLED}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            autoComplete="email"
          />
        </div>

        <PasswordField id="password" label="Password" value={password} onChange={setPassword} />

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Checkbox id="remember" checked={remember} onCheckedChange={(v) => setRemember(v === true)} />
            <Label htmlFor="remember" className="text-sm font-normal text-muted-foreground">
              Remember me
            </Label>
          </div>
          <Link
            to="/forgot-password"
            className="text-sm text-muted-foreground hover:text-foreground hover:underline"
          >
            Forgot password?
          </Link>
        </div>

        <FormError message={error} />

        <Button type="submit" className="w-full" disabled={pending}>
          {pending ? "Signing in…" : "Sign in"}
        </Button>
      </form>

      {!AUTH_ENABLED && (
        <p className="mt-6 rounded-md border border-border/60 bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
          Local demo build: accounts are off, so any details will do.
        </p>
      )}
    </AuthLayout>
  );
}
