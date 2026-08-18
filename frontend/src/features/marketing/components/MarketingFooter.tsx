import { Link } from "react-router-dom";
import { Logo } from "@/shared/components/Logo";
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

export function MarketingFooter() {
  return (
    <footer className="border-t border-white/10">
      <div className="mx-auto max-w-6xl px-6 py-16">
        <div className="grid gap-10 sm:grid-cols-[2fr_1fr_1fr]">
          <div>
            <Logo size="sm" />
            <p className="mt-4 max-w-xs text-sm text-white/50">
              A closed-loop, autonomous reliability system for Kubernetes-hosted microservices.
            </p>
          </div>

          <div>
            <p className="text-xs font-medium tracking-widest text-white/40 uppercase">Platform</p>
            <ul className="mt-4 space-y-2.5">
              {PLATFORM_LINKS.map((link) => (
                <li key={link.href}>
                  <a href={link.href} className="text-sm text-white/60 transition-colors hover:text-white">
                    {link.label}
                  </a>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <p className="text-xs font-medium tracking-widest text-white/40 uppercase">Account</p>
            <ul className="mt-4 space-y-2.5">
              {ACCOUNT_LINKS.map((link) => (
                <li key={link.to}>
                  <Link to={link.to} className="text-sm text-white/60 transition-colors hover:text-white">
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="mt-14 flex flex-col items-center justify-between gap-3 border-t border-white/10 pt-6 sm:flex-row">
          <p className="text-xs text-white/40">
            {REPO_NAME} &bull; {ORG_NAME}
          </p>
          <p className="text-xs text-white/30">Final year research project. Not a commercial product.</p>
        </div>
      </div>
    </footer>
  );
}
