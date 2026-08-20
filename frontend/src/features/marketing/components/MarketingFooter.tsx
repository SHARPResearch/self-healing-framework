import { Link } from "react-router-dom";
import { LogoMark, Wordmark } from "@/shared/components/Logo";
import { ORG_NAME, REPO_NAME } from "@/shared/brand";

const PLATFORM_LINKS = [
  { href: "#how-it-works", label: "How it works" },
  { href: "#remediation", label: "Remediation" },
  { href: "#product", label: "Product" },
  { href: "#research", label: "Research" },
];

const ACCOUNT_LINKS = [
  { to: "/login", label: "Sign in" },
  { to: "/signup", label: "Sign up" },
  { to: "/dashboard", label: "Dashboard" },
];

/**
 * The one real external link -- this repo's actual GitHub remote, not a
 * fabricated social-media presence. SHARP is a research project, not a
 * company with a LinkedIn/X account to point at.
 */
const PROJECT_LINKS = [
  { href: "https://github.com/SHARPResearch/self-healing-framework", label: "GitHub" },
];

const navLinkClass =
  "text-base font-semibold text-foreground/70 transition-[color,transform] duration-150 hover:translate-x-0.5 hover:text-foreground";

/**
 * Adapted from a "Site Footer" reference spec (black-canvas aerospace-brand
 * layout: dotted top strip, big tagline, oversized wordmark row) -- kept the
 * structure, replaced everything content- and color-wise to fit SHARP:
 * dark canvas tokens instead of literal #000/#fff, the real Wordmark/LogoMark
 * instead of a font-rendered brand name, real nav links instead of invented
 * "Careers"/"Investors" pages, and the existing honest disclaimer instead of
 * dead #privacy/#terms anchors this project has no pages behind.
 */
export function MarketingFooter() {
  return (
    <footer className="relative overflow-hidden border-t border-foreground/10 bg-background">
      <div aria-hidden="true" className="relative h-20 overflow-hidden">
        <div className="footer-dots-line animate-footer-dots" />
      </div>

      <div className="mx-auto max-w-6xl px-6 pt-2 pb-16">
        <div className="grid gap-10 lg:grid-cols-[1.5fr_1fr_1fr_1fr]">
          <h2 className="max-w-sm text-2xl leading-[1.15] font-medium tracking-display text-foreground sm:text-3xl">
            The loop closes itself, so your pager doesn&apos;t have to.
          </h2>

          <nav aria-label="Footer navigation">
            <p className="text-xs font-medium tracking-widest text-foreground/40 uppercase">
              Platform
            </p>
            <ul className="mt-4 space-y-3">
              {PLATFORM_LINKS.map((link) => (
                <li key={link.href}>
                  <a href={link.href} className={navLinkClass}>
                    {link.label}
                  </a>
                </li>
              ))}
            </ul>
          </nav>

          <nav aria-label="Account links">
            <p className="text-xs font-medium tracking-widest text-foreground/40 uppercase">
              Account
            </p>
            <ul className="mt-4 space-y-3">
              {ACCOUNT_LINKS.map((link) => (
                <li key={link.to}>
                  <Link to={link.to} className={navLinkClass}>
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>

          <nav aria-label="Project links">
            <p className="text-xs font-medium tracking-widest text-foreground/40 uppercase">
              Project
            </p>
            <ul className="mt-4 space-y-3">
              {PROJECT_LINKS.map((link) => (
                <li key={link.href}>
                  <a href={link.href} target="_blank" rel="noreferrer" className={navLinkClass}>
                    {link.label}
                  </a>
                </li>
              ))}
            </ul>
          </nav>
        </div>

        <div className="mt-14 w-full sm:mt-20">
          <Link to="/" aria-label="SHARP home" className="flex w-full items-center text-foreground">
            <span className="mr-4 flex size-14 shrink-0 items-center justify-center rounded-2xl bg-brand-badge p-3 sm:mr-6 sm:size-20 lg:size-28">
              <LogoMark className="size-full" />
            </span>
            <Wordmark className="h-14 w-auto sm:h-24 lg:h-36" />
          </Link>
        </div>

        <div className="mt-8 flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-foreground/10 pt-6 text-xs text-foreground/40">
          <p className="m-0">
            {REPO_NAME} &bull; {ORG_NAME}
          </p>
          <p className="m-0">Final year research project. Not a commercial product.</p>
        </div>
      </div>
    </footer>
  );
}
