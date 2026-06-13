"use client";

import { motion } from "framer-motion";
import { FileText, MessageSquare, Sparkles, Upload } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

interface HeroCardProps {
  name: string | null; // null = 未登录
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
  // 多句话轮播, 给个性, 不死板
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
    <div className="group relative h-full overflow-hidden rounded-3xl">
      {/* 渐变 mesh 背景 — 紫粉品牌色 */}
      <div className="absolute inset-0 bg-gradient-to-br from-violet-600 via-fuchsia-500 to-pink-500" />
      <div className="pointer-events-none absolute -right-12 -top-16 size-72 rounded-full bg-white/15 blur-3xl" />
      <div className="pointer-events-none absolute -bottom-20 -left-12 size-80 rounded-full bg-violet-300/20 blur-3xl" />

      {/* 装饰: 浮动 sparkle 圆点 (微动, 不打扰阅读) */}
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
            className="inline-flex items-center gap-1.5 rounded-xl bg-white/95 px-4 py-2 text-sm font-semibold text-violet-700 shadow-sm transition-all hover:scale-[1.03] hover:bg-white"
          >
            <MessageSquare className="size-4" /> 开始对话
          </Link>
          <Link
            href="/notes"
            className="inline-flex items-center gap-1.5 rounded-xl bg-white/15 px-4 py-2 text-sm font-semibold text-white backdrop-blur-md transition-all hover:scale-[1.03] hover:bg-white/25"
          >
            <FileText className="size-4" /> 新建笔记
          </Link>
          <Link
            href="/rag"
            className="inline-flex items-center gap-1.5 rounded-xl bg-white/15 px-4 py-2 text-sm font-semibold text-white backdrop-blur-md transition-all hover:scale-[1.03] hover:bg-white/25"
          >
            <Upload className="size-4" /> 上传文档
          </Link>
        </div>

        {/* 右下 Sparkles 装饰 */}
        <Sparkles
          aria-hidden
          className="pointer-events-none absolute bottom-7 right-7 size-6 text-white/40"
        />
      </div>
    </div>
  );
}
