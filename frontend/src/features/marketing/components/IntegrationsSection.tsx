import { Link } from "react-router-dom";
import { INTEGRATION_ITEMS } from "../data/marketingContent";
import { Reveal } from "./Reveal";

export function IntegrationsSection() {
  return (
    <section className="mx-auto max-w-6xl px-6 py-24">
      <Reveal>
        <div className="flex flex-col items-center text-center">
          <span className="rounded-full border border-white/15 bg-white/[0.04] px-4 py-1.5 text-xs text-white/60">
            Integrations
          </span>
          <h2 className="mt-5 max-w-xl text-3xl font-semibold tracking-tight text-white sm:text-4xl">
            Talks to the tools already running in your cluster
          </h2>
          <p className="mt-4 max-w-lg text-sm leading-relaxed text-white/60">
            No new agents to install and no proprietary protocol. SHARP reads and writes through
            APIs your platform team already trusts.
          </p>
          <Link
            to="/settings"
            className="mt-6 rounded-full border border-white/20 px-5 py-2 text-sm font-medium text-white/80 transition-colors hover:bg-white/5 hover:text-white"
          >
            View integration settings
          </Link>
        </div>
      </Reveal>

      <div className="mt-16 flex flex-wrap items-center justify-center gap-3">
        {INTEGRATION_ITEMS.map((item, i) => (
          <Reveal key={item.label} delay={i * 0.05}>
            <div className="rounded-full border border-white/10 bg-white/[0.03] px-4 py-2 font-mono text-xs text-white/60">
              {item.label}
            </div>
          </Reveal>
        ))}
      </div>
    </section>
  );
}
