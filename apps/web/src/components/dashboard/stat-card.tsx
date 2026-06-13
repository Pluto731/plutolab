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
  trend?: string;
  emptyHint?: string;
}

/**
 * 不大众化升级 (借鉴 MagicUI/Aceternity Magic Card + Spotlight):
 *  - 鼠标进卡时, 一团紫色辉光跟随鼠标位置 (radial-gradient at var(--mx, --my))
 *  - 同时卡片边框也有一圈跟鼠标的发光 (内部 .spotlight-border 元素)
 *  - 卡片轻微 3D tilt 跟鼠标 (perspective rotateX/Y)
 *  鼠标离开时全部 0.3s 淡出复位.
 */
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
    const mx = e.clientX - r.left;
    const my = e.clientY - r.top;
    // spotlight 位置 (CSS 变量, 让 .spotlight / .spotlight-border 跟随)
    el.style.setProperty("--mx", `${mx}px`);
    el.style.setProperty("--my", `${my}px`);
    // 3D tilt (±4°, 克制)
    const px = mx / r.width - 0.5;
    const py = my / r.height - 0.5;
    setTilt({ x: -py * 4, y: px * 4 });
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
      {/* Spotlight 边框 — 跟鼠标的内边发光圈 */}
      <div
        aria-hidden
        className="spotlight-border pointer-events-none absolute inset-0 rounded-2xl opacity-0 transition-opacity duration-300 group-hover:opacity-100"
      />

      {/* 卡片主体 — 玻璃质感 */}
      <div className="relative h-full rounded-2xl border border-border bg-card/80 p-5 backdrop-blur-md transition-shadow group-hover:shadow-xl">
        {/* Spotlight 面光 — 跟鼠标的紫色径向辉光, 覆在内容上层 */}
        <div
          aria-hidden
          className="spotlight pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-300 group-hover:opacity-100"
        />

        <div className="relative">
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
    </div>
  );
}
