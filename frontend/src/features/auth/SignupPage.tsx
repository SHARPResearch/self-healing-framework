import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AuthLayout } from "./components/AuthLayout";
import { PasswordField } from "./components/PasswordField";
import { PasswordStrength } from "./components/PasswordStrength";

/** Mock only -- see LoginPage. Submitting just navigates to the dashboard. */
export function SignupPage() {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    navigate("/dashboard");
  };

  return (
    <AuthLayout
      title="Create an account"
      subtitle="Start monitoring your cluster in a few minutes."
      footer={
        <>
          Already have an account?{" "}
          <Link to="/login" className="font-medium text-foreground hover:underline">
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
          <Checkbox id="terms" className="mt-0.5" />
          <Label htmlFor="terms" className="text-sm font-normal leading-snug text-muted-foreground">
            I agree to the terms of service and privacy policy
          </Label>
        </div>

        <Button type="submit" className="w-full">
          Create account
        </Button>
      </form>

      <p className="mt-6 rounded-md border border-border/60 bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
        Demo build. Nothing is submitted or stored.
      </p>
    </AuthLayout>
  );
}
