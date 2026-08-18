import type { Severity } from "@/shared/types";

const TOKEN_VAR: Record<Severity, string> = {
  watch: "--color-status-watch",
  warn: "--color-status-warn",
  degrade: "--color-status-degrade",
  critical: "--color-status-critical",
};

/** Only used if canvas resolution fails; matches the .dark oklch tokens. */
const FALLBACK_RGB: Record<Severity, string> = {
  watch: "rgb(136, 144, 156)",
  warn: "rgb(73, 169, 255)",
  degrade: "rgb(251, 161, 0)",
  critical: "rgb(253, 57, 63)",
};

let cache: Record<Severity, string> | null = null;

/**
 * Resolves the oklch() severity tokens to concrete rgb() strings three.js's
 * Color can parse -- three.js does not understand oklch(), and
 * getComputedStyle echoes oklch(...) back unchanged in Chromium rather than
 * normalising it (verified against Playwright's bundled Chromium), so
 * getPropertyValue alone is not enough.
 *
 * Instead this reads the token onto a 1x1 canvas: canvas fillStyle accepts
 * oklch, and getImageData always returns concrete 8-bit RGB regardless of
 * the input colour space, which is the general-purpose way to resolve any
 * CSS colour in the browser. Memoised per session since the tokens are
 * static for this dark-only theme.
 */
export function resolveSeverityColors(): Record<Severity, string> {
  if (cache) return cache;

  const root = getComputedStyle(document.documentElement);
  const canvas = document.createElement("canvas");
  canvas.width = 1;
  canvas.height = 1;
  const ctx = canvas.getContext("2d");

  const resolved = {} as Record<Severity, string>;
  for (const severity of Object.keys(TOKEN_VAR) as Severity[]) {
    const raw = root.getPropertyValue(TOKEN_VAR[severity]).trim();
    if (!ctx || !raw) {
      resolved[severity] = FALLBACK_RGB[severity];
      continue;
    }
    try {
      ctx.clearRect(0, 0, 1, 1);
      ctx.fillStyle = raw;
      ctx.fillRect(0, 0, 1, 1);
      const [r, g, b] = ctx.getImageData(0, 0, 1, 1).data;
      resolved[severity] = `rgb(${r}, ${g}, ${b})`;
    } catch {
      resolved[severity] = FALLBACK_RGB[severity];
    }
  }

  cache = resolved;
  return resolved;
}
