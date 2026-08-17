import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { motion, useReducedMotion } from "framer-motion";
import { HERO_VIDEO_URL } from "../data/marketingContent";
import { TrustRow } from "./TrustRow";
import { StatsRow } from "./StatsRow";

export function HeroSection() {
  const reduced = useReducedMotion();
  const [videoFailed, setVideoFailed] = useState(false);

  // `isolate` below is load bearing: it gives the section its own stacking
  // context so the negative z-index video and overlays paint inside it,
  // instead of escaping and landing behind the page root's black background.
  return (
    <section className="relative isolate flex min-h-screen flex-col items-center justify-center overflow-hidden px-6 pt-28 pb-16">
      {/* Painted first so a dead video URL or a slow buffer degrades to this
          rather than to a black rectangle. */}
      <div aria-hidden="true" className="absolute inset-0 -z-20 bg-black">
        <div className="animate-blob-drift absolute top-1/4 left-1/4 size-[36rem] rounded-full bg-status-healthy/12 blur-[140px]" />
        <div className="animate-blob-drift absolute right-1/4 bottom-1/4 size-[32rem] rounded-full bg-status-warn/12 blur-[140px]" />
      </div>

      {!videoFailed && !reduced && (
        <video
          className="pointer-events-none absolute inset-0 -z-10 size-full object-cover"
          autoPlay
          muted
          loop
          playsInline
          preload="metadata"
          aria-hidden="true"
          onError={() => setVideoFailed(true)}
        >
          <source src={HERO_VIDEO_URL} type="video/mp4" />
        </video>
      )}

      {/* Vignette rather than a flat wash: dark at the edges so the nav and the
          stat row stay legible, but light enough through the middle that the
          video is actually visible behind the headline. */}
      <div
        aria-hidden="true"
        className="absolute inset-0 -z-10 bg-gradient-to-b from-black/75 via-black/35 to-black"
      />
      <div
        aria-hidden="true"
        className="absolute inset-0 -z-10 bg-[radial-gradient(ellipse_at_center,transparent_25%,rgba(0,0,0,0.65)_100%)]"
      />

      <div className="relative mx-auto flex w-full max-w-4xl flex-col items-center text-center">
        <TrustRow />

        <motion.h1
          initial={reduced ? false : { opacity: 0, y: 14 }}
          animate={reduced ? undefined : { opacity: 1, y: 0 }}
          transition={{ duration: 0.85, delay: 0.12, ease: [0.22, 1, 0.36, 1] }}
          className="font-display text-4xl leading-tight tracking-tight text-white sm:text-5xl lg:text-6xl"
        >
          <span className="block">Intelligence</span>
          <span className="block">Designed To Evolve</span>
        </motion.h1>

        <motion.p
          initial={reduced ? false : { opacity: 0, y: 14 }}
          animate={reduced ? undefined : { opacity: 1, y: 0 }}
          transition={{ duration: 0.85, delay: 0.28, ease: [0.22, 1, 0.36, 1] }}
          className="mt-6 max-w-xl text-sm leading-relaxed text-white/70 sm:text-base"
        >
          SHARP predicts failures in Kubernetes microservices before they page anyone, then fixes
          them itself. Online learning on every metric scrape, graduated remediation through the
          Kubernetes API.
        </motion.p>

        <motion.div
          initial={reduced ? false : { opacity: 0, y: 14 }}
          animate={reduced ? undefined : { opacity: 1, y: 0 }}
          transition={{ duration: 0.85, delay: 0.4, ease: [0.22, 1, 0.36, 1] }}
          className="mt-9 flex flex-wrap items-center justify-center gap-3"
        >
          <Link
            to="/dashboard"
            className="inline-flex items-center gap-2 rounded-full bg-white px-7 py-3 text-sm font-semibold text-black shadow-[0_0_0_1px_rgba(255,255,255,0.15),0_0_22px_rgba(255,255,255,0.32),0_0_44px_rgba(255,255,255,0.12)] transition-transform hover:-translate-y-0.5 hover:scale-[1.02]"
          >
            Explore the dashboard
            <ArrowRight className="size-4" />
          </Link>
          <a
            href="#how-it-works"
            className="rounded-full border border-white/20 px-7 py-3 text-sm font-medium text-white/80 transition-colors hover:bg-white/5 hover:text-white"
          >
            See how it works
          </a>
        </motion.div>

        <StatsRow />
      </div>
    </section>
  );
}
