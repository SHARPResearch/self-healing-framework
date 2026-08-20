import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Checkbox } from "@/components/ui/checkbox";
import { SeverityBadge } from "@/shared/components/SeverityBadge";
import type { Severity } from "@/shared/types";

const SEVERITIES: Severity[] = ["watch", "warn", "degrade", "critical"];

const CHANNELS = [
  { id: "in-app", label: "In app", description: "The bell panel and notifications page.", on: true },
  { id: "email", label: "Email", description: "Digest of everything at degrade and above.", on: true },
  { id: "slack", label: "Slack", description: "Post to a channel via incoming webhook.", on: false },
  { id: "webhook", label: "Webhook", description: "POST the raw action receipt JSON.", on: false },
];

export function NotificationsTab() {
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h3 className="text-base font-semibold">Notifications</h3>
        <p className="text-sm text-muted-foreground">
          Which events reach you, and how.
        </p>
      </div>

      <section className="space-y-3 rounded-xl border border-border/60 p-4">
        <h4 className="text-sm font-medium">Channels</h4>
        {CHANNELS.map((channel) => (
          <div
            key={channel.id}
            className="flex items-center justify-between gap-4 rounded-lg border border-border/60 p-3"
          >
            <div>
              <Label htmlFor={channel.id}>{channel.label}</Label>
              <p className="text-xs text-muted-foreground">{channel.description}</p>
            </div>
            <Switch id={channel.id} defaultChecked={channel.on} />
          </div>
        ))}
      </section>

      <section className="space-y-3 rounded-xl border border-border/60 p-4">
        <h4 className="text-sm font-medium">Notify me at these severities</h4>
        <div className="flex flex-wrap gap-4">
          {SEVERITIES.map((severity) => (
            <div key={severity} className="flex items-center gap-2">
              <Checkbox id={`sev-${severity}`} defaultChecked={severity !== "watch"} />
              <Label htmlFor={`sev-${severity}`} className="font-normal">
                <SeverityBadge severity={severity} />
              </Label>
            </div>
          ))}
        </div>
      </section>

      <section className="space-y-3 rounded-xl border border-border/60 p-4">
        <h4 className="text-sm font-medium">Slack webhook</h4>
        <div className="space-y-2">
          <Label htmlFor="slack-webhook">Incoming webhook URL</Label>
          <Input
            id="slack-webhook"
            placeholder="https://hooks.slack.com/services/..."
            className="font-mono text-xs"
          />
        </div>
      </section>

      <Button size="sm">Save notification settings</Button>
    </div>
  );
}
