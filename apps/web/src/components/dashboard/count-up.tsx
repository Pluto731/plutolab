"use client";

import { animate, useMotionValue } from "framer-motion";
import { useEffect, useState } from "react";

interface CountUpProps {
  value: number;
  duration?: number;
  format?: (n: number) => string;
  className?: string;
}

export function CountUp({
  value,
  duration = 1.4,
  format = (n) => Math.round(n).toLocaleString(),
  className,
}: CountUpProps) {
  const mv = useMotionValue(0);
  const [display, setDisplay] = useState(format(0));

  useEffect(() => {
    const unsub = mv.on("change", (v) => setDisplay(format(v)));
    const controls = animate(mv, value, { duration, ease: [0.16, 1, 0.3, 1] });
    return () => {
      unsub();
      controls.stop();
    };
  }, [value, duration, format, mv]);

  return <span className={className}>{display}</span>;
}
