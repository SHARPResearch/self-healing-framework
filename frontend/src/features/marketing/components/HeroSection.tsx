import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { motion, useReducedMotion } from "framer-motion";
import { StatsRow } from "./StatsRow";
import Beams from "./Beams";

export function HeroSection() {
  const reduced = useReducedMotion();

  return (
    <section className="relative flex flex-col items-center overflow-hidden bg-background px-6 pt-36 pb-20">
      {!reduced && (
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-x-0 top-0 z-0 h-[700px] [mask-image:linear-gradient(to_bottom,black,black_55%,transparent)] [-webkit-mask-image:linear-gradient(to_bottom,black,black_55%,transparent)]"
        >
          <Beams
            beamWidth={3}
            beamHeight={30}
            beamNumber={20}
            lightColor="#50C878"
            speed={2}
            noiseIntensity={1.75}
            scale={0.2}
            rotation={30}
          />
        </div>
      )}

      <div className="relative z-10 mx-auto flex w-full max-w-3xl flex-col items-center text-center">
        {/* <motion.div
          initial={reduced ? false : { opacity: 0, y: 10 }}
          animate={reduced ? undefined : { opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="mb-6 inline-flex items-center gap-2 rounded-full border border-foreground/15 bg-foreground/[0.04] px-4 py-1.5 text-xs text-foreground/60 backdrop-blur-sm"
        >
          <span className="size-1.5 rounded-full bg-brand-primary" />
          Component 1 complete &bull; benchmarked on SMD and NAB
        </motion.div> */}

        <motion.h1
          initial={reduced ? false : { opacity: 0, y: 14 }}
          animate={reduced ? undefined : { opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.1, ease: [0.22, 1, 0.36, 1] }}
          className="bg-gradient-to-b from-foreground to-foreground/70 bg-clip-text text-4xl leading-[1.08] font-medium tracking-hero text-transparent sm:text-5xl lg:text-6xl"
        >
          The self-healing platform
          <br />
          built for Kubernetes microservices
        </motion.h1>

        <motion.p
          initial={reduced ? false : { opacity: 0, y: 14 }}
          animate={reduced ? undefined : { opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.22, ease: [0.22, 1, 0.36, 1] }}
          className="mt-6 max-w-xl text-sm leading-relaxed text-foreground/60 sm:text-base"
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
            className="inline-flex items-center gap-2 rounded-brand-sm bg-brand-primary px-6 py-2.5 text-sm font-semibold text-brand-on-primary transition-transform hover:-translate-y-0.5 hover:scale-[1.02]"
          >
            Explore the dashboard
            <ArrowRight className="size-4" />
          </Link>
          <Link
            to="/signup"
            className="rounded-brand-sm border border-foreground/20 px-6 py-2.5 text-sm font-medium text-foreground/80 transition-colors hover:bg-foreground/5 hover:text-foreground"
          >
            Get started
          </Link>
        </motion.div>
      </div>

      <motion.div
        initial={reduced ? false : { opacity: 0, y: 40 }}
        animate={reduced ? undefined : { opacity: 1, y: 0 }}
        transition={{ duration: 0.8, delay: 0.45, ease: [0.22, 1, 0.36, 1] }}
        className="relative z-10 mx-auto mt-16 w-full max-w-5xl"
      >
        <div className="overflow-hidden rounded-brand-lg border border-foreground/10 bg-foreground/[0.02] shadow-2xl">
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

      <div className="relative z-10 mt-16">
        <StatsRow />
      </div>
    </section>
  );
}
