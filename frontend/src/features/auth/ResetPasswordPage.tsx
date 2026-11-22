import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { authClient } from "@/lib/auth";
import { AuthLayout } from "./components/AuthLayout";
import { FormError } from "./components/FormError";
import { PasswordField } from "./components/PasswordField";
import { PasswordStrength } from "./components/PasswordStrength";

/** Where a reset link lands (/reset-password?token=...): choose the new password. */
export function ResetPasswordPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const token = params.get("token");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(params.get("error") ? "This reset link has expired" : null);
  const [pending, setPending] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!token) return;
    setPending(true);
    const { error: err } = await authClient.resetPassword({ newPassword: password, token });
    setPending(false);
    if (err) {
      setError(err.message ?? "Could not reset the password");
      return;
    }
    navigate("/login", { replace: true });
  };

  return (
    <AuthLayout
      title="Choose a new password"
      subtitle="Then sign in with it."
      footer={
        <Link to="/forgot-password" className="font-medium text-foreground hover:underline">
          Request a new link
        </Link>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-2">
          <PasswordField id="new-password" label="New password" value={password} onChange={setPassword}
            autoComplete="new-password" />
          <PasswordStrength password={password} />
        </div>
        <FormError message={token ? error : "This page needs the link from the reset email"} />
        <Button type="submit" className="w-full" disabled={!token || pending}>
          {pending ? "Saving…" : "Set password"}
        </Button>
      </form>
    </AuthLayout>
  );
}
