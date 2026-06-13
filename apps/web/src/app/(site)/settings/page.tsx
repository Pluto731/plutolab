"use client";

import { useQueryClient } from "@tanstack/react-query";
import { AlertCircle, CheckCircle2, KeyRound, Loader2, UserRound } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { ApiKeysSection } from "@/components/auth/api-keys-section";
import { Avatar } from "@/components/auth/avatar";
import { useAuthUser } from "@/components/auth/use-auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  changePassword,
  sendVerification,
  updateProfile,
  uploadAvatar,
} from "@/lib/auth";

type Msg = { type: "ok" | "err"; text: string } | null;

function FormMsg({ msg }: { msg: Msg }) {
  if (!msg) return null;
  return (
    <p
      className={
        msg.type === "ok"
          ? "text-sm text-emerald-600 dark:text-emerald-400"
          : "text-sm text-destructive"
      }
    >
      {msg.text}
    </p>
  );
}

export default function SettingsPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { user, loading, mounted } = useAuthUser();

  const fileRef = useRef<HTMLInputElement>(null);
  const [uploadingAvatar, setUploadingAvatar] = useState(false);
  const [avatarMsg, setAvatarMsg] = useState<Msg>(null);

  const [name, setName] = useState("");
  const [savingName, setSavingName] = useState(false);
  const [nameMsg, setNameMsg] = useState<Msg>(null);

  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [savingPw, setSavingPw] = useState(false);
  const [pwMsg, setPwMsg] = useState<Msg>(null);

  const [resendingVerify, setResendingVerify] = useState(false);
  const [verifyCooldown, setVerifyCooldown] = useState(0);
  const [verifyMsg, setVerifyMsg] = useState<Msg>(null);

  // 重发验证邮件按钮的 60s 冷却 (匹配后端 email_verify_rate_limit_seconds)
  useEffect(() => {
    if (verifyCooldown <= 0) return;
    const t = setInterval(() => setVerifyCooldown((c) => Math.max(0, c - 1)), 1000);
    return () => clearInterval(t);
  }, [verifyCooldown]);

  useEffect(() => {
    if (mounted && !loading && !user) router.replace("/login");
  }, [mounted, loading, user, router]);

  useEffect(() => {
    if (user) setName(user.name ?? "");
  }, [user]);

  if (!user) {
    return (
      <main className="flex min-h-[60vh] items-center justify-center text-muted-foreground">
        <Loader2 className="mr-2 size-5 animate-spin" /> 加载中…
      </main>
    );
  }

  const refreshUser = () => queryClient.invalidateQueries({ queryKey: ["auth-me"] });

  const onPickAvatar = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = ""; // 允许重选同一文件
    if (!file) return;
    setAvatarMsg(null);
    setUploadingAvatar(true);
    try {
      await uploadAvatar(file);
      await refreshUser();
      setAvatarMsg({ type: "ok", text: "头像已更新" });
    } catch (err) {
      setAvatarMsg({ type: "err", text: err instanceof Error ? err.message : "上传失败" });
    } finally {
      setUploadingAvatar(false);
    }
  };

  const onSaveName = async (e: React.FormEvent) => {
    e.preventDefault();
    setNameMsg(null);
    setSavingName(true);
    try {
      await updateProfile({ name: name.trim() });
      await refreshUser();
      setNameMsg({ type: "ok", text: "已保存" });
    } catch (err) {
      setNameMsg({ type: "err", text: err instanceof Error ? err.message : "保存失败" });
    } finally {
      setSavingName(false);
    }
  };

  const onResendVerify = async () => {
    setVerifyMsg(null);
    setResendingVerify(true);
    try {
      const res = await sendVerification();
      setVerifyMsg({ type: "ok", text: res.message });
      setVerifyCooldown(60);
    } catch (err) {
      setVerifyMsg({ type: "err", text: err instanceof Error ? err.message : "发送失败" });
    } finally {
      setResendingVerify(false);
    }
  };

  const onChangePw = async (e: React.FormEvent) => {
    e.preventDefault();
    setPwMsg(null);
    if (next !== confirm) {
      setPwMsg({ type: "err", text: "两次输入的新密码不一致" });
      return;
    }
    setSavingPw(true);
    try {
      await changePassword({ current_password: current, new_password: next });
      setCurrent("");
      setNext("");
      setConfirm("");
      setPwMsg({ type: "ok", text: "密码已修改" });
    } catch (err) {
      setPwMsg({ type: "err", text: err instanceof Error ? err.message : "修改失败" });
    } finally {
      setSavingPw(false);
    }
  };

  return (
    <main className="mx-auto max-w-2xl px-6 pb-24 pt-28">
      {/* 顶部用户概览 */}
      <header className="relative mb-8 overflow-hidden rounded-3xl border border-white/40 bg-gradient-to-br from-violet-500/90 via-fuchsia-500/90 to-pink-500/90 p-6 text-white shadow-lg dark:border-white/10">
        <div className="pointer-events-none absolute -right-8 -top-10 size-40 rounded-full bg-white/15 blur-2xl" />
        <div className="relative flex items-center gap-5">
          <div className="group relative">
            <Avatar user={user} className="size-20 text-2xl ring-4 ring-white/30" />
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              disabled={uploadingAvatar}
              className="absolute inset-0 flex items-center justify-center rounded-full bg-black/45 text-xs font-medium opacity-0 transition-opacity hover:opacity-100 disabled:opacity-100"
            >
              {uploadingAvatar ? <Loader2 className="size-5 animate-spin" /> : "更换"}
            </button>
            <input
              ref={fileRef}
              type="file"
              accept="image/*"
              onChange={onPickAvatar}
              className="hidden"
            />
          </div>
          <div className="min-w-0">
            <h1 className="truncate text-2xl font-bold">{user.name || "未命名"}</h1>
            <p className="truncate text-sm text-white/80">{user.email}</p>
            <span className="mt-2 inline-block rounded-full bg-white/20 px-2.5 py-0.5 text-xs font-medium uppercase tracking-wide">
              {user.plan}
            </span>
          </div>
        </div>
        {avatarMsg && (
          <p
            className={`relative mt-3 text-sm ${avatarMsg.type === "ok" ? "text-white" : "text-rose-100"}`}
          >
            {avatarMsg.text}
          </p>
        )}
      </header>

      {/* 个人资料 */}
      <section className="mb-6 rounded-2xl border border-border bg-card/80 p-6 shadow-sm backdrop-blur">
        <div className="mb-4 flex items-center gap-2">
          <UserRound className="size-5 text-violet-500" />
          <h2 className="text-lg font-semibold">个人资料</h2>
        </div>
        <form onSubmit={onSaveName} className="space-y-4">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Label htmlFor="email">邮箱</Label>
              {user.email_verified ? (
                <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-xs font-medium text-emerald-600 dark:text-emerald-400">
                  <CheckCircle2 className="size-3" /> 已验证
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/10 px-2 py-0.5 text-xs font-medium text-amber-600 dark:text-amber-400">
                  <AlertCircle className="size-3" /> 未验证
                </span>
              )}
            </div>
            <Input id="email" value={user.email} disabled className="h-11" />
            {!user.email_verified && (
              <div className="flex flex-wrap items-center gap-3 pt-1">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={onResendVerify}
                  disabled={resendingVerify || verifyCooldown > 0}
                >
                  {resendingVerify
                    ? "发送中…"
                    : verifyCooldown > 0
                      ? `重发 (${verifyCooldown}s)`
                      : "重发验证邮件"}
                </Button>
                <FormMsg msg={verifyMsg} />
              </div>
            )}
          </div>
          <div className="space-y-2">
            <Label htmlFor="name">昵称</Label>
            <Input
              id="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={100}
              required
              className="h-11"
            />
          </div>
          <div className="flex items-center gap-3">
            <Button type="submit" disabled={savingName}>
              {savingName ? "保存中…" : "保存"}
            </Button>
            <FormMsg msg={nameMsg} />
          </div>
        </form>
      </section>

      {/* 修改密码 */}
      <section className="rounded-2xl border border-border bg-card/80 p-6 shadow-sm backdrop-blur">
        <div className="mb-4 flex items-center gap-2">
          <KeyRound className="size-5 text-fuchsia-500" />
          <h2 className="text-lg font-semibold">修改密码</h2>
        </div>
        <form onSubmit={onChangePw} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="current">当前密码</Label>
            <Input
              id="current"
              type="password"
              value={current}
              autoComplete="current-password"
              onChange={(e) => setCurrent(e.target.value)}
              required
              className="h-11"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="new">新密码 <span className="text-muted-foreground">（至少 8 位）</span></Label>
            <Input
              id="new"
              type="password"
              value={next}
              autoComplete="new-password"
              minLength={8}
              onChange={(e) => setNext(e.target.value)}
              required
              className="h-11"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="confirm">确认新密码</Label>
            <Input
              id="confirm"
              type="password"
              value={confirm}
              autoComplete="new-password"
              minLength={8}
              onChange={(e) => setConfirm(e.target.value)}
              required
              className="h-11"
            />
          </div>
          <div className="flex items-center gap-3">
            <Button type="submit" disabled={savingPw}>
              {savingPw ? "修改中…" : "修改密码"}
            </Button>
            <FormMsg msg={pwMsg} />
          </div>
        </form>
      </section>

      {/* API Keys (Phase 2.5) */}
      <div className="mt-6">
        <ApiKeysSection />
      </div>
    </main>
  );
}
