import { useEffect, useMemo, useState } from "react";
import { Lock, RotateCw, Save, Info, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { toast } from "@/shared/store/toastStore";
import {
  useSettings,
  useSettingsAudit,
  useNotifications,
} from "../data/useSettings";
import { PREMIUM_ACTOR, type ApiEngineSetting } from "@/lib/api";

type Draft = Record<string, number | boolean | string>;

export function RuntimeTab() {
  const { settings, groups, loading, error, save, reload } = useSettings(0);
  const { entries: audit } = useSettingsAudit(0);
  const { entries: notifs } = useNotifications(10000);

  // Local draft of edited values, keyed by setting key.
  const [draft, setDraft] = useState<Draft>({});
  const [saving, setSaving] = useState(false);

  // The only "user" is the hardcoded premium owner for now.
  const isPremium = true;
  const actor = PREMIUM_ACTOR;

  // Reset the draft whenever the server values change (after a save/reload).
  useEffect(() => {
    setDraft({});
  }, [settings]);

  const byKey = useMemo(() => {
    const m = new Map<string, ApiEngineSetting>();
    for (const s of settings) m.set(s.key, s);
    return m;
  }, [settings]);

  const valueOf = (s: ApiEngineSetting): number | boolean | string =>
    s.key in draft ? draft[s.key] : s.value;

  const setValue = (key: string, value: number | boolean | string) =>
    setDraft((d) => ({ ...d, [key]: value }));

  const dirtyKeys = Object.keys(draft).filter((k) => {
    const s = byKey.get(k);
    if (!s) return false;
    return valueOf(s) !== s.value;
  });

  const onSave = async () => {
    if (dirtyKeys.length === 0) {
      toast("No changes to save", "default");
      return;
    }
    const patch: Draft = {};
    for (const k of dirtyKeys) patch[k] = draft[k];
    setSaving(true);
    try {
      const result = await save(patch, actor);
      const restart = result.requires_restart ?? [];
      if (restart.length > 0) {
        toast(
          `Saved ${result.changed.length} setting(s)`,
          "success",
          `Restart required for: ${restart.join(", ")}`,
        );
      } else {
        toast(`Saved ${result.changed.length} setting(s)`, "success");
      }
    } catch (e: unknown) {
      toast("Save failed", "error", String((e as Error)?.message ?? e));
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="mx-auto max-w-3xl py-12 text-center text-sm text-muted-foreground">
        Loading runtime settings…
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto max-w-3xl py-12 text-center text-sm text-destructive">
        {error}
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold">Runtime engine settings</h3>
          <p className="text-sm text-muted-foreground">
            Live knobs for the decision engine. Changes marked{" "}
            <span className="font-mono text-xs">live</span> apply immediately;
            others take effect on the next restart.
          </p>
        </div>
        <Button size="sm" variant="outline" onClick={() => reload(actor)}>
          <RefreshCw className="size-3.5" /> Reload from DB
        </Button>
      </div>

      {groups.map((group) => {
        const items = settings.filter((s) => s.group === group);
        if (items.length === 0) return null;
        return (
          <section
            key={group}
            className="space-y-3 rounded-xl border border-border/60 p-4"
          >
            <h4 className="text-sm font-medium">{group}</h4>
            <div className="space-y-3">
              {items.map((s) => (
                <SettingRow
                  key={s.key}
                  setting={s}
                  value={valueOf(s)}
                  locked={s.premium && !isPremium}
                  onChange={(v) => setValue(s.key, v)}
                />
              ))}
            </div>
          </section>
        );
      })}

      <Alert>
        <Info className="size-4" />
        <AlertTitle>Premium-only settings</AlertTitle>
        <AlertDescription>
          Snapshot windows, decision lookback and per-event email toggles are
          premium. Acting as{" "}
          <span className="font-mono text-xs">{actor}</span> (premium). Standard
          accounts see these locked.
        </AlertDescription>
      </Alert>

      <div className="flex items-center gap-3">
        <Button size="sm" onClick={onSave} disabled={saving || dirtyKeys.length === 0}>
          <Save className="size-3.5" />
          {saving ? "Saving…" : `Save changes${dirtyKeys.length ? ` (${dirtyKeys.length})` : ""}`}
        </Button>
        {dirtyKeys.length > 0 && (
          <Button size="sm" variant="ghost" onClick={() => setDraft({})}>
            Discard
          </Button>
        )}
      </div>

      {/* Notification log */}
      <section className="space-y-3 rounded-xl border border-border/60 p-4">
        <div className="flex items-center justify-between">
          <h4 className="text-sm font-medium">Recent notification emails</h4>
          <span className="font-mono text-[10px] text-muted-foreground">
            {notifs.length} row(s)
          </span>
        </div>
        {notifs.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            No emails sent yet. Add an SMTP app password to enable real delivery
            (currently dry-run).
          </p>
        ) : (
          <div className="overflow-hidden rounded-lg border border-border/60">
            <table className="w-full text-xs">
              <thead className="bg-muted/40 text-[10px] uppercase text-muted-foreground">
                <tr>
                  <th className="px-2 py-1.5 text-left">Kind</th>
                  <th className="px-2 py-1.5 text-left">Subject</th>
                  <th className="px-2 py-1.5 text-left">Status</th>
                  <th className="px-2 py-1.5 text-left">Time</th>
                </tr>
              </thead>
              <tbody>
                {notifs.map((n) => (
                  <tr key={n.id} className="border-t border-border/60">
                    <td className="px-2 py-1.5 font-mono text-[10px]">{n.kind}</td>
                    <td className="max-w-[220px] truncate px-2 py-1.5">
                      {n.subject}
                    </td>
                    <td className="px-2 py-1.5">
                      <NotifStatus status={n.status} />
                    </td>
                    <td className="px-2 py-1.5 font-mono text-[10px] text-muted-foreground">
                      {new Date(n.created_at).toLocaleTimeString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Audit trail */}
      {audit.length > 0 && (
        <section className="space-y-3 rounded-xl border border-border/60 p-4">
          <h4 className="text-sm font-medium">Change history</h4>
          <ul className="space-y-1.5">
            {audit.slice(0, 8).map((a) => (
              <li
                key={a.id}
                className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground"
              >
                <span className="font-mono text-[10px]">{a.key}</span>
                <span className="font-mono">
                  {JSON.stringify(a.old_value)} → {JSON.stringify(a.new_value)}
                </span>
                <span className="ml-auto">{a.actor}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function SettingRow({
  setting,
  value,
  locked,
  onChange,
}: {
  setting: ApiEngineSetting;
  value: number | boolean | string;
  locked: boolean;
  onChange: (v: number | boolean | string) => void;
}) {
  return (
    <div className="flex items-start justify-between gap-4 rounded-lg border border-border/60 p-3">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <Label htmlFor={setting.key} className={locked ? "text-muted-foreground" : ""}>
            {setting.label}
          </Label>
          {setting.premium && (
            <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/10 px-2 py-0.5 text-[10px] font-medium text-amber-600">
              {locked && <Lock className="size-2.5" />}
              Premium
            </span>
          )}
          {!setting.live && (
            <span className="inline-flex items-center gap-1 rounded-full bg-blue-500/10 px-2 py-0.5 text-[10px] font-medium text-blue-600">
              <RotateCw className="size-2.5" />
              Restart
            </span>
          )}
          {setting.source === "db" && (
            <span className="rounded-full bg-green-500/10 px-2 py-0.5 text-[10px] font-medium text-green-600">
              saved
            </span>
          )}
        </div>
        <p className="mt-0.5 text-xs text-muted-foreground">{setting.help}</p>
        <p className="mt-0.5 font-mono text-[10px] text-muted-foreground/70">
          {setting.key}
          {setting.min != null && setting.max != null
            ? ` · ${setting.min}–${setting.max}`
            : ""}
        </p>
      </div>

      <div className="w-40 shrink-0">
        {setting.type === "bool" ? (
          <div className="flex justify-end">
            <Switch
              id={setting.key}
              checked={Boolean(value)}
              disabled={locked}
              onCheckedChange={(v: boolean) => onChange(v)}
            />
          </div>
        ) : (
          <Input
            id={setting.key}
            type={setting.type === "int" ? "number" : "text"}
            value={String(value)}
            min={setting.min ?? undefined}
            max={setting.max ?? undefined}
            disabled={locked}
            onChange={(e) =>
              onChange(
                setting.type === "int"
                  ? Number(e.target.value)
                  : e.target.value,
              )
            }
            className="text-right font-mono text-xs"
          />
        )}
      </div>
    </div>
  );
}

function NotifStatus({ status }: { status: string }) {
  const map: Record<string, string> = {
    SENT: "bg-green-500/15 text-green-600",
    SKIPPED: "bg-zinc-500/15 text-zinc-600",
    FAILED: "bg-red-500/15 text-red-600",
    PENDING: "bg-yellow-500/15 text-yellow-600",
  };
  return (
    <span
      className={`rounded-full px-2 py-0.5 font-mono text-[10px] font-medium uppercase ${
        map[status] ?? ""
      }`}
    >
      {status}
    </span>
  );
}
