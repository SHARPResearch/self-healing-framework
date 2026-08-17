import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { Reveal } from "./Reveal";

export function MarketingFooter() {
  return (
    <footer className="border-t border-white/10">
      <div className="mx-auto max-w-6xl px-6 py-20">
        <Reveal>
          <div className="flex flex-col items-center gap-6 text-center">
            <h2 className="max-w-2xl font-display text-3xl leading-tight tracking-tight text-white sm:text-4xl">
              See it running
            </h2>
            <p className="max-w-lg text-sm leading-relaxed text-white/60">
              The dashboard runs on mock telemetry, so you can explore every screen without a
              cluster attached.
            </p>
            <Link
              to="/dashboard"
              className="inline-flex items-center gap-2 rounded-full bg-white px-7 py-3 text-sm font-semibold text-black transition-transform hover:-translate-y-0.5 hover:scale-[1.02]"
            >
              Open the dashboard
              <ArrowRight className="size-4" />
            </Link>
          </div>
        </Reveal>

        <div className="mt-16 flex flex-col items-center justify-between gap-4 border-t border-white/10 pt-8 sm:flex-row">
          <div className="flex items-center gap-2">
            <div className="flex size-7 items-center justify-center rounded-full bg-white">
              <img src="/favicon.svg" alt="" className="size-4" />
            </div>
            <span className="text-sm font-semibold text-white">SHARP</span>
          </div>

          <nav className="flex flex-wrap items-center justify-center gap-5 text-xs text-white/50">
            <a href="#how-it-works" className="transition-colors hover:text-white">
              How it works
            </a>
            <a href="#ladder" className="transition-colors hover:text-white">
              Remediation
            </a>
            <a href="#research" className="transition-colors hover:text-white">
              Research
            </a>
            <Link to="/login" className="transition-colors hover:text-white">
              Sign in
            </Link>
          </nav>

          <p className="text-xs text-white/40">
            self-healing-framework &bull; SHARPResearch
          </p>
        </div>
      </div>
    </footer>
  );
}
