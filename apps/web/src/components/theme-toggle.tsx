"use client";

import { motion } from "framer-motion";
import { useTheme } from "next-themes";
import { useEffect, useId, useRef, useState } from "react";

/**
 * 太阳 ↔ 月亮 morph 主题切换。
 *
 * 光线收缩旋转隐去，中心圆膨胀成月亮，遮罩刻出月牙；spring 物理。
 * 切换时一声轻柔的开关咔哒。由 next-themes 驱动（保证持久化 + SSR 同步）。
 */

let _ctx: AudioContext | null = null;
let _buf: AudioBuffer | null = null;

function audioCtx(): AudioContext {
  if (!_ctx) {
    _ctx = new (window.AudioContext ||
      (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)();
  }
  if (_ctx.state === "suspended") void _ctx.resume();
  return _ctx;
}

function ensureBuf(ac: AudioContext): AudioBuffer {
  if (_buf && _buf.sampleRate === ac.sampleRate) return _buf;
  const rate = ac.sampleRate;
  const len = Math.floor(rate * 0.006);
  const buf = ac.createBuffer(1, len, rate);
  const ch = buf.getChannelData(0);
  for (let i = 0; i < len; i++) {
    const t = i / len;
    const sine = Math.sin(2 * Math.PI * 3400 * t);
    const noise = Math.random() * 2 - 1;
    ch[i] = (sine * 0.6 + noise * 0.4) * (1 - t) ** 3;
  }
  _buf = buf;
  return buf;
}

function playTick(last: React.MutableRefObject<number>): void {
  const now = performance.now();
  if (now - last.current < 80) return;
  last.current = now;
  try {
    const ac = audioCtx();
    const src = ac.createBufferSource();
    const gain = ac.createGain();
    src.buffer = ensureBuf(ac);
    gain.gain.value = 0.08;
    src.connect(gain);
    gain.connect(ac.destination);
    src.start();
  } catch {
    /* 静默：音频不可用不影响切换 */
  }
}

export function ThemeToggle({ sound = true }: { sound?: boolean }) {
  const rawId = useId();
  const maskId = `att${rawId.replace(/:/g, "")}`;
  const lastSnd = useRef(0);
  const isFirst = useRef(true);
  const [mounted, setMounted] = useState(false);
  const { resolvedTheme, setTheme } = useTheme();

  useEffect(() => {
    setMounted(true);
    requestAnimationFrame(() => {
      isFirst.current = false;
    });
  }, []);

  // 占位避免 SSR 水合不一致 (与旧实现一致, size-10)
  if (!mounted) return <div className="size-10" />;

  const isDark = resolvedTheme === "dark";

  const toggle = () => {
    setTheme(isDark ? "light" : "dark");
    if (sound) playTick(lastSnd);
  };

  const spring = isFirst.current
    ? { duration: 0 }
    : { type: "spring" as const, stiffness: 380, damping: 30 };

  return (
    <motion.button
      type="button"
      onClick={toggle}
      whileHover={{ scale: 1.1 }}
      whileTap={{ scale: 0.86 }}
      transition={{ type: "spring", stiffness: 400, damping: 25 }}
      className="inline-flex size-10 items-center justify-center rounded-full border border-zinc-200 bg-white/80 text-zinc-700 backdrop-blur transition-colors hover:border-zinc-300 dark:border-zinc-800 dark:bg-zinc-950/60 dark:text-zinc-300 dark:hover:border-zinc-700"
      aria-label="切换主题"
    >
      <motion.svg
        width="20"
        height="20"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        initial={false}
        animate={{ rotate: isDark ? 270 : 0 }}
        transition={spring}
        style={{ overflow: "visible" }}
      >
        <mask id={maskId}>
          <rect x="0" y="0" width="100%" height="100%" fill="white" />
          <motion.circle
            initial={false}
            animate={{ cx: isDark ? 17 : 33, cy: isDark ? 8 : 0 }}
            transition={spring}
            r="9"
            fill="black"
          />
        </mask>

        <motion.circle
          cx="12"
          cy="12"
          fill="currentColor"
          stroke="none"
          mask={`url(#${maskId})`}
          initial={false}
          animate={{ r: isDark ? 9 : 5 }}
          transition={spring}
        />

        <motion.g
          initial={false}
          animate={{ opacity: isDark ? 0 : 1, scale: isDark ? 0 : 1, rotate: isDark ? -30 : 0 }}
          transition={spring}
          style={{ transformOrigin: "12px 12px" }}
        >
          <line x1="12" y1="1" x2="12" y2="3" />
          <line x1="12" y1="21" x2="12" y2="23" />
          <line x1="1" y1="12" x2="3" y2="12" />
          <line x1="21" y1="12" x2="23" y2="12" />
          <line x1="5.64" y1="5.64" x2="4.22" y2="4.22" />
          <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
          <line x1="5.64" y1="18.36" x2="4.22" y2="19.78" />
          <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
        </motion.g>
      </motion.svg>
    </motion.button>
  );
}
