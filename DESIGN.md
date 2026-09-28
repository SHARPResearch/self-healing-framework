---
version: alpha
name: SHARP-design-system
description: SHARP's design language, adapted from an analysis of Supabase's marketing site with the canvas polarity inverted — a near-black system instead of white, keeping the same rigor (a single emerald-green accent used sparingly, a tracked humanist sans, square-ish button radii, no atmospheric gradients, real product-UI screenshots as the dominant decorative element) but built for a dark-only app. The brand reads as quietly technical: minimal chrome, a near-monochrome grey ladder, and the green primary acting as the only chromatic event on an otherwise black canvas.

colors:
  primary: "var(--brand-primary)"
  primary-deep: "var(--brand-primary-deep)"
  ink: "var(--foreground)"
  ink-mute: "var(--muted-foreground)"
  on-primary: "var(--brand-on-primary)"
  on-dark: "var(--foreground)"
  canvas: "var(--background)"
  canvas-soft: "var(--card)"
  hairline: "var(--border)"
  status-watch: "var(--status-watch)"
  status-warn: "var(--status-warn)"
  status-degrade: "var(--status-degrade)"
  status-critical: "var(--status-critical)"

typography:
  display-xxl:
    fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif"
    fontSize: 64px
    fontWeight: 500
    lineHeight: 1.1
    letterSpacing: -1.92px
  display-xl:
    fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif"
    fontSize: 48px
    fontWeight: 500
    lineHeight: 1.1
    letterSpacing: -1.44px
  display-lg:
    fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif"
    fontSize: 36px
    fontWeight: 500
    lineHeight: 1.15
    letterSpacing: -0.72px
  heading-md:
    fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif"
    fontSize: 18px
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: 0
  body-lg:
    fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif"
    fontSize: 18px
    fontWeight: 400
    lineHeight: 1.55
    letterSpacing: 0
  body-md:
    fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif"
    fontSize: 16px
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: 0
  button-md:
    fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif"
    fontSize: 14px
    fontWeight: 600
    lineHeight: 1.0
    letterSpacing: 0
  caption:
    fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif"
    fontSize: 13px
    fontWeight: 400
    lineHeight: 1.45
    letterSpacing: 0
  code:
    fontFamily: "ui-monospace, Menlo, Monaco, Consolas, 'Liberation Mono', monospace"
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: 0

rounded:
  xs: 4px
  sm: 6px
  md: 8px
  lg: 12px
  xl: 16px
  full: 9999px

spacing:
  xxs: 2px
  xs: 4px
  sm: 8px
  md: 12px
  lg: 16px
  xl: 24px
  xxl: 32px
  huge: 64px

components:
  button-primary-green:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.button-md}"
    rounded: "{rounded.sm}"
    padding: 8px 16px
  button-secondary-outline:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    typography: "{typography.button-md}"
    rounded: "{rounded.sm}"
    padding: 8px 16px
  button-neutral:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.canvas}"
    typography: "{typography.button-md}"
    rounded: "{rounded.sm}"
    padding: 8px 16px
  card-feature:
    backgroundColor: "{colors.canvas-soft}"
    textColor: "{colors.ink}"
    typography: "{typography.body-md}"
    rounded: "{rounded.lg}"
    padding: 24px
  product-mockup:
    backgroundColor: "{colors.canvas-soft}"
    rounded: "{rounded.lg}"
    padding: 0px
  pill-tag-green:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.caption}"
    rounded: "{rounded.full}"
    padding: 2px 8px
  pill-tag-neutral:
    backgroundColor: "{colors.canvas-soft}"
    textColor: "{colors.ink-mute}"
    typography: "{typography.caption}"
    rounded: "{rounded.full}"
    padding: 2px 8px
  nav-bar:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    typography: "{typography.body-md}"
    rounded: "{rounded.xs}"
    padding: 16px 24px
---

## Overview

SHARP's design language is inverted from Supabase's in exactly one dimension — canvas polarity —
and identical to it in every other principle. The marketing surfaces sit on `{colors.canvas}`
(near-black), with text rendered in `{colors.ink}` (near-white, never pure white). Across the
entire system the only consistent chromatic event is the **emerald green primary**
(`{colors.primary}`) — used as the filled CTA, the logo mark, and small accent dots. Everything
else is a calibrated grey ladder from near-black chrome to near-white text, with the green
appearing sparingly enough that its rarity is what makes it read.

Typography runs **Inter** at weight 500 for display and 400 for body, with tight negative tracking
on the display tier (`--tracking-hero`/`--tracking-display`) to pull the geometric letterforms
into a denser, more engineered read. There is no atmospheric gradient, no ambient glow, no
full-bleed photography — the same "non-negotiable" commitment Supabase makes to white, SHARP makes
to black.

The product itself appears as real, current screenshots of the actual app (`/marketing/*.png`,
captured with Playwright, never stock images) composited above and inside the marketing page.
These screenshots are the brand's argument, sitting inside `{rounded.lg}` containers with a
level-2 shadow.

**Key characteristics:**
- Single emerald primary (`{colors.primary}`) as the only chromatic event; everything else is
  monochrome grey-on-black.
- Near-black canvas with a grey-ladder hierarchy from `{colors.canvas-soft}` to `{colors.ink}`.
- Inter at weight 500 with negative tracking for the display tier; body stays weight 400.
- Real product screenshots are the dominant decorative element — never illustration, never
  atmospheric gradients or glow blobs.
- Square-ish 6px button radii (`{rounded.sm}`) — never pill-shaped. Pills are reserved for tags
  and badges only.
- Near-black text on the green button fill, not white — the button reads as a "lit" surface with
  dark type, the one deliberate inversion-survivor from the source system.
- `status-watch/warn/degrade/critical` are a **separate semantic system** (service health, per
  root `CLAUDE.md`'s thresholds), not brand color — they are exempt from the sparse-green rule and
  can appear together wherever severity needs to be shown.

## Colors

### Brand & Accent
- **Primary** (`{colors.primary}`): the signature CTA color, aliasing `--status-healthy` by
  reference rather than a duplicated value — same green, different semantic name, since brand
  action color and service-health color are different intents that happen to share a hue.
- **Primary Deep** (`{colors.primary-deep}`): hover/pressed lift of the primary.

### Surface
- **Canvas** (`{colors.canvas}`): default page background, near-black.
- **Canvas Soft** (`{colors.canvas-soft}`): the app's existing card surface, used for alternating
  section bands and card fills.
- **Hairline** (`{colors.hairline}`): 1px borders — already alpha-baked at 10% white, so opacity
  modifiers should be applied to `ink`/`foreground` directly rather than stacked onto hairline
  itself, which would compound rather than override the alpha.

### Text
- **Ink** (`{colors.ink}`): default body text, near-white.
- **Ink Mute** (`{colors.ink-mute}`): secondary/helper text.
- **On Primary** (`{colors.on-primary}`): near-black text on the green button fill.

### Severity (separate system, not brand color)
- `status-watch` / `status-warn` / `status-degrade` / `status-critical`: the app-wide anomaly
  severity ladder. Never conflate these with `{colors.primary}` even where hues are adjacent —
  they answer "how healthy is this service," not "what should I click."

## Typography

### Font Family
Inter, loaded via Google Fonts (weights 400/500/600). No proprietary font dependency.

### Principles
- **Weight 500 for display, 400 for body.** Mid-weight reads as engineered, not decorative — the
  same discipline as the source system, carried over unchanged since it's canvas-independent.
- **Negative tracking on display only** (`tracking-hero` at -0.03em, `tracking-display` at
  -0.02em) — applied to headings, not to buttons/badges/stat numbers, which stay at their existing
  weight and default tracking.
- **Mono for code** — system mono stack, no proprietary mono webfont.

## Layout

- **Spacing**: 8px base unit (2/4/8/12/16/24/32/64px tokens), matching what Tailwind's default
  scale already provides — no new spacing tokens needed.
- **Section padding**: 64–96px on marketing surfaces (`py-24` and up).
- **Container**: marketing content centers in a ~1152px (`max-w-6xl`) container, no edge-bleed.

## Shapes

| Token | Value | Use |
|---|---|---|
| `{rounded.sm}` | 6px | Buttons — the signature radius, square-ish, never pill-shaped |
| `{rounded.lg}` | 12px | Cards, product-screenshot containers |
| `{rounded.xl}` | 16px | Large container chrome (e.g. the closing CTA band) |
| `{rounded.full}` | 9999px | Pills, tags, badges — the one place rounded-full is correct |

These map onto `frontend/src/index.css`'s `--radius-brand-*` scale, kept separate from the
existing `--radius-*` scale that drives shadcn's `Button`/`Card` everywhere else in the app, so
adopting this system on the marketing page doesn't silently reshape already-built pages.

## Components

**`button-primary-green`** — the signature CTA. `bg-brand-primary text-brand-on-primary`,
`rounded-brand-sm`, no shadow/glow — a flat fill, since atmospheric glow effects are exactly what
this system avoids.

**`button-neutral`** — used where a second CTA would otherwise put two green buttons in the same
viewport (e.g. the fixed nav's "Sign up" button, always co-visible with whichever section's own
primary CTA is in view). `bg-foreground text-background`, same shape as the primary.

**`pill-tag-green`** / **`pill-tag-neutral`** — small accent dots and status pills. The only other
places green is allowed: a single accent dot in the hero badge, the per-layer dot in the
architecture diagram, and the logo mark itself.

**`product-mockup`** — real screenshots inside `{rounded.lg}` containers with a level-2 shadow,
no glow behind them. The screenshot's own shadow is sufficient depth cue.

## Do's and Don'ts

### Do
- Reserve `{colors.primary}` for the filled CTA, the logo mark, and small accent dots — it should
  appear once or twice per viewport, not as a background wash.
- Render display headings at weight 500 with negative tracking.
- Use `{rounded.sm}` for buttons — square-ish, never pill-shaped.
- Composite real, current product screenshots inside `{rounded.lg}` containers.
- Keep near-black text on the green button — not white.

### Don't
- Don't add atmospheric gradients, glow blobs, or ambient backgrounds to any section — the black
  canvas is the design, the same way the source system's white canvas was.
- Don't conflate `status-*` severity tokens with `{colors.primary}` — they're allowed to look
  similar in hue but are a different system, and are exempt from the sparse-green rule.
- Don't use pill-shaped buttons — reserve `rounded.full` for tags and badges.
- Don't bump display weight above 500, or drop body below 400.

## Iteration Guide

1. Focus on one component at a time.
2. Reference the token names in this document directly (`rounded-brand-sm`, `bg-brand-primary`,
   `tracking-display`) rather than hand-picking arbitrary Tailwind values.
3. Keep the green scarce — one filled button per viewport is the target.
4. This is marketing-first: once the marketing page reads well, the same tokens extend to the
   dashboard and every other page — but that migration is a separate, later pass.
