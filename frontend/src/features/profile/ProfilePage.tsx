import { useState } from "react";
import { Check, Copy, KeyRound } from "lucide-react";
import { AppShell } from "@/shared/layout/AppShell";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";

const API_TOKENS = [
  { id: "tok-1", label: "Local dev", value: "shp_live_4f8c...b21a", created: "12 Aug 2026" },
  { id: "tok-2", label: "CI pipeline", value: "shp_live_9d2e...74fc", created: "28 Jul 2026" },
];

function TokenRow({ label, value, created }: { label: string; value: string; created: string }) {
  const [copied, setCopied] = useState(false);

  const copy = () => {
    navigator.clipboard?.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border border-border/60 p-3">
      <div className="min-w-0">
        <p className="text-sm font-medium">{label}</p>
        <p className="truncate font-mono text-xs text-muted-foreground">{value}</p>
        <p className="mt-0.5 text-xs text-muted-foreground">Created {created}</p>
      </div>
      <Button
        variant="ghost"
        size="sm"
        onClick={copy}
        aria-label={`Copy the ${label} token`}
        className="shrink-0"
      >
        {copied ? <Check className="size-4 text-status-healthy" /> : <Copy className="size-4" />}
      </Button>
    </div>
  );
}

export function ProfilePage() {
  return (
    <AppShell pageTitle="Profile">
      <div className="max-w-3xl space-y-8">
        <section className="flex items-center gap-4">
          <Avatar className="size-16">
            <AvatarImage
              src="https://images.unsplash.com/photo-1633332755192-727a05c4013d?w=128&h=128&fit=crop&crop=faces"
              alt=""
            />
            <AvatarFallback>SF</AvatarFallback>
          </Avatar>
          <div>
            <h2 className="text-lg font-semibold">Shalon Fernando</h2>
            <p className="text-sm text-muted-foreground">shalonfernando52@gmail.com</p>
            <Badge variant="secondary" className="mt-2">
              Owner
            </Badge>
          </div>
        </section>

        <section className="space-y-4 rounded-xl border border-border/60 p-4">
          <div>
            <h3 className="text-base font-semibold">Account details</h3>
            <p className="text-sm text-muted-foreground">Mock only, nothing is saved.</p>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="profile-name">Full name</Label>
              <Input id="profile-name" defaultValue="Shalon Fernando" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="profile-email">Email</Label>
              <Input id="profile-email" type="email" defaultValue="shalonfernando52@gmail.com" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="profile-role">Role</Label>
              <Input id="profile-role" defaultValue="Owner" readOnly />
            </div>
            <div className="space-y-2">
              <Label htmlFor="profile-cluster">Default cluster</Label>
              <Input id="profile-cluster" defaultValue="selfheal-apps" readOnly />
            </div>
          </div>
          <Button size="sm">Save changes</Button>
        </section>

        <section className="space-y-4 rounded-xl border border-border/60 p-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h3 className="flex items-center gap-2 text-base font-semibold">
                <KeyRound className="size-4" />
                API tokens
              </h3>
              <p className="text-sm text-muted-foreground">
                Used by the ingest API and the decision engine.
              </p>
            </div>
            <Button variant="outline" size="sm">
              Generate token
            </Button>
          </div>
          <div className="space-y-2">
            {API_TOKENS.map((t) => (
              <TokenRow key={t.id} {...t} />
            ))}
          </div>
        </section>
      </div>
    </AppShell>
  );
}
