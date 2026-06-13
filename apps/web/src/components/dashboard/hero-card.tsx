"use client";

import { motion } from "framer-motion";
import { FileText, MessageSquare, Sparkles, Upload } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

interface HeroCardProps {
  name: string | null;
}

const WEEKDAYS = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];

function greet(hours: number): string {
  if (hours < 6) return "夜深了";
  if (hours < 12) return "早上好";
  if (hours < 14) return "中午好";
  if (hours < 18) return "下午好";
  if (hours < 22) return "晚上好";
  return "夜深了";
}

function HeroQuote() {
  const quotes = [
    "今天准备 ship 什么？",
    "把一个想法变成 demo。",
    "在炼丹之前，先把数据洗干净。",
    "Stay weird, build hard.",
  ];
  const [i, setI] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setI((v) => (v + 1) % quotes.length), 4500);
    return () => clearInterval(t);
  }, [quotes.length]);
  return (
    <motion.p
      key={i}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="text-base text-white/85"
    >
      {quotes[i]}
    </motion.p>
  );
}

/**
 * Aurora 极光背景: 多个色块各自不规律漂移 + 缩放 + 旋转, 用 mix-blend-mode 叠加,
 * filter: blur(60px) 让边缘融化. 每个 blob duration 不同, 看起来"不重复".
 * 灵感来源: Aceternity Aurora Background.
 */
function AuroraBackdrop() {
  const blobs = [
    {
      color: "bg-violet-500",
      size: "size-[420px]",
      pos: { top: "-10%", left: "-10%" },
      duration: 18,
      delay: 0,
    },
    {
      color: "bg-fuchsia-400",
      size: "size-[360px]",
      pos: { top: "20%", left: "55%" },
      duration: 22,
      delay: 1.5,
    },
    {
      color: "bg-pink-500",
      size: "size-[300px]",
      pos: { top: "55%", left: "-5%" },
      duration: 15,
      delay: 3,
    },
    {
      color: "bg-indigo-400",
      size: "size-[340px]",
      pos: { top: "60%", left: "60%" },
      duration: 20,
      delay: 0.8,
    },
    {
      color: "bg-rose-400",
      size: "size-[260px]",
      pos: { top: "10%", left: "30%" },
      duration: 14,
      delay: 2.2,
    },
  ];
  return (
    <div aria-hidden className="aurora-canvas pointer-events-none absolute inset-0">
      {blobs.map((b, i) => (
        <motion.div
          key={i}
          className={`absolute ${b.size} ${b.color} rounded-full opacity-70`}
          style={b.pos}
          animate={{
            x: [0, 30, -20, 0],
            y: [0, -25, 20, 0],
            scale: [1, 1.15, 0.9, 1],
          }}
          transition={{
            duration: b.duration,
            delay: b.delay,
            repeat: Infinity,
            ease: "easeInOut",
          }}
        />
      ))}
    </div>
  );
}

export function HeroCard({ name }: HeroCardProps) {
  const [now, setNow] = useState<Date | null>(null);
  useEffect(() => {
    setNow(new Date());
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  const timeStr = now
    ? now.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", hour12: false })
    : "--:--";
  const dateStr = now
    ? `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(
        now.getDate(),
      ).padStart(2, "0")} ${WEEKDAYS[now.getDay()]}`
    : "—";
  const hours = now ? now.getHours() : 8;
  const greeting = greet(hours);

  return (
    <div className="group relative h-full overflow-hidden rounded-3xl bg-zinc-900">
      {/* Aurora 流动背景 — 替代静态 mesh, 多 blob 漂移 morph */}
      <AuroraBackdrop />

      {/* 顶层一层暗罩 + sparkle 装饰 (让文字 contrast 足够) */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-gradient-to-br from-violet-900/30 via-transparent to-pink-900/30"
      />
      <motion.div
        aria-hidden
        className="pointer-events-none absolute right-10 top-8 size-2 rounded-full bg-white/70"
        animate={{ scale: [1, 1.5, 1], opacity: [0.5, 1, 0.5] }}
        transition={{ duration: 2.6, repeat: Infinity }}
      />
      <motion.div
        aria-hidden
        className="pointer-events-none absolute right-20 top-16 size-1.5 rounded-full bg-white/60"
        animate={{ scale: [1, 1.4, 1], opacity: [0.4, 0.9, 0.4] }}
        transition={{ duration: 3.4, repeat: Infinity, delay: 0.6 }}
      />
      <motion.div
        aria-hidden
        className="pointer-events-none absolute left-12 bottom-12 size-1.5 rounded-full bg-white/50"
        animate={{ scale: [1, 1.3, 1], opacity: [0.3, 0.8, 0.3] }}
        transition={{ duration: 3.0, repeat: Infinity, delay: 1.2 }}
      />

      <div className="relative flex h-full flex-col justify-between p-7 text-white">
        <div>
          <p className="mb-1 text-sm font-medium text-white/75">
            {dateStr} · <span className="font-mono tabular-nums">{timeStr}</span>
          </p>
          <h1 className="mb-3 text-3xl font-bold tracking-tight md:text-4xl">
            {greeting}
            {name ? `，${name}` : "，欢迎来到 PlutoLab"} 👋
          </h1>
          <HeroQuote />
        </div>

        <div className="mt-6 flex flex-wrap gap-2">
          <Link
            href="/agents"
            className="shimmer-on-hover inline-flex items-center gap-1.5 rounded-xl bg-white/95 px-4 py-2 text-sm font-semibold text-violet-700 shadow-sm transition-all hover:scale-[1.03] hover:bg-white"
          >
            <MessageSquare className="size-4" /> 开始对话
          </Link>
          <Link
            href="/notes"
            className="shimmer-on-hover inline-flex items-center gap-1.5 rounded-xl bg-white/15 px-4 py-2 text-sm font-semibold text-white backdrop-blur-md transition-all hover:scale-[1.03] hover:bg-white/25"
          >
            <FileText className="size-4" /> 新建笔记
          </Link>
          <Link
            href="/rag"
            className="shimmer-on-hover inline-flex items-center gap-1.5 rounded-xl bg-white/15 px-4 py-2 text-sm font-semibold text-white backdrop-blur-md transition-all hover:scale-[1.03] hover:bg-white/25"
          >
            <Upload className="size-4" /> 上传文档
          </Link>
        </div>

        <Sparkles
          aria-hidden
          className="pointer-events-none absolute bottom-7 right-7 size-6 text-white/40"
        />
      </div>
    </div>
  );
}
