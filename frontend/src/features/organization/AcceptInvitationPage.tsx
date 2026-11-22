import { useEffect, useState } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import { MailOpen } from "lucide-react";
import { Button } from "@/components/ui/button";
import { AuthLayout } from "@/features/auth/components/AuthLayout";
import { FormError } from "@/features/auth/components/FormError";
import { AUTH_ENABLED, authClient, clearAccessToken, useSession } from "@/lib/auth";

interface InvitationInfo {
  organizationName: string;
  inviterEmail: string;
  role: string;
  email: string;
}

/**
 * Where an invitation link lands (/accept-invitation/:id). The invitation is for one email
 * address, so the invited person signs in (or creates the account) first, then accepts.
 */
export function AcceptInvitationPage() {
  const { id = "" } = useParams();
  const { data: session, isPending } = useSession();
  const [info, setInfo] = useState<InvitationInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!session) return;
    authClient.organization
      .getInvitation({ query: { id } })
      .then(({ data, error: err }) => {
        if (err) setError(err.message ?? "This invitation is not valid");
        else setInfo(data as unknown as InvitationInfo);
      });
  }, [id, session]);

  if (!AUTH_ENABLED) return <Navigate to="/dashboard" replace />;
  if (!isPending && !session) {
    const next = encodeURIComponent(`/accept-invitation/${id}`);
    return <Navigate to={`/signup?next=${next}`} replace />;
  }

  const respond = async (accept: boolean) => {
    setBusy(true);
    const { error: err } = accept
      ? await authClient.organization.acceptInvitation({ invitationId: id })
      : await authClient.organization.rejectInvitation({ invitationId: id });
    setBusy(false);
    if (err) {
      setError(err.message ?? "Could not answer the invitation");
      return;
    }
    clearAccessToken();
    window.location.assign(accept ? "/model-lifecycle" : "/onboarding");
  };

  return (
    <AuthLayout
      title={info ? `Join ${info.organizationName}` : "Invitation"}
      subtitle={info ? `${info.inviterEmail} invited you as ${info.role}.` : "Checking the invitation…"}
      footer={<Link to="/dashboard" className="font-medium text-foreground hover:underline">Not now</Link>}
    >
      <div className="space-y-4">
        <div className="flex items-center gap-3 rounded-lg border border-border/60 bg-muted/40 px-4 py-4">
          <MailOpen className="size-5 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">
            Signed in as <span className="font-medium text-foreground">{session?.user.email ?? "…"}</span>
            {info && info.email !== session?.user.email && (
              <> but the invitation is for <span className="font-medium text-foreground">{info.email}</span>. Sign in with that address to accept.</>
            )}
          </p>
        </div>
        <FormError message={error} />
        <div className="flex gap-2">
          <Button className="flex-1" disabled={!info || busy} onClick={() => void respond(true)}>
            Accept
          </Button>
          <Button variant="outline" disabled={!info || busy} onClick={() => void respond(false)}>
            Decline
          </Button>
        </div>
      </div>
    </AuthLayout>
  );
}
