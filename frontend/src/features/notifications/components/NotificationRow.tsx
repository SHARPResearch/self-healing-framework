import { cn } from "@/lib/utils";
import { SeverityBadge } from "@/shared/components/SeverityBadge";
import { KIND_ICON, KIND_LABEL, timeAgo } from "./notificationMeta";
import type { AppNotification } from "../types";

interface NotificationRowProps {
  notification: AppNotification;
  onSelect?: (id: string) => void;
  compact?: boolean;
}

export function NotificationRow({ notification, onSelect, compact = false }: NotificationRowProps) {
  const Icon = KIND_ICON[notification.kind];
  const interactive = Boolean(onSelect);

  return (
    <div
      role={interactive ? "button" : undefined}
      tabIndex={interactive ? 0 : undefined}
      onClick={() => onSelect?.(notification.id)}
      onKeyDown={(e) => {
        if (!interactive) return;
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect?.(notification.id);
        }
      }}
      className={cn(
        "flex gap-3 rounded-lg border border-border/60 p-3 transition-colors",
        !notification.read && "bg-muted/40",
        interactive &&
          "cursor-pointer hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
      )}
    >
      <div className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-md bg-muted">
        <Icon className="size-4 text-muted-foreground" />
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-2">
          <p className={cn("text-sm", !notification.read && "font-medium")}>{notification.title}</p>
          {!notification.read && (
            <span
              className="mt-1.5 size-1.5 shrink-0 rounded-full bg-status-critical"
              aria-label="Unread"
            />
          )}
        </div>

        <p className={cn("mt-0.5 text-xs text-muted-foreground", compact && "line-clamp-2")}>
          {notification.body}
        </p>

        <div className="mt-2 flex flex-wrap items-center gap-2">
          <SeverityBadge severity={notification.severity} />
          <span className="text-[11px] text-muted-foreground">{KIND_LABEL[notification.kind]}</span>
          <span className="text-[11px] text-muted-foreground">&bull;</span>
          <span className="text-[11px] text-muted-foreground">{notification.serviceId}</span>
          <span className="text-[11px] text-muted-foreground">&bull;</span>
          <span className="text-[11px] text-muted-foreground">{timeAgo(notification.timestamp)}</span>
        </div>
      </div>
    </div>
  );
}
