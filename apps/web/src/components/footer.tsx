"use client";

import { motion } from "framer-motion";
import { Code2, ExternalLink, FileText, Github, Heart } from "lucide-react";
import Link from "next/link";

const stacks = [
  { name: "Next.js 16", color: "from-zinc-700 to-zinc-900" },
  { name: "React 19", color: "from-cyan-500 to-sky-600" },
  { name: "FastAPI", color: "from-emerald-500 to-teal-600" },
  { name: "PostgreSQL + pgvector", color: "from-blue-500 to-indigo-600" },
  { name: "Tailwind v4", color: "from-sky-400 to-blue-600" },
  { name: "Framer Motion", color: "from-pink-500 to-rose-500" },
  { name: "Claude", color: "from-orange-500 to-amber-500" },
  { name: "Docker", color: "from-sky-500 to-blue-700" },
];

const links = [
  {
    name: "GitHub",
    icon: Github,
    href: "https://github.com/Pluto731/plutolab",
    external: true,
  },
  { name: "Swagger", icon: FileText, href: "/docs", external: true },
  { name: "Health", icon: Code2, href: "/api/v1/health", external: true },
];

export function Footer() {
  return (
    <motion.footer
      initial={{ opacity: 0, y: 30 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-100px" }}
      transition={{ duration: 0.8 }}
      className="relative px-6 py-16"
    >
      <div className="mx-auto max-w-5xl">
        {/* Footer 卡片 - 苹果毛玻璃, 跟功能卡同一风格 */}
        <div
          className="rounded-3xl border border-white/40 bg-white/20 px-8 py-10 backdrop-blur-2xl
                     shadow-[inset_0_1px_0_0_rgba(255,255,255,0.6),0_20px_50px_-20px_rgba(0,0,0,0.12)]
                     dark:border-white/[0.06] dark:bg-white/[0.02]
                     dark:shadow-[inset_0_1px_0_0_rgba(255,255,255,0.06),0_20px_50px_-20px_rgba(0,0,0,0.5)]"
        >
          {/* 标题区 */}
          <div className="flex flex-col items-center text-center">
            <div className="text-5xl select-none">🪐</div>
            <h3
              className="mt-3 bg-gradient-to-r from-violet-600 via-fuchsia-500 to-pink-500 bg-clip-text text-2xl font-bold text-transparent
                         dark:from-violet-400 dark:via-fuchsia-400 dark:to-pink-400"
            >
              PlutoLab
            </h3>
            <p className="mt-2 text-sm text-zinc-500 dark:text-zinc-400">
              Your AI Workshop
            </p>
          </div>

          {/* 技术栈 badges */}
          <div className="mt-8 flex flex-wrap items-center justify-center gap-2">
            {stacks.map((s) => (
              <span
                key={s.name}
                className={`inline-flex items-center rounded-full bg-gradient-to-r ${s.color} px-3 py-1 text-xs font-medium text-white shadow-sm transition-transform hover:scale-105`}
              >
                {s.name}
              </span>
            ))}
          </div>

          {/* 链接行 */}
          <div className="mt-8 flex flex-wrap items-center justify-center gap-6">
            {links.map((l) => {
              const Icon = l.icon;
              return (
                <Link
                  key={l.name}
                  href={l.href}
                  target={l.external ? "_blank" : undefined}
                  rel={l.external ? "noopener noreferrer" : undefined}
                  className="group inline-flex items-center gap-1.5 text-sm text-zinc-600 transition-colors hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100"
                >
                  <Icon className="size-4" />
                  {l.name}
                  <ExternalLink className="size-3 opacity-0 transition-opacity group-hover:opacity-100" />
                </Link>
              );
            })}
          </div>

          {/* 版权 — 细分割线 */}
          <div className="mt-10 flex flex-col items-center gap-1.5 border-t border-white/20 pt-6 dark:border-white/[0.06]">
            <p className="flex items-center gap-1.5 font-mono text-xs text-zinc-500 dark:text-zinc-500">
              <span>Built with</span>
              <Heart className="size-3 fill-pink-500 text-pink-500" />
              <span>
                by{" "}
                <span className="font-semibold text-zinc-700 dark:text-zinc-300">
                  pluto
                </span>
              </span>
            </p>
            <p className="font-mono text-xs text-zinc-400 dark:text-zinc-600">
              © 2026 · Phase 1.b.3 · MIT-ish · Open source
            </p>
          </div>
        </div>
      </div>
    </motion.footer>
  );
}
