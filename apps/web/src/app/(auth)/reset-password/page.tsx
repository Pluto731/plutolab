"use client";

import { CheckCircle2, Eye, EyeOff } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { AuthShell } from "@/components/auth/auth-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { resetPassword } from "@/lib/auth";

export default function ResetPasswordPage() {
  const [token, setToken] = useState<string | null>(null);
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [passwordFocused, setPasswordFocused] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);

  // token 从 query 读 — 用 window.location 兼容当前 Next.js 版本
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setToken(params.get("token") ?? "");
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) return;
    setError("");
    setIsLoading(true);
    try {
      await resetPassword(token, password);
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "重置失败，请稍后重试");
      setIsLoading(false);
    }
  };

  // token 还没从 URL 读出来 — 防止 SSR/初次渲染闪烁
  if (token === null) {
    return (
      <AuthShell>
        <div className="text-center text-sm text-muted-foreground">加载中…</div>
      </AuthShell>
    );
  }

  if (token === "") {
    return (
      <AuthShell>
        <div className="space-y-6 text-center">
          <h1 className="text-3xl font-bold tracking-tight">链接无效</h1>
          <p className="text-sm text-muted-foreground">
            缺少重置令牌。请通过邮件中的链接打开此页面。
          </p>
          <Link
            href="/forgot-password"
            className="inline-block text-sm font-medium text-primary hover:underline"
          >
            重新发送重置邮件
          </Link>
        </div>
      </AuthShell>
    );
  }

  if (done) {
    return (
      <AuthShell>
        <div className="space-y-6 text-center">
          <div className="mx-auto flex size-16 items-center justify-center rounded-full bg-emerald-500/10">
            <CheckCircle2 className="size-8 text-emerald-500" />
          </div>
          <div className="space-y-2">
            <h1 className="text-3xl font-bold tracking-tight">密码已重置</h1>
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

  return (
    <AuthShell hidingEyes={passwordFocused}>
      <div className="mb-10 text-center">
        <h1 className="mb-2 text-3xl font-bold tracking-tight">设置新密码</h1>
        <p className="text-sm text-muted-foreground">至少 8 位</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
        <div className="space-y-2">
          <Label htmlFor="password">新密码</Label>
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

        {error && (
          <div
            role="alert"
            className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive"
          >
            {error}
          </div>
        )}

        <Button type="submit" size="lg" className="h-12 w-full text-base" disabled={isLoading}>
          {isLoading ? "重置中…" : "重置密码"}
        </Button>
      </form>

      <p className="mt-8 text-center text-sm text-muted-foreground">
        <Link href="/login" className="font-medium text-foreground hover:underline">
          返回登录
        </Link>
      </p>
    </AuthShell>
  );
}
