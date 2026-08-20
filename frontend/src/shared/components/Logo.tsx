import { cn } from "@/lib/utils";

/**
 * Hand-authored as line segments rather than rendered from a font, so the
 * mark is pixel-identical across every OS instead of depending on whatever
 * --font-sans resolves to locally. Letterforms are original (straight
 * strokes, sharp corners) -- the Oracle reference informed the proportions
 * (wide, geometric, uniform stroke, tight tracking), not the glyphs.
 */
type Point = readonly [number, number];
type Letter = readonly Point[][];

const CELL = 64;
const GAP = 16;
const STROKE = 9;

const LETTERS: Record<string, Letter> = {
  S: [[[58, 10], [6, 10], [6, 45], [58, 45], [58, 80], [6, 80]]],
  H: [[[6, 10], [6, 80]], [[58, 10], [58, 80]], [[6, 45], [58, 45]]],
  A: [[[6, 80], [32, 10], [58, 80]], [[17, 50], [47, 50]]],
  R: [[[6, 80], [6, 10], [58, 10], [58, 45], [6, 45], [58, 80]]],
  P: [[[6, 80], [6, 10], [58, 10], [58, 45], [6, 45]]],
};

const WORD = ["S", "H", "A", "R", "P"];

function Wordmark({ className }: { className?: string }) {
  const totalWidth = WORD.length * CELL + (WORD.length - 1) * GAP;

  return (
    <svg
      viewBox={`-6 -6 ${totalWidth + 12} 102`}
      className={className}
      role="img"
      aria-label="SHARP"
      fill="none"
      stroke="currentColor"
      strokeWidth={STROKE}
      strokeLinecap="square"
      strokeLinejoin="miter"
    >
      {WORD.map((letter, i) => (
        <g key={i} transform={`translate(${i * (CELL + GAP)}, 0)`}>
          {LETTERS[letter].map((poly, j) => (
            <polyline key={j} points={poly.map(([x, y]) => `${x},${y}`).join(" ")} />
          ))}
        </g>
      ))}
    </svg>
  );
}

function LogoMark({ className, hidden }: { className?: string; hidden?: boolean }) {
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
const WORDMARK_HEIGHT: Record<"sm" | "md", string> = { sm: "h-3.5", md: "h-4" };

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
      {!badgeOnly && <Wordmark className={cn("w-auto", WORDMARK_HEIGHT[size])} />}
    </span>
  );
}
