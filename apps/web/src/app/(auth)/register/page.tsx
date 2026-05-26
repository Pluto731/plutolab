"use client";

import { Eye, EyeOff } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { AuthShell } from "@/components/auth/auth-shell";
import { GitHubButton } from "@/components/auth/github-button";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { register, storeTokens } from "@/lib/auth";

export default function RegisterPage() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [glancing, setGlancing] = useState(false);
  const [passwordFocused, setPasswordFocused] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setIsLoading(true);
    try {
      const tokens = await register({ email, password, name: name.trim() || undefined });
      storeTokens(tokens);
      // 整页跳转, 让 Nav 重新读取登录态
      window.location.assign("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "注册失败，请稍后重试");
      setIsLoading(false);
    }
  };

  return (
    <AuthShell typing={glancing} hidingEyes={passwordFocused}>
      <div className="mb-10 text-center">
        <h1 className="mb-2 text-3xl font-bold tracking-tight">创建账号</h1>
        <p className="text-sm text-muted-foreground">开启你的 AI 工作台</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
        <div className="space-y-2">
          <Label htmlFor="name">昵称 <span className="text-muted-foreground">（可选）</span></Label>
          <Input
            id="name"
            type="text"
            placeholder="怎么称呼你"
            value={name}
            autoComplete="nickname"
            maxLength={100}
            onChange={(e) => setName(e.target.value)}
            onFocus={() => setGlancing(true)}
            onBlur={() => setGlancing(false)}
            className="h-12"
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="email">邮箱</Label>
          <Input
            id="email"
            type="email"
            placeholder="you@example.com"
            value={email}
            autoComplete="email"
            onChange={(e) => setEmail(e.target.value)}
            onFocus={() => setGlancing(true)}
            onBlur={() => setGlancing(false)}
            required
            className="h-12"
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="password">密码 <span className="text-muted-foreground">（至少 8 位）</span></Label>
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
          {isLoading ? "创建中…" : "创建账号"}
        </Button>
      </form>

      <GitHubButton label="用 GitHub 注册" />

      <p className="mt-8 text-center text-sm text-muted-foreground">
        已有账号？{" "}
        <Link href="/login" className="font-medium text-foreground hover:underline">
          登录
        </Link>
      </p>
    </AuthShell>
  );
}
