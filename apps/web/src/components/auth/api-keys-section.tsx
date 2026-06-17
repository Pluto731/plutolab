"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, Loader2, Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  type ApiKeyProvider,
  type ApiKeyPublic,
  createApiKey,
  deleteApiKey,
  listApiKeys,
} from "@/lib/auth";

const PROVIDERS: { value: ApiKeyProvider; label: string; gradient: string }[] = [
  { value: "anthropic", label: "Anthropic", gradient: "from-amber-500 to-orange-500" },
  { value: "openai", label: "OpenAI", gradient: "from-emerald-500 to-teal-500" },
  { value: "deepseek", label: "DeepSeek", gradient: "from-blue-500 to-violet-500" },
  { value: "replicate", label: "Replicate", gradient: "from-sky-500 to-indigo-500" },
];

function providerMeta(p: ApiKeyProvider) {
  return PROVIDERS.find((x) => x.value === p) ?? PROVIDERS[0];
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function ApiKeysSection() {
  const queryClient = useQueryClient();
  const { data: keys, isLoading } = useQuery<ApiKeyPublic[]>({
    queryKey: ["api-keys"],
    queryFn: listApiKeys,
    staleTime: 30 * 1000,
  });

  const [showForm, setShowForm] = useState(false);
  const [provider, setProvider] = useState<ApiKeyProvider>("anthropic");
  const [keyValue, setKeyValue] = useState("");
  const [label, setLabel] = useState("");
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState("");

  const refetch = () => queryClient.invalidateQueries({ queryKey: ["api-keys"] });

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setAdding(true);
    try {
      await createApiKey({ provider, key: keyValue, label: label.trim() || undefined });
      setKeyValue("");
      setLabel("");
      setShowForm(false);
      await refetch();
    } catch (err) {
      setError(err instanceof Error ? err.message : "添加失败");
    } finally {
      setAdding(false);
    }
  };

  const onDelete = async (id: string) => {
    if (!confirm("确定删除这个 API Key？删除后不可恢复。")) return;
    await deleteApiKey(id);
    await refetch();
  };

  return (
    <section className="rounded-2xl border border-border bg-card/80 p-6 shadow-sm backdrop-blur">
      <div className="mb-4 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <KeyRound className="size-5 text-amber-500" />
          <h2 className="text-lg font-semibold">API Keys</h2>
        </div>
        {!showForm && (
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setShowForm(true)}
          >
            <Plus className="mr-1 size-4" />
            添加
          </Button>
        )}
      </div>

      <p className="mb-4 text-sm text-muted-foreground">
        存你自己的 Anthropic / OpenAI / Replicate key，调用 LLM 时用。**服务端加密保存，明文不会返回**。
      </p>

      {/* 新增表单 — 折叠态 */}
      {showForm && (
        <form
          onSubmit={onSubmit}
          className="mb-5 space-y-3 rounded-xl border border-dashed border-border bg-background/50 p-4"
        >
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="provider">Provider</Label>
              <select
                id="provider"
                value={provider}
                onChange={(e) => setProvider(e.target.value as ApiKeyProvider)}
                className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-primary/40"
              >
                {PROVIDERS.map((p) => (
                  <option key={p.value} value={p.value}>
                    {p.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="label">备注 <span className="text-muted-foreground">（可选）</span></Label>
              <Input
                id="label"
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                placeholder="dev / prod / 个人"
                maxLength={50}
                className="h-10"
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="key">Key</Label>
            <Input
              id="key"
              type="password"
              value={keyValue}
              onChange={(e) => setKeyValue(e.target.value)}
              placeholder="sk-..."
              minLength={10}
              maxLength={200}
              required
              className="h-10 font-mono"
              autoComplete="off"
            />
            <p className="text-xs text-muted-foreground">
              立即用 Fernet 加密入库；服务端只保留密文 + 末 4 位预览。
            </p>
          </div>
          {error && (
            <p className="text-sm text-destructive">{error}</p>
          )}
          <div className="flex items-center gap-2">
            <Button type="submit" size="sm" disabled={adding}>
              {adding ? "加密中…" : "保存"}
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => {
                setShowForm(false);
                setKeyValue("");
                setLabel("");
                setError("");
              }}
            >
              取消
            </Button>
          </div>
        </form>
      )}

      {/* 列表 */}
      {isLoading ? (
        <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
          <Loader2 className="mr-2 size-4 animate-spin" /> 加载中…
        </div>
      ) : !keys || keys.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border py-10 text-center text-sm text-muted-foreground">
          还没有 API Key — 点右上「添加」开始
        </div>
      ) : (
        <ul className="divide-y divide-border">
          {keys.map((k) => {
            const meta = providerMeta(k.provider);
            return (
              <li key={k.id} className="flex items-center gap-3 py-3">
                <span
                  className={`inline-flex h-7 items-center rounded-full bg-gradient-to-br ${meta.gradient} px-2.5 text-xs font-semibold text-white shadow-sm`}
                >
                  {meta.label}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="flex items-center gap-2 font-mono text-sm">
                    <span className="text-muted-foreground">sk-…</span>
                    <span className="font-semibold">{k.key_preview}</span>
                    {k.label && (
                      <span className="rounded bg-muted px-1.5 py-0.5 font-sans text-xs text-muted-foreground">
                        {k.label}
                      </span>
                    )}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    添加于 {formatDate(k.created_at)}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => onDelete(k.id)}
                  className="rounded-lg p-2 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
                  aria-label="删除"
                >
                  <Trash2 className="size-4" />
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
