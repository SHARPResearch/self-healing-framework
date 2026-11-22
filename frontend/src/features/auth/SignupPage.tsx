import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AUTH_ENABLED, signUp } from "@/lib/auth";
import { AuthLayout } from "./components/AuthLayout";
import { FormError } from "./components/FormError";
import { PasswordField } from "./components/PasswordField";
import { PasswordStrength } from "./components/PasswordStrength";

/**
 * Create an account (Better Auth). A new account belongs to no organization yet, so it continues
 * to an invitation it was sent (`next`) or to creating its own organization.
 */
export function SignupPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const next = params.get("next");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [agreed, setAgreed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!AUTH_ENABLED) {
      navigate("/dashboard");
      return;
    }
    if (!agreed) {
      setError("Please accept the terms to continue");
      return;
    }
    setPending(true);
    setError(null);
    const { error: err } = await signUp.email({ name, email, password });
    setPending(false);
    if (err) {
      setError(err.message ?? "Could not create the account");
      return;
    }
    navigate(next || "/onboarding", { replace: true });
  };

  return (
    <AuthLayout
      title="Create an account"
      subtitle="Start monitoring your cluster in a few minutes."
      footer={
        <>
          Already have an account?{" "}
          <Link to={`/login${params.toString() ? `?${params}` : ""}`} className="font-medium text-foreground hover:underline">
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="name">Full name</Label>
          <Input
            id="name"
            required={AUTH_ENABLED}
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Ada Lovelace"
            autoComplete="name"
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="signup-email">Work email</Label>
          <Input
            id="signup-email"
            type="email"
            required={AUTH_ENABLED}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            autoComplete="email"
          />
        </div>

        <div className="space-y-2">
          <PasswordField
            id="signup-password"
            label="Password"
            value={password}
            onChange={setPassword}
            autoComplete="new-password"
          />
          <PasswordStrength password={password} />
        </div>

        <div className="flex items-start gap-2">
          <Checkbox id="terms" className="mt-0.5" checked={agreed} onCheckedChange={(v) => setAgreed(v === true)} />
          <Label htmlFor="terms" className="text-sm font-normal leading-snug text-muted-foreground">
            I agree to the terms of service and privacy policy
          </Label>
        </div>

        <FormError message={error} />

        <Button type="submit" className="w-full" disabled={pending}>
          {pending ? "Creating account…" : "Create account"}
        </Button>
      </form>

      {!AUTH_ENABLED && (
        <p className="mt-6 rounded-md border border-border/60 bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
          Local demo build: accounts are off, so nothing is stored.
        </p>
      )}
    </AuthLayout>
  );
}
