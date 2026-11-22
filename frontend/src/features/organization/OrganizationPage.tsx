import { useState, type FormEvent } from "react";
import { Building2, Copy, Check, UserMinus, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { FormError } from "@/features/auth/components/FormError";
import { AUTH_ENABLED, authClient, ROLE_HINT, ROLES, useSession, type Role } from "@/lib/auth";
import { AppShell } from "@/shared/layout/AppShell";

/**
 * The active organization: who is in it, with which role, and pending invitations. Admins and
 * owners invite and manage members; everyone else sees the list. Without an email provider the
 * invitation link is shown here to pass on.
 */
export function OrganizationPage() {
  return (
    <AppShell pageTitle="Organization">
      {AUTH_ENABLED ? (
        <Members />
      ) : (
        <p className="text-sm text-muted-foreground">
          Accounts are off in this build (no VITE_AUTH=on), so there is one implicit organization.
        </p>
      )}
    </AppShell>
  );
}

function Members() {
  const { data: session } = useSession();
  const { data: org, refetch } = authClient.useActiveOrganization();
  const { data: myRole } = authClient.useActiveMemberRole();
  const canManage = myRole?.role === "owner" || myRole?.role === "admin";
  const [error, setError] = useState<string | null>(null);

  const run = async (call: Promise<{ error: { message?: string } | null }>) => {
    setError(null);
    const { error: err } = await call;
    if (err) setError(err.message ?? "That did not work");
    refetch();
  };

  if (!org) return <p className="text-sm text-muted-foreground">Loading the organization…</p>;
  const pending = (org.invitations ?? []).filter((i) => i.status === "pending");

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Building2 className="size-5 text-muted-foreground" />
        <div>
          <h2 className="text-base font-semibold">{org.name}</h2>
          <p className="text-sm text-muted-foreground">
            {org.members.length} member{org.members.length === 1 ? "" : "s"} · your role: {myRole?.role ?? "…"}
          </p>
        </div>
      </div>

      <FormError message={error} />

      <Card className="border-border/60">
        <CardHeader>
          <CardTitle className="text-sm">Members</CardTitle>
          <CardDescription>Roles decide what each person can do to this organization's fleet.</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Email</TableHead>
                <TableHead className="w-48">Role</TableHead>
                {canManage && <TableHead className="w-12" />}
              </TableRow>
            </TableHeader>
            <TableBody>
              {org.members.map((m) => {
                const self = m.userId === session?.user.id;
                const editable = canManage && !self && m.role !== "owner";
                return (
                  <TableRow key={m.id}>
                    <TableCell className="font-medium">{m.user.name}{self && " (you)"}</TableCell>
                    <TableCell className="text-muted-foreground">{m.user.email}</TableCell>
                    <TableCell>
                      {editable ? (
                        <RoleSelect value={m.role as Role} label={`Role of ${m.user.name}`}
                          onChange={(role) => void run(authClient.organization.updateMemberRole({ memberId: m.id, role }))} />
                      ) : (
                        <span className="capitalize">{m.role}</span>
                      )}
                    </TableCell>
                    {canManage && (
                      <TableCell>
                        {editable && (
                          <Button variant="ghost" size="icon" aria-label={`Remove ${m.user.name}`}
                            onClick={() => void run(authClient.organization.removeMember({ memberIdOrEmail: m.id }))}>
                            <UserMinus className="size-4" />
                          </Button>
                        )}
                      </TableCell>
                    )}
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {canManage && <InviteForm onInvited={refetch} />}

      {pending.length > 0 && (
        <Card className="border-border/60">
          <CardHeader>
            <CardTitle className="text-sm">Pending invitations</CardTitle>
            <CardDescription>Valid for 7 days. Send the link if no email went out.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {pending.map((inv) => (
              <div key={inv.id} className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border/50 px-3 py-2">
                <div className="min-w-0 text-sm">
                  <span className="font-medium">{inv.email}</span>
                  <span className="text-muted-foreground"> · {inv.role}</span>
                </div>
                <div className="flex items-center gap-1">
                  <CopyLink url={`${window.location.origin}/accept-invitation/${inv.id}`} />
                  {canManage && (
                    <Button variant="ghost" size="icon" aria-label={`Cancel the invitation to ${inv.email}`}
                      onClick={() => void run(authClient.organization.cancelInvitation({ invitationId: inv.id }))}>
                      <X className="size-4" />
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function RoleSelect({ value, onChange, label }: { value: Role; onChange: (role: Role) => void; label: string }) {
  return (
    <Select value={value} onValueChange={(v) => onChange(v as Role)}>
      <SelectTrigger className="h-8 w-40" aria-label={label}>
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {ROLES.map((r) => (
          <SelectItem key={r} value={r} disabled={r === "owner"}>
            <span className="capitalize">{r}</span>
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

function InviteForm({ onInvited }: { onInvited: () => void }) {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role>("operator");
  const [error, setError] = useState<string | null>(null);
  const [link, setLink] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setPending(true);
    setError(null);
    const { data, error: err } = await authClient.organization.inviteMember({ email, role });
    setPending(false);
    if (err || !data) {
      setError(err?.message ?? "Could not invite");
      return;
    }
    setLink(`${window.location.origin}/accept-invitation/${data.id}`);
    setEmail("");
    onInvited();
  };

  return (
    <Card className="border-border/60">
      <CardHeader>
        <CardTitle className="text-sm">Invite someone</CardTitle>
        <CardDescription>{ROLE_HINT[role]}.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <form onSubmit={submit} className="flex flex-wrap items-end gap-2">
          <div className="min-w-56 flex-1 space-y-1.5">
            <Label htmlFor="invite-email">Email</Label>
            <Input id="invite-email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
              placeholder="teammate@example.com" />
          </div>
          <div className="space-y-1.5">
            <Label>Role</Label>
            <RoleSelect value={role} onChange={setRole} label="Role for the invitation" />
          </div>
          <Button type="submit" disabled={pending}>{pending ? "Inviting…" : "Invite"}</Button>
        </form>
        <FormError message={error} />
        {link && (
          <div className="flex items-center justify-between gap-2 rounded-md bg-muted/40 px-3 py-2 text-xs">
            <span className="truncate font-mono text-muted-foreground">{link}</span>
            <CopyLink url={link} />
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function CopyLink({ url }: { url: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <Button variant="ghost" size="sm" className="gap-1.5" onClick={() => {
      void navigator.clipboard.writeText(url).then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      });
    }}>
      {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
      {copied ? "Copied" : "Copy link"}
    </Button>
  );
}
