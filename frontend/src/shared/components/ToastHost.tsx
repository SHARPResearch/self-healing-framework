import { CheckCircle2, XCircle, Info, X } from "lucide-react";
import { useToastStore } from "@/shared/store/toastStore";

export function ToastHost() {
  const toasts = useToastStore((s) => s.toasts);
  const dismiss = useToastStore((s) => s.dismiss);

  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-[60] flex w-80 flex-col gap-2">
      {toasts.map((t) => {
        const Icon =
          t.variant === "success" ? CheckCircle2 : t.variant === "error" ? XCircle : Info;
        const color =
          t.variant === "success"
            ? "text-green-600"
            : t.variant === "error"
              ? "text-red-600"
              : "text-blue-600";
        return (
          <div
            key={t.id}
            className="flex items-start gap-2 rounded-lg border border-border bg-background p-3 shadow-lg"
            role="status"
          >
            <Icon className={`mt-0.5 size-4 shrink-0 ${color}`} />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium">{t.title}</p>
              {t.description && (
                <p className="mt-0.5 text-xs text-muted-foreground">{t.description}</p>
              )}
            </div>
            <button
              onClick={() => dismiss(t.id)}
              aria-label="Dismiss"
              className="rounded-md p-0.5 text-muted-foreground hover:bg-accent"
            >
              <X className="size-3.5" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
