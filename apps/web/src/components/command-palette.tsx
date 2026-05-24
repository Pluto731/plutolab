"use client";

import { Command } from "cmdk";
import {
  Code2,
  ExternalLink,
  FileSearch,
  FileText,
  Github,
  GitPullRequest,
  Home,
  Image as ImageIcon,
  Search,
  StickyNote,
  Workflow,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

type Item = {
  id: string;
  label: string;
  hint?: string;
  icon: typeof Home;
  href: string;
  external?: boolean;
  keywords?: string;
};

const navItems: Item[] = [
  { id: "home", label: "首页", icon: Home, href: "/", keywords: "home index 主页" },
  { id: "notes", label: "智能笔记", hint: "Markdown / 标签 / 搜索 / AI 总结", icon: StickyNote, href: "/notes", keywords: "notes markdown 笔记 phase 3" },
  { id: "rag", label: "RAG 文档问答", hint: "PDF / Word / 向量检索", icon: FileSearch, href: "/rag", keywords: "rag pdf 文档 问答 phase 4" },
  { id: "review", label: "AI 代码评审", hint: "GitHub PR / Claude 审查", icon: GitPullRequest, href: "/review", keywords: "review pr code 评审 phase 5" },
  { id: "agents", label: "多 Agent 协作", hint: "可视化工作流编排", icon: Workflow, href: "/agents", keywords: "agents 多智能体 workflow phase 6" },
  { id: "gallery", label: "画作收藏", hint: "Pixiv 风画廊 / AI 打标", icon: ImageIcon, href: "/gallery", keywords: "gallery 画廊 pixiv 收藏 phase 7" },
];

const externalItems: Item[] = [
  { id: "docs", label: "API 文档 (Swagger)", hint: "OpenAPI · 在线试调", icon: FileText, href: "/docs", external: true, keywords: "swagger api openapi" },
  { id: "redoc", label: "API 文档 (ReDoc)", hint: "更美观的 API 浏览器", icon: Code2, href: "/redoc", external: true, keywords: "redoc api" },
  { id: "github", label: "GitHub 仓库", hint: "源码 · star · 提 issue", icon: Github, href: "https://github.com/Pluto731/plutolab", external: true, keywords: "github source 仓库 star" },
];

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const router = useRouter();

  // 全局监听 cmd+k / ctrl+k
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((v) => !v);
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, []);

  const handleSelect = useCallback(
    (item: Item) => {
      setOpen(false);
      if (item.external) {
        window.open(item.href, "_blank", "noopener,noreferrer");
      } else {
        router.push(item.href);
      }
    },
    [router],
  );

  return (
    <Command.Dialog
      open={open}
      onOpenChange={setOpen}
      label="命令面板"
      shouldFilter
      className="fixed inset-0 z-[100] flex items-start justify-center pt-[15vh]"
    >
      {/* 遮罩层 — 点击关闭 */}
      <button
        type="button"
        aria-label="关闭命令面板"
        onClick={() => setOpen(false)}
        className="absolute inset-0 bg-black/30 backdrop-blur-sm dark:bg-black/50"
      />

      {/* 面板主体 */}
      <div
        className="relative w-full max-w-2xl mx-4 overflow-hidden rounded-2xl border border-white/40 bg-white/80 backdrop-blur-2xl
                   shadow-[inset_0_1px_0_0_rgba(255,255,255,0.8),0_30px_60px_-15px_rgba(0,0,0,0.25)]
                   dark:border-white/[0.08] dark:bg-zinc-950/85
                   dark:shadow-[inset_0_1px_0_0_rgba(255,255,255,0.06),0_30px_60px_-15px_rgba(0,0,0,0.7)]"
      >
        {/* 搜索输入框 */}
        <div className="flex items-center gap-3 border-b border-zinc-200/60 px-4 dark:border-zinc-800/60">
          <Search className="size-4 shrink-0 text-zinc-400" />
          <Command.Input
            placeholder="搜索页面 · 文档 · 命令..."
            className="h-14 w-full bg-transparent text-base text-zinc-900 placeholder:text-zinc-400 focus:outline-none dark:text-zinc-100"
          />
          <kbd className="hidden shrink-0 items-center gap-1 rounded border border-zinc-200/60 bg-zinc-100/60 px-1.5 py-0.5 font-mono text-[10px] text-zinc-500 sm:inline-flex dark:border-zinc-700 dark:bg-zinc-800/60 dark:text-zinc-400">
            ESC
          </kbd>
        </div>

        {/* 结果列表 */}
        <Command.List className="max-h-[60vh] overflow-y-auto p-2">
          <Command.Empty className="py-12 text-center text-sm text-zinc-500 dark:text-zinc-400">
            没找到相关结果 · 试试 "笔记" / "rag" / "github"
          </Command.Empty>

          <Command.Group
            heading="导航"
            className="px-2 pb-1 pt-2 text-xs font-semibold tracking-wider text-zinc-500 uppercase dark:text-zinc-400 [&_[cmdk-group-items]]:mt-1 [&_[cmdk-group-items]]:flex [&_[cmdk-group-items]]:flex-col [&_[cmdk-group-items]]:gap-0.5"
          >
            {navItems.map((item) => (
              <CommandItem key={item.id} item={item} onSelect={handleSelect} />
            ))}
          </Command.Group>

          <Command.Group
            heading="外部链接"
            className="px-2 pt-3 pb-2 text-xs font-semibold tracking-wider text-zinc-500 uppercase dark:text-zinc-400 [&_[cmdk-group-items]]:mt-1 [&_[cmdk-group-items]]:flex [&_[cmdk-group-items]]:flex-col [&_[cmdk-group-items]]:gap-0.5"
          >
            {externalItems.map((item) => (
              <CommandItem key={item.id} item={item} onSelect={handleSelect} />
            ))}
          </Command.Group>
        </Command.List>

        {/* 底部快捷键提示 */}
        <div className="flex items-center justify-between border-t border-zinc-200/60 bg-zinc-50/40 px-4 py-2.5 text-xs text-zinc-500 dark:border-zinc-800/60 dark:bg-zinc-900/40 dark:text-zinc-400">
          <div className="flex items-center gap-3">
            <ShortcutHint keys={["↑", "↓"]} label="选择" />
            <ShortcutHint keys={["↵"]} label="跳转" />
            <ShortcutHint keys={["ESC"]} label="关闭" />
          </div>
          <span className="font-mono">
            <span className="text-zinc-700 dark:text-zinc-300">⌘K</span> 随时召唤
          </span>
        </div>
      </div>
    </Command.Dialog>
  );
}

function CommandItem({
  item,
  onSelect,
}: {
  item: Item;
  onSelect: (item: Item) => void;
}) {
  const Icon = item.icon;
  return (
    <Command.Item
      value={`${item.label} ${item.keywords ?? ""}`}
      onSelect={() => onSelect(item)}
      className="group flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2.5
                 data-[selected=true]:bg-gradient-to-r data-[selected=true]:from-violet-500/15 data-[selected=true]:to-fuchsia-500/15
                 dark:data-[selected=true]:from-violet-500/20 dark:data-[selected=true]:to-fuchsia-500/20"
    >
      <Icon className="size-4 shrink-0 text-zinc-500 group-data-[selected=true]:text-violet-500 dark:text-zinc-400 dark:group-data-[selected=true]:text-violet-400" />
      <div className="flex flex-1 flex-col">
        <span className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
          {item.label}
        </span>
        {item.hint && (
          <span className="text-xs text-zinc-500 dark:text-zinc-400">
            {item.hint}
          </span>
        )}
      </div>
      {item.external && (
        <ExternalLink className="size-3.5 shrink-0 text-zinc-400 dark:text-zinc-500" />
      )}
    </Command.Item>
  );
}

function ShortcutHint({ keys, label }: { keys: string[]; label: string }) {
  return (
    <span className="flex items-center gap-1">
      {keys.map((k) => (
        <kbd
          key={k}
          className="inline-flex h-5 min-w-5 items-center justify-center rounded border border-zinc-200/80 bg-white/80 px-1 font-mono text-[10px] text-zinc-700 dark:border-zinc-700 dark:bg-zinc-800/80 dark:text-zinc-300"
        >
          {k}
        </kbd>
      ))}
      <span>{label}</span>
    </span>
  );
}
