import { ArrowDown, ArrowUp } from "lucide-react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { StatCardData } from "../types";

export function StatCard({
  label,
  value,
  deltaLabel,
  deltaDirection,
  deltaTone,
}: StatCardData) {
  const Icon = deltaDirection === "up" ? ArrowUp : ArrowDown;

  return (
    <Card className="border-border/60">
      <CardHeader className="pb-0">
        <p className="text-sm text-muted-foreground">{label}</p>
      </CardHeader>
      <CardContent>
        <p className="text-3xl font-semibold tracking-tight">{value}</p>
        {deltaLabel && (
          <p
            className={cn(
              "mt-2 flex items-center gap-1 text-xs font-medium",
              deltaTone === "positive"
                ? "text-status-healthy"
                : deltaTone === "negative"
                  ? "text-status-critical"
                  : "text-muted-foreground",
            )}
          >
            {deltaDirection && <Icon className="size-3.5" />}
            {deltaLabel}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
