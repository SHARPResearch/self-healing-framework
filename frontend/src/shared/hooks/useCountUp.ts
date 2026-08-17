import { useEffect, useRef, useState } from "react";
import { useInView } from "framer-motion";

interface UseCountUpOptions {
  /** Final value to count to. */
  to: number;
  /** Decimal places to render. */
  decimals?: number;
  /** Animation duration in ms. */
  duration?: number;
  /** Delay before starting, in ms. */
  delay?: number;
}

function easeOutCubic(t: number): number {
  return 1 - Math.pow(1 - t, 3);
}

/**
 * Counts up to `to` once the element scrolls into view, then stops. Returns a
 * ref to attach to the element and the formatted current value.
 *
 * Respects prefers-reduced-motion by jumping straight to the final value.
 */
export function useCountUp({ to, decimals = 0, duration = 1500, delay = 0 }: UseCountUpOptions) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, amount: 0.25 });
  const [value, setValue] = useState(0);

  useEffect(() => {
    if (!inView) return;

    const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (prefersReduced) {
      setValue(to);
      return;
    }

    let frame = 0;
    let start: number | null = null;

    const timeout = window.setTimeout(() => {
      const step = (now: number) => {
        if (start === null) start = now;
        const elapsed = now - start;
        const progress = Math.min(elapsed / duration, 1);
        setValue(to * easeOutCubic(progress));
        if (progress < 1) frame = requestAnimationFrame(step);
      };
      frame = requestAnimationFrame(step);
    }, delay);

    return () => {
      window.clearTimeout(timeout);
      cancelAnimationFrame(frame);
    };
  }, [inView, to, duration, delay]);

  const display = value.toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });

  return { ref, display };
}
