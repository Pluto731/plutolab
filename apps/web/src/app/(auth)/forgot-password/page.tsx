"use client";

import { ArrowLeft, CheckCircle2, Eye, EyeOff, MailCheck } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { AuthShell } from "@/components/auth/auth-shell";
import { OTPInput } from "@/components/auth/otp-input";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { requestPasswordCode, verifyPasswordCode } from "@/lib/auth";

type Step = "input" | "code" | "done";

export default function ForgotPasswordPage() {
  const [step, setStep] = useState<Step>("input");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [code, setCode] = useState("");

  const [showPassword, setShowPassword] = useState(false);
  const [emailFocused, setEmailFocused] = useState(false);
  const [passwordFocused, setPasswordFocused] = useState(false);

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  // ─── Step 1: 输邮箱 + 新密码 ──────────────────────────────
  const submitStep1 = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (password !== confirm) {
      setError("两次输入的新密码不一致");
      return;
    }
    setIsLoading(true);
    try {
      await requestPasswordCode(email, password);
      setStep("code");
    } catch (err) {
      setError(err instanceof Error ? err.message : "请求失败，请稍后重试");
    } finally {
      setIsLoading(false);
    }
  };

  // ─── Step 2: 输 6 位验证码 ────────────────────────────────
  const submitStep2 = async () => {
    setError("");
    setIsLoading(true);
    try {
      await verifyPasswordCode(email, code);
      setStep("done");
    } catch (err) {
      setError(err instanceof Error ? err.message : "验证失败");
      setCode("");
    } finally {
      setIsLoading(false);
    }
  };

  // 验证码满 6 位自动提交 (减少多余点击)
  useEffect(() => {
    if (step === "code" && code.length === 6 && !isLoading) {
      void submitStep2();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [code, step]);

  const [resending, setResending] = useState(false);
  const [resendCooldown, setResendCooldown] = useState(60);
  useEffect(() => {
    if (step !== "code" || resendCooldown <= 0) return;
    const t = setInterval(() => setResendCooldown((c) => Math.max(0, c - 1)), 1000);
    return () => clearInterval(t);
  }, [step, resendCooldown]);

  const onResend = async () => {
    if (resending || resendCooldown > 0) return;
    setError("");
    setResending(true);
    try {
      await requestPasswordCode(email, password);
      setResendCooldown(60);
    } catch (err) {
      setError(err instanceof Error ? err.message : "重发失败");
    } finally {
      setResending(false);
    }
  };

  // ─── Step 3: 完成态 ────────────────────────────────────────
  if (step === "done") {
    return (
      <AuthShell>
        <div className="space-y-6 text-center">
          <div className="mx-auto flex size-16 items-center justify-center rounded-full bg-emerald-500/10">
            <CheckCircle2 className="size-8 text-emerald-500" />
          </div>
          <div className="space-y-2">
            <h1 className="text-3xl font-bold tracking-tight">密码已修改</h1>
            <p className="text-sm text-muted-foreground">用新密码登录吧。</p>
          </div>
          <Link
            href="/login"
            className="inline-block text-sm font-medium text-primary hover:underline"
          >
            前往登录
          </Link>
        </div>
      </AuthShell>
    );
  }

  // ─── Step 2: 验证码输入 ────────────────────────────────────
  if (step === "code") {
    return (
      <AuthShell>
        <div className="space-y-6">
          <button
            type="button"
            onClick={() => {
              setStep("input");
              setCode("");
              setError("");
            }}
            className="flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeft className="size-4" /> 返回修改
          </button>

          <div className="space-y-2 text-center">
            <div className="mx-auto flex size-16 items-center justify-center rounded-full bg-primary/10">
              <MailCheck className="size-8 text-primary" />
            </div>
            <h1 className="text-3xl font-bold tracking-tight">输入验证码</h1>
            <p className="text-sm leading-relaxed text-muted-foreground">
              验证码已发送到{" "}
              <span className="font-medium text-foreground">{email}</span>
              <br />
              请查收邮件（10 分钟内有效），输入验证码完成密码修改。
            </p>
          </div>

          <OTPInput value={code} onChange={setCode} autoFocus disabled={isLoading} />

          {error && (
            <div
              role="alert"
              className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-center text-sm text-destructive"
            >
              {error}
            </div>
          )}

          <div className="space-y-2 text-center">
            <p className="text-xs text-muted-foreground">
              {isLoading ? "验证中…" : "输入完整 6 位会自动提交"}
            </p>
            <button
              type="button"
              onClick={onResend}
              disabled={resending || resendCooldown > 0}
              className="text-sm font-medium text-primary transition-opacity hover:underline disabled:cursor-not-allowed disabled:opacity-50"
            >
              {resending
                ? "重发中…"
                : resendCooldown > 0
                  ? `重发验证码 (${resendCooldown}s)`
                  : "没收到？重发验证码"}
            </button>
          </div>
        </div>
      </AuthShell>
    );
  }

  // ─── Step 1: 输邮箱 + 新密码 ──────────────────────────────
  return (
    <AuthShell typing={emailFocused} hidingEyes={passwordFocused}>
      <div className="mb-8 text-center">
        <h1 className="mb-2 text-3xl font-bold tracking-tight">修改密码</h1>
        <p className="text-sm text-muted-foreground">
          输入注册邮箱和新密码，我们会发验证码到你邮箱
        </p>
      </div>

      <form onSubmit={submitStep1} className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="email">邮箱</Label>
          <Input
            id="email"
            type="email"
            placeholder="you@example.com"
            value={email}
            autoComplete="email"
            onChange={(e) => setEmail(e.target.value)}
            onFocus={() => setEmailFocused(true)}
            onBlur={() => setEmailFocused(false)}
            required
            className="h-12"
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="password">
            新密码 <span className="text-muted-foreground">（至少 8 位）</span>
          </Label>
          <div className="relative">
            <Input
              id="password"
              type={showPassword ? "text" : "password"}
              placeholder="••••••••"
              value={password}
              autoComplete="new-password"
              minLength={8}
              onChange={(e) => setPassword(e.target.value)}
              onFocus={() => setPasswordFocused(true)}
              onBlur={() => setPasswordFocused(false)}
              required
              className="h-12 pr-10"
            />
            <button
              type="button"
              onClick={() => setShowPassword((v) => !v)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground transition-colors hover:text-foreground"
              aria-label={showPassword ? "隐藏密码" : "显示密码"}
            >
              {showPassword ? <EyeOff className="size-5" /> : <Eye className="size-5" />}
            </button>
          </div>
        </div>

        <div className="space-y-2">
          <Label htmlFor="confirm">确认新密码</Label>
          <Input
            id="confirm"
            type={showPassword ? "text" : "password"}
            placeholder="••••••••"
            value={confirm}
            autoComplete="new-password"
            minLength={8}
            onChange={(e) => setConfirm(e.target.value)}
            onFocus={() => setPasswordFocused(true)}
            onBlur={() => setPasswordFocused(false)}
            required
            className="h-12"
          />
        </div>

        {error && (
          <div
            role="alert"
            className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive"
          >
            {error}
          </div>
        )}

        <Button type="submit" size="lg" className="h-12 w-full text-base" disabled={isLoading}>
          {isLoading ? "发送中…" : "发送验证码"}
        </Button>
      </form>

      <p className="mt-6 text-center text-sm text-muted-foreground">
        想起来了？{" "}
        <Link href="/login" className="font-medium text-foreground hover:underline">
          返回登录
        </Link>
      </p>
    </AuthShell>
  );
}
