import { useState } from "react";
import { BellOff } from "lucide-react";
import { AppShell } from "@/shared/layout/AppShell";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useNotificationStore, selectUnreadCount } from "@/shared/store/notificationStore";
import { NotificationRow } from "./components/NotificationRow";
import { KIND_LABEL } from "./components/notificationMeta";
import type { NotificationKind } from "./types";

type Filter = "all" | "unread" | NotificationKind;

const FILTERS: { value: Filter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "unread", label: "Unread" },
  ...(Object.keys(KIND_LABEL) as NotificationKind[]).map((k) => ({
    value: k as Filter,
    label: KIND_LABEL[k],
  })),
];

export function NotificationsPage() {
  const notifications = useNotificationStore((s) => s.notifications);
  const markRead = useNotificationStore((s) => s.markRead);
  const markAllRead = useNotificationStore((s) => s.markAllRead);
  const unread = useNotificationStore(selectUnreadCount);
  const [filter, setFilter] = useState<Filter>("all");

  const visible = notifications.filter((n) => {
    if (filter === "all") return true;
    if (filter === "unread") return !n.read;
    return n.kind === filter;
  });

  return (
    <AppShell pageTitle="Notifications">
      <div className="space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold">Notifications</h2>
            <p className="text-sm text-muted-foreground">
              {unread > 0 ? `${unread} unread of ${notifications.length}` : "All caught up"}
            </p>
          </div>
          {unread > 0 && (
            <Button variant="outline" size="sm" onClick={markAllRead}>
              Mark all read
            </Button>
          )}
        </div>

        <div className="flex flex-wrap gap-2">
          {FILTERS.map((f) => (
            <button
              key={f.value}
              type="button"
              onClick={() => setFilter(f.value)}
              aria-pressed={filter === f.value}
              className={cn(
                "rounded-full border px-3 py-1 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                filter === f.value
                  ? "border-transparent bg-primary text-primary-foreground"
                  : "border-border/60 text-muted-foreground hover:bg-accent hover:text-accent-foreground",
              )}
            >
              {f.label}
            </button>
          ))}
        </div>

        {visible.length === 0 ? (
          <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed border-border py-16 text-center">
            <BellOff className="size-6 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">Nothing here for this filter</p>
          </div>
        ) : (
          <div className="space-y-2">
            {visible.map((n) => (
              <NotificationRow key={n.id} notification={n} onSelect={markRead} />
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
