"use client";

import { markdown, markdownLanguage } from "@codemirror/lang-markdown";
import { HighlightStyle, syntaxHighlighting } from "@codemirror/language";
import { EditorView } from "@codemirror/view";
import { tags as t } from "@lezer/highlight";
import CodeMirror from "@uiw/react-codemirror";
import { useTheme } from "next-themes";
import { useMemo } from "react";

import { markdownLiveDecorations } from "./markdown-extensions";

/**
 * Markdown 编辑器 — Phase 3.1.polish A.2-a.
 *
 * 基于 CodeMirror 6 + @codemirror/lang-markdown 自定义 syntax highlighting:
 *   - 标题 (#/##/###) → Lora 衬线字 + 阶梯字号
 *   - **加粗** → font-weight 700
 *   - *斜体* → font-style italic
 *   - `行内 code` → 紫底等宽字
 *   - [链接](url) → 紫色下划线
 *   - > 引文 → 灰斜体
 *   - markup 字符 (# / ** / `) 浅淡, 不抢主视觉
 *
 * Bear / Typora 风格的 source mode + decoration, 不是 wysiwyg.
 * 代码块多语言高亮 / 复制按钮 / 专注模式 → A.2-b.
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
  // markup 字符 (# * > ` 等)
  { tag: t.processingInstruction, class: "cm-md-mark" },
  { tag: t.meta, class: "cm-md-mark" },
]);

// 透明背景 + 继承父级字体 (让 Tailwind 控制)
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
    // caret 颜色由 .cm-cursor border-left 控制 (globals.css), 这里只关 caret-color 属性
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
  // selection
  ".cm-selectionBackground, ::selection": {
    backgroundColor: "oklch(0.7 0.2 320 / 0.22) !important",
  },
  // caret — 细一点 (1.5px) 品牌紫
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

  // 扩展列表 — markdownLiveDecorations 在 syntaxHighlighting 之后, 让 line decoration 覆盖
  const extensions = useMemo(
    () => [
      markdown({ base: markdownLanguage }),
      syntaxHighlighting(markdownHighlightStyle),
      markdownLiveDecorations,
      editorTheme,
      EditorView.lineWrapping,
      EditorView.contentAttributes.of({
        "data-placeholder": placeholder ?? "",
        spellcheck: "false",
      }),
    ],
    [placeholder],
  );

  return (
    <CodeMirror
      value={value}
      onChange={onChange}
      autoFocus={autoFocus}
      extensions={extensions}
      theme={isDark ? "dark" : "light"}
      basicSetup={{
        lineNumbers: false,
        foldGutter: false,
        // A.2-b C.1: 打开 active line 类供后续 focus mode 用; 默认黄底由 CSS 透明覆盖
        highlightActiveLine: true,
        highlightActiveLineGutter: false,
        searchKeymap: false,
        bracketMatching: false,
        autocompletion: false,
        indentOnInput: false,
      }}
      className={className}
    />
  );
}
