import type { Severity } from "@/shared/types";

/**
 * Resolves any CSS colour (including oklch()) to a concrete rgb() string
 * three.js's Color can parse -- three.js does not understand oklch(), and
 * getComputedStyle echoes oklch(...) back unchanged in Chromium rather than
 * normalising it (verified against Playwright's bundled Chromium), so
 * getPropertyValue alone is not enough.
 *
 * Instead this paints the token onto a 1x1 canvas: canvas fillStyle accepts
 * oklch, and getImageData always returns concrete 8-bit RGB regardless of
 * the input colour space, which is the general-purpose way to resolve any
 * CSS colour in the browser.
 */
function resolveCssVarToRgb(varName: string, fallback: string): string {
  const raw = getComputedStyle(document.documentElement).getPropertyValue(varName).trim();
  const canvas = document.createElement("canvas");
  canvas.width = 1;
  canvas.height = 1;
  const ctx = canvas.getContext("2d");
  if (!ctx || !raw) return fallback;

  try {
    ctx.fillStyle = raw;
    ctx.fillRect(0, 0, 1, 1);
    const [r, g, b] = ctx.getImageData(0, 0, 1, 1).data;
    return `rgb(${r}, ${g}, ${b})`;
  } catch {
    return fallback;
  }
}

const SEVERITY_TOKEN_VAR: Record<Severity, string> = {
  watch: "--color-status-watch",
  warn: "--color-status-warn",
  degrade: "--color-status-degrade",
  critical: "--color-status-critical",
};

/** Only used if canvas resolution fails; matches the .dark oklch tokens. */
const SEVERITY_FALLBACK_RGB: Record<Severity, string> = {
  watch: "rgb(136, 144, 156)",
  warn: "rgb(73, 169, 255)",
  degrade: "rgb(251, 161, 0)",
  critical: "rgb(253, 57, 63)",
};

let severityCache: Record<Severity, string> | null = null;

/** Memoised per session since the severity tokens are static for this dark-only theme. */
export function resolveSeverityColors(): Record<Severity, string> {
  if (severityCache) return severityCache;

  const resolved = {} as Record<Severity, string>;
  for (const severity of Object.keys(SEVERITY_TOKEN_VAR) as Severity[]) {
    resolved[severity] = resolveCssVarToRgb(SEVERITY_TOKEN_VAR[severity], SEVERITY_FALLBACK_RGB[severity]);
  }

  severityCache = resolved;
  return resolved;
}

let cardCache: string | null = null;

/** The app's --color-card token, for the 3D canvas's clear colour. */
export function resolveCardColor(): string {
  if (!cardCache) cardCache = resolveCssVarToRgb("--color-card", "rgb(31, 31, 31)");
  return cardCache;
}
