"use client";

import { Loader2 } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { githubLogin, storeTokens } from "@/lib/auth";

export default function GitHubCallbackPage() {
  const [error, setError] = useState("");
  const ran = useRef(false);

  useEffect(() => {
    if (ran.current) return; // 防 React StrictMode 双跑 (code 只能用一次)
    ran.current = true;

    const params = new URLSearchParams(window.location.search);
    const code = params.get("code");
    const state = params.get("state");
    const savedState = sessionStorage.getItem("gh_oauth_state");
    sessionStorage.removeItem("gh_oauth_state");

    if (params.get("error")) {
      setError("已取消 GitHub 授权");
      return;
    }
    if (!code || !state || state !== savedState) {
      setError("授权校验失败，请重试");
      return;
    }

    const redirectUri = `${window.location.origin}/auth/github/callback`;
    githubLogin(code, redirectUri)
      .then((tokens) => {
        storeTokens(tokens);
        window.location.assign("/dashboard");
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "GitHub 登录失败");
      });
  }, []);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 px-6 text-center">
      {error ? (
        <>
          <p className="text-destructive">{error}</p>
          <Link href="/login" className="text-sm font-medium text-primary hover:underline">
            返回登录
          </Link>
        </>
      ) : (
        <p className="flex items-center gap-2 text-muted-foreground">
          <Loader2 className="size-5 animate-spin" /> 正在用 GitHub 登录…
        </p>
      )}
    </div>
  );
}
