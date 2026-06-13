"use client";

import { motion } from "framer-motion";
import type { LucideIcon } from "lucide-react";
import { useRef, useState } from "react";

import { CountUp } from "./count-up";

interface StatCardProps {
  icon: LucideIcon;
  iconGradient: string; // tailwind classes 拼出渐变, 如 "from-violet-500 to-fuchsia-500"
  label: string;
  value: number;
  trend?: string; // "+3 本周"
  emptyHint?: string; // value=0 时显示这段而不是 "0"
}

export function StatCard({
  icon: Icon,
  iconGradient,
  label,
  value,
  trend,
  emptyHint,
}: StatCardProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [tilt, setTilt] = useState({ x: 0, y: 0 });

  const onMove = (e: React.MouseEvent) => {
    const el = ref.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const px = (e.clientX - r.left) / r.width - 0.5;
    const py = (e.clientY - r.top) / r.height - 0.5;
    setTilt({ x: -py * 4, y: px * 4 }); // 倾斜 ±4 度, 克制
  };

  const reset = () => setTilt({ x: 0, y: 0 });

  return (
    <div
      ref={ref}
      onMouseMove={onMove}
      onMouseLeave={reset}
      style={{
        transform: `perspective(900px) rotateX(${tilt.x}deg) rotateY(${tilt.y}deg)`,
        transition: "transform 0.18s ease-out",
        transformStyle: "preserve-3d",
      }}
      className="group relative overflow-hidden rounded-2xl"
    >
      {/* Conic glow border — 仅 hover 时浮现 */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 rounded-2xl opacity-0 transition-opacity duration-300 group-hover:opacity-100"
      >
        <div className="conic-border absolute inset-0 rounded-2xl" />
      </div>

      {/* 卡片主体 — 玻璃质感 */}
      <div className="relative h-full rounded-2xl border border-border bg-card/80 p-5 backdrop-blur-md transition-shadow group-hover:shadow-xl">
        <div
          className={`mb-3 inline-flex size-10 items-center justify-center rounded-xl bg-gradient-to-br ${iconGradient} shadow-md`}
        >
          <Icon className="size-5 text-white" />
        </div>
        <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          {label}
        </p>
        {value === 0 && emptyHint ? (
          <p className="mt-1 text-sm leading-snug text-muted-foreground">{emptyHint}</p>
        ) : (
          <motion.p
            className="mt-1 text-3xl font-bold tabular-nums"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.2 }}
          >
            <CountUp value={value} />
          </motion.p>
        )}
        {trend && value > 0 && (
          <p className="mt-1 text-xs font-medium text-emerald-500">{trend}</p>
        )}
      </div>
    </div>
  );
}
