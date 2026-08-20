import type { SimpleIcon } from "simple-icons";

/**
 * Renders a simple-icons brand mark in the surrounding text color rather
 * than the icon's own brand hex -- keeps the marquee monochrome/neutral
 * like the rest of SHARP's sparse-color system instead of turning it into
 * a row of competing brand colors.
 */
export function ToolIcon({ icon, className }: { icon: SimpleIcon; className?: string }) {
  return (
    <svg viewBox="0 0 24 24" role="img" aria-hidden="true" fill="currentColor" className={className}>
      <path d={icon.path} />
    </svg>
  );
}
