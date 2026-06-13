"use client";

import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { AuthShell } from "@/components/auth/auth-shell";
import { verifyEmail } from "@/lib/auth";

type Phase = "loading" | "success" | "error" | "missing";

export default function VerifyEmailPage() {
  const [phase, setPhase] = useState<Phase>("loading");
  const [error, setError] = useState("");
  const ran = useRef(false);

  useEffect(() => {
    if (ran.current) return; // 防 StrictMode 双跑 (token 一次性, 不能多调)
    ran.current = true;

    const token = new URLSearchParams(window.location.search).get("token");
    if (!token) {
      setPhase("missing");
      return;
    }
    verifyEmail(token)
      .then(() => setPhase("success"))
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "验证失败");
        setPhase("error");
      });
  }, []);

  if (phase === "loading") {
    return (
      <AuthShell>
        <div className="flex flex-col items-center gap-4 text-center">
          <Loader2 className="size-10 animate-spin text-primary" />
          <p className="text-sm text-muted-foreground">正在验证邮箱…</p>
        </div>
      </AuthShell>
    );
  }

  if (phase === "success") {
    return (
      <AuthShell>
        <div className="space-y-6 text-center">
          <div className="mx-auto flex size-16 items-center justify-center rounded-full bg-emerald-500/10">
            <CheckCircle2 className="size-8 text-emerald-500" />
          </div>
          <div className="space-y-2">
            <h1 className="text-3xl font-bold tracking-tight">邮箱已验证</h1>
            <p className="text-sm text-muted-foreground">
              欢迎加入 PlutoLab，开始你的 AI 工作之旅。
            </p>
          </div>
          <Link
            href="/"
            className="inline-block text-sm font-medium text-primary hover:underline"
          >
            前往首页
          </Link>
        </div>
      </AuthShell>
    );
  }

  if (phase === "missing") {
    return (
      <AuthShell>
        <div className="space-y-6 text-center">
          <h1 className="text-3xl font-bold tracking-tight">链接无效</h1>
          <p className="text-sm text-muted-foreground">
            缺少验证令牌。请通过邮件里的链接打开此页面。
          </p>
          <Link
            href="/settings"
            className="inline-block text-sm font-medium text-primary hover:underline"
          >
            前往设置重发邮件
          </Link>
        </div>
      </AuthShell>
    );
  }

  return (
    <AuthShell>
      <div className="space-y-6 text-center">
        <div className="mx-auto flex size-16 items-center justify-center rounded-full bg-destructive/10">
          <XCircle className="size-8 text-destructive" />
        </div>
        <div className="space-y-2">
          <h1 className="text-3xl font-bold tracking-tight">验证失败</h1>
          <p className="text-sm text-muted-foreground">{error || "链接无效或已过期"}</p>
        </div>
        <Link
          href="/settings"
          className="inline-block text-sm font-medium text-primary hover:underline"
        >
          前往设置重发邮件
        </Link>
      </div>
    </AuthShell>
  );
}
