"use client";

import { markdown, markdownLanguage } from "@codemirror/lang-markdown";
import { HighlightStyle, syntaxHighlighting } from "@codemirror/language";
import { EditorView } from "@codemirror/view";
import { tags as t } from "@lezer/highlight";
import CodeMirror from "@uiw/react-codemirror";
import { Sparkles } from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useMemo, useRef, useState } from "react";

import {
  codeBlockChromeDecorations,
  codeLanguages,
  markdownLiveDecorations,
} from "./markdown-extensions";

/**
 * Markdown 编辑器 — Phase 3.1.polish A.2-a + A.2-b 稳定版.
 *
 * 视觉:
 *   - 标题 (#/##/###) → Lora 衬线字 + 阶梯字号
 *   - **加粗** → font-weight 700
 *   - *斜体* → font-style italic
 *   - `行内 code` → 紫底等宽字
 *   - [链接](url) → 紫色下划线
 *   - > 引文 → 灰斜体
 *   - markup 字符 (# / ** / `) 非光标行隐藏 (Bear live preview)
 *   - fenced code block: 顶部 chrome 条 (语言 chip + 复制按钮) + 整段紫淡底
 *   - 多语言高亮: Python / JS / TS / HTML / CSS / JSON
 *   - ⌘. / Ctrl+. 专注模式 (光标行清晰其他淡)
 */
const markdownHighlightStyle = HighlightStyle.define([
  { tag: t.heading1, class: "cm-md-h1" },
  { tag: t.heading2, class: "cm-md-h2" },
  { tag: t.heading3, class: "cm-md-h3" },
  { tag: t.heading4, class: "cm-md-h4" },
  { tag: t.heading5, class: "cm-md-h5" },
  { tag: t.heading6, class: "cm-md-h6" },
  { tag: t.strong, class: "cm-md-strong" },
  { tag: t.emphasis, class: "cm-md-em" },
  { tag: t.strikethrough, class: "cm-md-strike" },
  { tag: t.monospace, class: "cm-md-code-inline" },
  { tag: t.link, class: "cm-md-link" },
  { tag: t.url, class: "cm-md-url" },
  { tag: t.quote, class: "cm-md-quote" },
  { tag: t.list, class: "cm-md-list" },
  { tag: t.contentSeparator, class: "cm-md-hr" },
  { tag: t.processingInstruction, class: "cm-md-mark" },
  { tag: t.meta, class: "cm-md-mark" },
]);

const editorTheme = EditorView.theme({
  "&": {
    backgroundColor: "transparent",
    color: "inherit",
    fontSize: "15px",
    height: "100%",
  },
  ".cm-content": {
    fontFamily: "inherit",
    padding: "16px 0",
    caretColor: "transparent",
  },
  ".cm-line": {
    padding: "0 4px",
  },
  "&.cm-focused": {
    outline: "none",
  },
  ".cm-scroller": {
    fontFamily: "inherit",
    lineHeight: "1.7",
  },
  ".cm-selectionBackground, ::selection": {
    backgroundColor: "oklch(0.7 0.2 320 / 0.22) !important",
  },
  ".cm-cursor, .cm-dropCursor": {
    borderLeftWidth: "1.5px",
    borderLeftColor: "oklch(0.55 0.2 285)",
  },
});

interface NoteEditorProps {
  value: string;
  onChange: (v: string) => void;
  className?: string;
  autoFocus?: boolean;
  placeholder?: string;
}

export function NoteEditor({
  value,
  onChange,
  className,
  autoFocus,
  placeholder,
}: NoteEditorProps) {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";

  // 扩展列表 — line decoration / chrome widget 拆两个独立 plugin 互不干扰
  const extensions = useMemo(
    () => [
      markdown({ base: markdownLanguage, codeLanguages }),
      syntaxHighlighting(markdownHighlightStyle),
      markdownLiveDecorations,
      codeBlockChromeDecorations,
      editorTheme,
      EditorView.lineWrapping,
      EditorView.contentAttributes.of({
        "data-placeholder": placeholder ?? "",
        spellcheck: "false",
      }),
    ],
    [placeholder],
  );

  // ⌘. / Ctrl+. 切换专注模式 (仅在编辑器内获焦时响应)
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const [focusMode, setFocusMode] = useState(false);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === ".") {
        const root = wrapRef.current;
        if (!root) return;
        const inEditor = root.contains(document.activeElement);
        if (!inEditor) return;
        e.preventDefault();
        setFocusMode((v) => !v);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div
      ref={wrapRef}
      data-focus-mode={focusMode ? "true" : "false"}
      className="relative h-full"
    >
      <CodeMirror
        value={value}
        onChange={onChange}
        autoFocus={autoFocus}
        extensions={extensions}
        theme={isDark ? "dark" : "light"}
        basicSetup={{
          lineNumbers: false,
          foldGutter: false,
          // 必须 true 才有 .cm-activeLine class 让 focus mode CSS 工作
          highlightActiveLine: true,
          highlightActiveLineGutter: false,
          searchKeymap: false,
          bracketMatching: false,
          autocompletion: false,
          indentOnInput: false,
        }}
        className={className}
      />
      {focusMode && (
        <div className="pointer-events-none absolute right-2 top-2 z-20 inline-flex items-center gap-1.5 rounded-full border border-violet-500/30 bg-violet-500/10 px-2.5 py-1 text-[10px] font-medium text-violet-700 backdrop-blur dark:text-violet-300">
          <Sparkles className="size-3" />
          专注模式 · ⌘. 退出
        </div>
      )}
    </div>
  );
}
