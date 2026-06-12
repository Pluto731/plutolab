"use client";

import { MailCheck } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { AuthShell } from "@/components/auth/auth-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { forgotPassword } from "@/lib/auth";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [emailFocused, setEmailFocused] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [sentMessage, setSentMessage] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setIsLoading(true);
    try {
      const res = await forgotPassword(email);
      setSentMessage(res.message);
    } catch (err) {
      setError(err instanceof Error ? err.message : "请求失败，请稍后重试");
    } finally {
      setIsLoading(false);
    }
  };

  if (sentMessage) {
    return (
      <AuthShell>
        <div className="space-y-6 text-center">
          <div className="mx-auto flex size-16 items-center justify-center rounded-full bg-primary/10">
            <MailCheck className="size-8 text-primary" />
          </div>
          <div className="space-y-2">
            <h1 className="text-3xl font-bold tracking-tight">检查你的邮箱</h1>
            <p className="text-sm leading-relaxed text-muted-foreground">{sentMessage}</p>
            <p className="text-xs text-muted-foreground">
              没收到？检查垃圾邮件，或 1 分钟后再试一次。
            </p>
          </div>
          <Link
            href="/login"
            className="inline-block text-sm font-medium text-primary hover:underline"
          >
            返回登录
          </Link>
        </div>
      </AuthShell>
    );
  }

  return (
    <AuthShell typing={emailFocused}>
      <div className="mb-10 text-center">
        <h1 className="mb-2 text-3xl font-bold tracking-tight">忘记密码</h1>
        <p className="text-sm text-muted-foreground">
          输入注册邮箱，我们会发送重置链接
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
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

        {error && (
          <div
            role="alert"
            className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive"
          >
            {error}
          </div>
        )}

        <Button type="submit" size="lg" className="h-12 w-full text-base" disabled={isLoading}>
          {isLoading ? "发送中…" : "发送重置链接"}
        </Button>
      </form>

      <p className="mt-8 text-center text-sm text-muted-foreground">
        想起来了？{" "}
        <Link href="/login" className="font-medium text-foreground hover:underline">
          返回登录
        </Link>
      </p>
    </AuthShell>
  );
}
