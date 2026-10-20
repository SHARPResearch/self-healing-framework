import { Switch } from "@/components/ui/switch";

interface Props {
  enabled: boolean;
  disabled?: boolean;
  onToggle: (next: boolean) => void | Promise<void>;
}

/** Level 1 — inline enable/disable. One click, immediate save. */
export function EnableToggle({ enabled, disabled, onToggle }: Props) {
  return (
    <Switch
      size="sm"
      checked={enabled}
      disabled={disabled}
      aria-label={enabled ? "Disable rule" : "Enable rule"}
      onCheckedChange={(next) => onToggle(next)}
    />
  );
}
