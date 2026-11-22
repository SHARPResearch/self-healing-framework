import { useState, type FormEvent } from "react";
import { Link, Navigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AuthLayout } from "@/features/auth/components/AuthLayout";
import { FormError } from "@/features/auth/components/FormError";
import { AUTH_ENABLED, authClient, clearAccessToken, logOut, useSession } from "@/lib/auth";

const slugify = (name: string) =>
  name.toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 48);

/**
 * First stop for an account with no organization: create one (and become its owner), or wait for
 * an invitation. An organization is a tenant: its own fleet, models, decisions and logs.
 */
export function OnboardingPage() {
  const { data: session, isPending: sessionPending } = useSession();
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  if (!AUTH_ENABLED) return <Navigate to="/dashboard" replace />;
  if (!sessionPending && !session) return <Navigate to="/login?next=%2Fonboarding" replace />;

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setPending(true);
    setError(null);
    const slug = `${slugify(name) || "org"}-${Math.random().toString(36).slice(2, 6)}`;
    const { error: err } = await authClient.organization.create({ name, slug });
    setPending(false);
    if (err) {
      setError(err.message ?? "Could not create the organization");
      return;
    }
    clearAccessToken();
    window.location.assign("/model-lifecycle");     // the new organization is active now
  };

  return (
    <AuthLayout
      title="Create your organization"
      subtitle="Your team's services, models and decisions live here, separate from everyone else's."
      footer={
        <>
          Waiting for an invitation? Open the link from it, or{" "}
          <button type="button" onClick={() => void logOut()} className="font-medium text-foreground hover:underline">
            sign out
          </button>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="org-name">Organization name</Label>
          <Input id="org-name" required value={name} onChange={(e) => setName(e.target.value)}
            placeholder="Acme Platform Team" autoComplete="organization" />
          <p className="text-xs text-muted-foreground">
            You become its owner and can invite operators and viewers afterwards.
          </p>
        </div>
        <FormError message={error} />
        <Button type="submit" className="w-full" disabled={pending || !name.trim()}>
          {pending ? "Creating…" : "Create organization"}
        </Button>
      </form>
      <p className="mt-6 text-xs text-muted-foreground">
        Signed in as {session?.user.email ?? "…"}. <Link to="/" className="hover:underline">Back to the site</Link>
      </p>
    </AuthLayout>
  );
}
