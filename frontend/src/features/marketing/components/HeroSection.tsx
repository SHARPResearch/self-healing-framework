import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { motion, useReducedMotion } from "framer-motion";
import { StatsRow } from "./StatsRow";

export function HeroSection() {
  const reduced = useReducedMotion();

  // `isolate` gives the section its own stacking context so the
  // negative-z-index ambient blobs paint inside it instead of escaping and
  // landing behind the page root's black background.
  return (
    <section className="relative isolate flex flex-col items-center overflow-hidden px-6 pt-36 pb-20">
      {/* Ambient background built from the app's own severity palette
          (status-healthy green, status-warn blue) instead of a stock video,
          so the hero reads as SHARP's colours rather than a generic template. */}
      <div aria-hidden="true" className="absolute inset-0 -z-20 bg-black">
        <div className="animate-blob-drift absolute top-1/4 left-1/4 size-[36rem] rounded-full bg-status-healthy/14 blur-[140px]" />
        <div className="animate-blob-drift absolute right-1/4 bottom-1/4 size-[32rem] rounded-full bg-status-warn/14 blur-[140px]" />
        <div
          aria-hidden="true"
          className="absolute inset-0 opacity-[0.035]"
          style={{
            backgroundImage:
              "linear-gradient(to right, white 1px, transparent 1px), linear-gradient(to bottom, white 1px, transparent 1px)",
            backgroundSize: "48px 48px",
            maskImage: "radial-gradient(ellipse 60% 50% at 50% 0%, black, transparent)",
          }}
        />
      </div>

      <div className="relative mx-auto flex w-full max-w-3xl flex-col items-center text-center">
        <motion.div
          initial={reduced ? false : { opacity: 0, y: 10 }}
          animate={reduced ? undefined : { opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="mb-6 inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/[0.04] px-4 py-1.5 text-xs text-white/60 backdrop-blur-sm"
        >
          <span className="size-1.5 rounded-full bg-status-healthy" />
          Component 1 complete &bull; benchmarked on SMD and NAB
        </motion.div>

        <motion.h1
          initial={reduced ? false : { opacity: 0, y: 14 }}
          animate={reduced ? undefined : { opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.1, ease: [0.22, 1, 0.36, 1] }}
          className="bg-gradient-to-b from-white to-white/70 bg-clip-text text-4xl leading-[1.08] font-medium tracking-tight text-transparent sm:text-5xl lg:text-6xl"
        >
          The self-healing platform
          <br />
          built for Kubernetes microservices
        </motion.h1>

        <motion.p
          initial={reduced ? false : { opacity: 0, y: 14 }}
          animate={reduced ? undefined : { opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.22, ease: [0.22, 1, 0.36, 1] }}
          className="mt-6 max-w-xl text-sm leading-relaxed text-white/60 sm:text-base"
        >
          SHARP predicts failures before they page anyone, then fixes them itself. Online learning
          on every metric scrape, graduated remediation through the Kubernetes API.
        </motion.p>

        <motion.div
          initial={reduced ? false : { opacity: 0, y: 14 }}
          animate={reduced ? undefined : { opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.34, ease: [0.22, 1, 0.36, 1] }}
          className="mt-8 flex flex-wrap items-center justify-center gap-3"
        >
          <Link
            to="/dashboard"
            className="inline-flex items-center gap-2 rounded-full bg-white px-6 py-2.5 text-sm font-semibold text-black shadow-[0_0_24px_oklch(0.75_0.18_150/35%)] transition-transform hover:-translate-y-0.5 hover:scale-[1.02]"
          >
            Explore the dashboard
            <ArrowRight className="size-4" />
          </Link>
          <Link
            to="/signup"
            className="rounded-full border border-white/20 px-6 py-2.5 text-sm font-medium text-white/80 transition-colors hover:bg-white/5 hover:text-white"
          >
            Get started
          </Link>
        </motion.div>
      </div>

      <motion.div
        initial={reduced ? false : { opacity: 0, y: 40 }}
        animate={reduced ? undefined : { opacity: 1, y: 0 }}
        transition={{ duration: 0.8, delay: 0.45, ease: [0.22, 1, 0.36, 1] }}
        className="relative mx-auto mt-16 w-full max-w-5xl"
      >
        <div
          aria-hidden="true"
          className="absolute inset-x-0 -top-10 -z-10 mx-auto h-40 w-3/4 rounded-full bg-status-healthy/15 blur-[100px]"
        />
        <div className="overflow-hidden rounded-2xl border border-white/10 bg-white/[0.02] shadow-2xl">
          <img
            src="/marketing/dashboard.png"
            alt="SHARP dashboard showing service health tiles, anomaly score trend and the incident feed"
            width={1440}
            height={900}
            loading="eager"
            decoding="async"
            className="w-full"
          />
        </div>
      </motion.div>

      <div className="relative mt-16">
        <StatsRow />
      </div>
    </section>
  );
}
