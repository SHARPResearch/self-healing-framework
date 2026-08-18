import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AuthLayout } from "./components/AuthLayout";
import { PasswordField } from "./components/PasswordField";

/**
 * Mock only -- no real authentication. Submitting navigates to the dashboard
 * so the shell stays explorable; nothing is validated or persisted.
 */
export function LoginPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    navigate("/dashboard");
  };

  return (
    <AuthLayout
      title="Sign in"
      subtitle="Welcome back. Pick up where the cluster left off."
      footer={
        <>
          Don't have an account?{" "}
          <Link to="/signup" className="font-medium text-foreground hover:underline">
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
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            autoComplete="email"
          />
        </div>

        <PasswordField id="password" label="Password" value={password} onChange={setPassword} />

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Checkbox id="remember" />
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

        <Button type="submit" className="w-full">
          Sign in
        </Button>
      </form>

      <p className="mt-6 rounded-md border border-border/60 bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
        Demo build. Authentication is not wired up, so any details will do.
      </p>
    </AuthLayout>
  );
}
