import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, MailCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AuthLayout } from "./components/AuthLayout";

/** Mock only -- no email is sent, the success state is local. */
export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    setSent(true);
  };

  return (
    <AuthLayout
      title={sent ? "Check your inbox" : "Reset your password"}
      subtitle={
        sent
          ? "If an account exists for that address, a reset link is on its way."
          : "Enter your email and we'll send you a reset link."
      }
      footer={
        <Link
          to="/login"
          className="inline-flex items-center gap-1.5 font-medium text-foreground hover:underline"
        >
          <ArrowLeft className="size-3.5" />
          Back to sign in
        </Link>
      }
    >
      {sent ? (
        <div className="flex flex-col items-center gap-3 rounded-lg border border-border/60 bg-muted/40 px-4 py-8 text-center">
          <MailCheck className="size-7 text-status-healthy" />
          <p className="text-sm text-muted-foreground">
            Sent to <span className="font-medium text-foreground">{email || "your address"}</span>
          </p>
          <Button variant="ghost" size="sm" onClick={() => setSent(false)}>
            Use a different email
          </Button>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="reset-email">Email</Label>
            <Input
              id="reset-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              autoComplete="email"
            />
          </div>
          <Button type="submit" className="w-full">
            Send reset link
          </Button>
        </form>
      )}

      <p className="mt-6 rounded-md border border-border/60 bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
        Demo build. No email is actually sent.
      </p>
    </AuthLayout>
  );
}
