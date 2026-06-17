"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  Clock,
  Coffee,
  History,
  Loader2,
  Pause,
  Play,
  RotateCcw,
  Sparkles,
  Target,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useAuthUser } from "@/components/auth/use-auth";
import { Button } from "@/components/ui/button";
import {
  listPomodoros,
  type PomodoroKind,
  type PomodoroWithTask,
  recordPomodoro,
} from "@/lib/pomodoros";
import { listTasks, type TaskPublic } from "@/lib/tasks";
import { cn } from "@/lib/utils";

const MODES: { key: PomodoroKind; label: string; seconds: number; gradient: string }[] = [
  {
    key: "focus",
    label: "专注",
    seconds: 25 * 60,
    gradient: "from-rose-500 to-orange-500",
  },
  {
    key: "short_break",
    label: "短休",
    seconds: 5 * 60,
    gradient: "from-emerald-500 to-teal-500",
  },
  {
    key: "long_break",
    label: "长休",
    seconds: 15 * 60,
    gradient: "from-sky-500 to-indigo-500",
  },
];

function mmss(total: number): string {
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function formatTimeOfDay(iso: string): string {
  const d = new Date(iso);
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

const NOTIFICATION_TITLE: Record<PomodoroKind, string> = {
  focus: "专注完成 ✨",
  short_break: "短休结束",
  long_break: "长休结束",
};

const NOTIFICATION_BODY: Record<PomodoroKind, string> = {
  focus: "干得漂亮，去喝口水吧。",
  short_break: "回来工作了。",
  long_break: "充电完毕，启动下一段专注。",
};

async function ensureNotificationPermission(): Promise<boolean> {
  if (typeof window === "undefined" || !("Notification" in window)) return false;
  if (Notification.permission === "granted") return true;
  if (Notification.permission === "denied") return false;
  const result = await Notification.requestPermission();
  return result === "granted";
}

function notify(kind: PomodoroKind) {
  if (typeof window === "undefined" || !("Notification" in window)) return;
  if (Notification.permission !== "granted") return;
  try {
    new Notification(NOTIFICATION_TITLE[kind], {
      body: NOTIFICATION_BODY[kind],
      icon: "/favicon.ico",
      tag: "plutolab-pomodoro",
    });
  } catch {
    // Safari 私有窗口等可能抛
  }
}

export default function PomodoroPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { user, loading, mounted } = useAuthUser();

  useEffect(() => {
    if (mounted && !loading && !user) router.replace("/login");
  }, [mounted, loading, user, router]);

  const [mode, setMode] = useState<PomodoroKind>("focus");
  const [taskId, setTaskId] = useState<string | null>(null);
  // 当前剩余秒数 (用户能看到的). 用 deadlineRef + Date.now() 计算避免 setInterval 漂移
  const modeMeta = MODES.find((m) => m.key === mode) ?? MODES[0];
  const [remaining, setRemaining] = useState(modeMeta.seconds);
  const [running, setRunning] = useState(false);
  const deadlineRef = useRef<number | null>(null);
  const baseSecondsRef = useRef(modeMeta.seconds);

  // 切 mode 时 reset 时钟 + 停止运行
  useEffect(() => {
    setRunning(false);
    deadlineRef.current = null;
    baseSecondsRef.current = modeMeta.seconds;
    setRemaining(modeMeta.seconds);
  }, [mode, modeMeta.seconds]);

  // 查询用户任务列表 (focus 模式才需要关联)
  const { data: tasks } = useQuery<TaskPublic[]>({
    queryKey: ["tasks"],
    queryFn: listTasks,
    enabled: !!user,
    staleTime: 30 * 1000,
  });
  const undoneTasks = useMemo(
    () => (tasks ?? []).filter((t) => !t.done && !t.parent_id),
    [tasks],
  );

  // 历史 (今日)
  const { data: history } = useQuery<PomodoroWithTask[]>({
    queryKey: ["pomodoros", "today"],
    queryFn: () => listPomodoros(1),
    enabled: !!user,
    staleTime: 30 * 1000,
  });

  const recordMutation = useMutation({
    mutationFn: recordPomodoro,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pomodoros"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
    },
  });

  // 完成回调 — 记录会话 + 通知
  const handleComplete = useCallback(
    (kind: PomodoroKind, planned: number, tid: string | null) => {
      recordMutation.mutate({
        kind,
        planned_seconds: planned,
        task_id: tid ?? undefined,
      });
      notify(kind);
    },
    [recordMutation],
  );

  // tick loop — 用 Date.now() 计算剩余, 不依赖 setInterval 精度; 后台/切 tab 也准
  useEffect(() => {
    if (!running) return;
    const tick = () => {
      const dl = deadlineRef.current;
      if (dl === null) return;
      const left = Math.max(0, Math.ceil((dl - Date.now()) / 1000));
      setRemaining(left);
      if (left === 0) {
        // 完成
        setRunning(false);
        deadlineRef.current = null;
        const currentMode = mode;
        const planned = baseSecondsRef.current;
        const tid = currentMode === "focus" ? taskId : null;
        handleComplete(currentMode, planned, tid);
        // reset 显示
        setRemaining(modeMeta.seconds);
      }
    };
    tick(); // 立刻跑一次让切 tab 回来即时同步
    const id = setInterval(tick, 250);
    return () => clearInterval(id);
  }, [running, mode, taskId, handleComplete, modeMeta.seconds]);

  // tab 标题倒计时
  useEffect(() => {
    if (typeof document === "undefined") return;
    const original = "PlutoLab — Your AI Workshop";
    if (running) {
      document.title = `${mmss(remaining)} · ${modeMeta.label}`;
    } else {
      document.title = original;
    }
    return () => {
      document.title = original;
    };
  }, [running, remaining, modeMeta.label]);

  const onStart = async () => {
    if (running) return;
    await ensureNotificationPermission();
    const left = remaining > 0 ? remaining : modeMeta.seconds;
    baseSecondsRef.current = modeMeta.seconds;
    deadlineRef.current = Date.now() + left * 1000;
    setRunning(true);
  };

  const onPause = () => {
    setRunning(false);
    deadlineRef.current = null;
  };

  const onReset = () => {
    setRunning(false);
    deadlineRef.current = null;
    setRemaining(modeMeta.seconds);
  };

  if (!user) {
    return (
      <main className="flex min-h-[60vh] items-center justify-center text-muted-foreground">
        <Loader2 className="mr-2 size-5 animate-spin" /> 加载中…
      </main>
    );
  }

  const progress = 1 - remaining / modeMeta.seconds;
  const focusToday = (history ?? []).filter((p) => p.kind === "focus").length;

  return (
    <main className="mx-auto max-w-2xl px-6 pb-24 pt-20 md:pt-10">
      {/* 渐变 hero */}
      <header className="relative mb-8 overflow-hidden rounded-3xl border border-white/40 bg-gradient-to-br from-rose-500/90 via-orange-500/90 to-amber-500/90 p-6 text-white shadow-lg dark:border-white/10">
        <div className="pointer-events-none absolute -right-10 -top-12 size-44 rounded-full bg-white/15 blur-2xl" />
        <div className="pointer-events-none absolute -bottom-12 left-1/3 size-40 rounded-full bg-amber-300/30 blur-3xl" />
        <div className="relative">
          <div className="mb-2 inline-flex items-center gap-1.5 rounded-full bg-white/15 px-2.5 py-0.5 text-xs font-medium backdrop-blur">
            <Sparkles className="size-3" />
            Phase 3.4 · 番茄钟
          </div>
          <h1 className="text-2xl font-bold">番茄钟</h1>
          <p className="mt-1 text-sm text-white/85">
            {focusToday === 0
              ? "今天还没开始 — 一颗番茄就够了。"
              : `今天已完成 ${focusToday} 颗 🍅`}
          </p>
        </div>
      </header>

      {/* 模式切换 */}
      <div className="mb-6 flex gap-2 overflow-x-auto rounded-xl border border-border bg-card/50 p-1 backdrop-blur">
        {MODES.map((m) => {
          const active = m.key === mode;
          return (
            <button
              key={m.key}
              type="button"
              onClick={() => setMode(m.key)}
              disabled={running}
              className={cn(
                "flex flex-1 items-center justify-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium transition-all disabled:opacity-50",
                active
                  ? `bg-gradient-to-r ${m.gradient} text-white shadow-sm`
                  : "text-muted-foreground hover:bg-accent",
              )}
            >
              {m.key === "focus" ? (
                <Target className="size-4" />
              ) : (
                <Coffee className="size-4" />
              )}
              {m.label}
              <span className="text-[10px] opacity-75">
                {Math.floor(m.seconds / 60)}m
              </span>
            </button>
          );
        })}
      </div>

      {/* 圆环 + 数字 */}
      <div className="mb-6 flex flex-col items-center rounded-3xl border border-border bg-card/80 p-8 shadow-sm backdrop-blur">
        <RingTimer
          progress={progress}
          gradient={modeMeta.gradient}
          label={mmss(remaining)}
          sublabel={modeMeta.label}
        />

        {/* 控制按钮 */}
        <div className="mt-6 flex items-center gap-3">
          {running ? (
            <Button
              type="button"
              onClick={onPause}
              className="bg-gradient-to-r from-zinc-600 to-zinc-700 text-white hover:brightness-110"
            >
              <Pause className="size-4" /> 暂停
            </Button>
          ) : (
            <Button
              type="button"
              onClick={onStart}
              className={cn(
                "bg-gradient-to-r text-white hover:brightness-110",
                modeMeta.gradient,
              )}
            >
              <Play className="size-4" />
              {remaining < modeMeta.seconds ? "继续" : "开始"}
            </Button>
          )}
          <button
            type="button"
            onClick={onReset}
            className="inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
          >
            <RotateCcw className="size-3.5" /> 重置
          </button>
        </div>

        {/* 任务关联 (仅 focus 模式) */}
        {mode === "focus" && (
          <div className="mt-6 w-full">
            <p className="mb-2 px-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              专注什么
            </p>
            <select
              value={taskId ?? ""}
              onChange={(e) => setTaskId(e.target.value || null)}
              className="h-10 w-full rounded-lg border border-border bg-background px-3 text-sm focus:border-rose-500/40 focus:outline-none focus:ring-2 focus:ring-rose-500/15"
            >
              <option value="">— 不关联任务 —</option>
              {undoneTasks.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.title}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* 今日历史 */}
      <section>
        <p className="mb-3 flex items-center gap-1.5 px-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          <History className="size-3" />
          今日记录 {(history ?? []).length > 0 && `· ${history!.length}`}
        </p>
        {!history || history.length === 0 ? (
          <p className="rounded-2xl border border-dashed border-border py-10 text-center text-sm text-muted-foreground">
            还没有记录。完成第一颗番茄会出现在这。
          </p>
        ) : (
          <ul className="overflow-hidden rounded-2xl border border-border bg-card/80 shadow-sm backdrop-blur">
            {history.map((p) => {
              const meta = MODES.find((m) => m.key === p.kind) ?? MODES[0];
              return (
                <li
                  key={p.id}
                  className="flex items-center gap-3 border-b border-border/40 px-4 py-3 last:border-b-0"
                >
                  <span
                    className={cn(
                      "inline-flex size-7 items-center justify-center rounded-lg bg-gradient-to-br text-white",
                      meta.gradient,
                    )}
                  >
                    {p.kind === "focus" ? (
                      <Target className="size-3.5" />
                    ) : (
                      <Coffee className="size-3.5" />
                    )}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium">
                      {meta.label}
                      {p.task_title && (
                        <span className="ml-1.5 text-muted-foreground">
                          · {p.task_title}
                        </span>
                      )}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {Math.round(p.planned_seconds / 60)} 分钟
                    </p>
                  </div>
                  <span className="shrink-0 font-mono text-xs text-muted-foreground">
                    {formatTimeOfDay(p.completed_at)}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </main>
  );
}

function RingTimer({
  progress,
  gradient,
  label,
  sublabel,
}: {
  progress: number;
  gradient: string;
  label: string;
  sublabel: string;
}) {
  const size = 240;
  const stroke = 14;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const clamped = Math.max(0, Math.min(1, progress));
  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <defs>
          {/* gradient id 用随机字符串避免多个 instance 冲突 */}
          <linearGradient id="ringGradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="currentColor" className={`${gradient.split(" ")[0].replace("from-", "text-")}`} />
            <stop offset="100%" stopColor="currentColor" className={`${gradient.split(" ")[1].replace("to-", "text-")}`} />
          </linearGradient>
        </defs>
        {/* 底圈 */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="currentColor"
          strokeWidth={stroke}
          className="text-zinc-200 dark:text-zinc-700/50"
        />
        {/* 进度圈 */}
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="url(#ringGradient)"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          animate={{ strokeDashoffset: c * (1 - clamped) }}
          transition={{ duration: 0.3, ease: "linear" }}
        />
      </svg>
      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
        <div className="font-mono text-5xl font-bold tabular-nums">{label}</div>
        <div className="mt-1 inline-flex items-center gap-1 text-xs text-muted-foreground">
          <Clock className="size-3" /> {sublabel}
        </div>
      </div>
    </div>
  );
}
