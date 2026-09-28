import { cn } from "@/lib/utils";

/**
 * Rendered from --font-sans (Inter) rather than hand-drawn -- an earlier
 * version was hand-authored SVG polylines to stay pixel-identical across
 * OSes back when --font-sans was a system-stack placeholder, but that made
 * the wordmark read as technical/schematic line art instead of a clean
 * typographic mark. Now that Inter is loaded everywhere, a real font with
 * tight tracking and a heavier weight (Supabase's logotype was the
 * reference point) reads as a much more legible, less "wireframe" brand
 * mark, and it renders consistently since Inter itself is loaded globally.
 */
export function Wordmark({ className }: { className?: string }) {
  return (
    <span className={cn("font-sans leading-none font-semibold tracking-tight", className)}>
      SHARP
    </span>
  );
}

/** Exported alongside `Wordmark` for the marketing footer's oversized brand
 *  row, which composes its own badge wrapper at a size bigger than
 *  BADGE_SIZE's sm/md presets support. */
export function LogoMark({ className, hidden }: { className?: string; hidden?: boolean }) {
  return (
    <svg
      viewBox="0 0 32 32"
      className={className}
      role={hidden ? undefined : "img"}
      aria-hidden={hidden || undefined}
      aria-label={hidden ? undefined : "SHARP"}
      fill="none"
      stroke="var(--color-brand-primary)"
      strokeWidth={3}
      strokeLinecap="square"
      strokeLinejoin="miter"
    >
      <path d="M6 22L16 8L26 22" />
      <path d="M9 26H23" />
    </svg>
  );
}

const BADGE_SIZE: Record<"sm" | "md", string> = { sm: "size-7", md: "size-8" };
const WORDMARK_TEXT: Record<"sm" | "md", string> = { sm: "text-base", md: "text-lg" };

interface LogoProps {
  /** "mark" for the collapsed sidebar; "full" (icon + wordmark) everywhere else. */
  variant?: "full" | "mark";
  size?: "sm" | "md";
  className?: string;
}

/**
 * The single source of truth for the brand mark, replacing five separate
 * <img src="/favicon.svg"> call sites that each re-implemented the badge
 * wrapper with inconsistent backgrounds. Badge is bg-brand-badge everywhere
 * (the same dark navy as favicon.svg's hardcoded fill), so the browser tab
 * icon and every in-app instance of the mark read as the same badge.
 */
export function Logo({ variant = "full", size = "md", className }: LogoProps) {
  const badgeOnly = variant === "mark";

  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      <span
        className={cn(
          "flex shrink-0 items-center justify-center rounded-md bg-brand-badge p-1.5",
          BADGE_SIZE[size],
        )}
      >
        <LogoMark className="size-full" hidden={!badgeOnly} />
      </span>
      {/* No colour class here on purpose: currentColor inherits from the
          ancestor's text colour, which is already white on the marketing
          page and foreground everywhere else (body sets text-foreground). */}
      {!badgeOnly && <Wordmark className={WORDMARK_TEXT[size]} />}
    </span>
  );
}
