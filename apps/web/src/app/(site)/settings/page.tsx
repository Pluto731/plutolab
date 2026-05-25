"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuthUser } from "@/components/auth/use-auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { changePassword, updateProfile } from "@/lib/auth";

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

  const [name, setName] = useState("");
  const [savingName, setSavingName] = useState(false);
  const [nameMsg, setNameMsg] = useState<Msg>(null);

  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [savingPw, setSavingPw] = useState(false);
  const [pwMsg, setPwMsg] = useState<Msg>(null);

  // 未登录 → 去登录页
  useEffect(() => {
    if (mounted && !loading && !user) router.replace("/login");
  }, [mounted, loading, user, router]);

  useEffect(() => {
    if (user) setName(user.name ?? "");
  }, [user]);

  if (!user) {
    return (
      <main className="flex min-h-[60vh] items-center justify-center text-muted-foreground">
        加载中…
      </main>
    );
  }

  const onSaveName = async (e: React.FormEvent) => {
    e.preventDefault();
    setNameMsg(null);
    setSavingName(true);
    try {
      await updateProfile({ name: name.trim() });
      await queryClient.invalidateQueries({ queryKey: ["auth-me"] });
      setNameMsg({ type: "ok", text: "已保存" });
    } catch (err) {
      setNameMsg({ type: "err", text: err instanceof Error ? err.message : "保存失败" });
    } finally {
      setSavingName(false);
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
    <main className="mx-auto max-w-2xl px-6 pb-20 pt-28">
      <h1 className="mb-8 text-3xl font-bold tracking-tight">个人设置</h1>

      <section className="mb-6 rounded-2xl border border-border bg-card p-6 shadow-sm">
        <h2 className="mb-4 text-lg font-semibold">个人资料</h2>
        <form onSubmit={onSaveName} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="email">邮箱</Label>
            <Input id="email" value={user.email} disabled className="h-11" />
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
          <FormMsg msg={nameMsg} />
          <Button type="submit" disabled={savingName}>
            {savingName ? "保存中…" : "保存"}
          </Button>
        </form>
      </section>

      <section className="rounded-2xl border border-border bg-card p-6 shadow-sm">
        <h2 className="mb-4 text-lg font-semibold">修改密码</h2>
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
          <FormMsg msg={pwMsg} />
          <Button type="submit" disabled={savingPw}>
            {savingPw ? "修改中…" : "修改密码"}
          </Button>
        </form>
      </section>
    </main>
  );
}
