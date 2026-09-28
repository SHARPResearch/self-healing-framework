import { cn } from "@/lib/utils";

/** Cosmetic only -- nothing enforces this, there is no real signup. */
export function scorePassword(password: string): number {
  if (!password) return 0;
  let score = 0;
  if (password.length >= 8) score += 1;
  if (password.length >= 12) score += 1;
  if (/[a-z]/.test(password) && /[A-Z]/.test(password)) score += 1;
  if (/\d/.test(password)) score += 1;
  if (/[^A-Za-z0-9]/.test(password)) score += 1;
  return Math.min(score, 4);
}

const LABELS = ["Too short", "Weak", "Fair", "Good", "Strong"];
const BAR_CLASS = [
  "bg-muted",
  "bg-status-critical",
  "bg-status-degrade",
  "bg-status-warn",
  "bg-status-healthy",
];

export function PasswordStrength({ password }: { password: string }) {
  const score = scorePassword(password);

  if (!password) return null;

  return (
    <div className="space-y-1.5">
      <div className="flex gap-1" aria-hidden="true">
        {[0, 1, 2, 3].map((i) => (
          <div
            key={i}
            className={cn(
              "h-1 flex-1 rounded-full transition-colors",
              i < score ? BAR_CLASS[score] : "bg-muted",
            )}
          />
        ))}
      </div>
      <p className="text-xs text-muted-foreground" aria-live="polite">
        Password strength: {LABELS[score]}
      </p>
    </div>
  );
}
