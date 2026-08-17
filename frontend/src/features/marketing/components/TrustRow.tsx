import { motion, useReducedMotion } from "framer-motion";

/**
 * The reference design puts enterprise customer logos here. This is a research
 * project with no customers, so it shows what SHARP is actually validated
 * against instead of inventing logos.
 */
const MARKS = ["SMD", "NAB", "K8s"];

export function TrustRow() {
  const reduced = useReducedMotion();

  return (
    <motion.div
      initial={reduced ? false : { opacity: 0, y: 10 }}
      animate={reduced ? undefined : { opacity: 1, y: 0 }}
      transition={{ duration: 0.6, delay: 0.05 }}
      className="mb-8 inline-flex items-center"
    >
      <div className="flex items-center">
        {MARKS.map((mark, i) => (
          <div
            key={mark}
            style={{ marginLeft: i === 0 ? 0 : "-0.42rem", zIndex: i + 1 }}
            className="flex size-10 items-center justify-center rounded-full border border-white/40 bg-[#28282a] p-[5px]"
          >
            <span className="flex size-full items-center justify-center rounded-full bg-white text-[9px] font-bold text-[#111]">
              {mark}
            </span>
          </div>
        ))}
      </div>
      <div className="-ml-[0.42rem] flex h-10 items-center rounded-full border border-white/40 bg-[#28282a] pr-4 pl-6">
        <span className="text-xs font-medium text-[#c4c2c3]">
          Benchmarked on SMD and NAB, deployed on Kubernetes
        </span>
      </div>
    </motion.div>
  );
}
