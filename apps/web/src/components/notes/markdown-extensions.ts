"use client";

import { css } from "@codemirror/lang-css";
import { html } from "@codemirror/lang-html";
import { javascript } from "@codemirror/lang-javascript";
import { json } from "@codemirror/lang-json";
import { python } from "@codemirror/lang-python";
import { LanguageDescription, syntaxTree } from "@codemirror/language";
import { type Range } from "@codemirror/state";
import {
  Decoration,
  type DecorationSet,
  type EditorView,
  ViewPlugin,
  type ViewUpdate,
  WidgetType,
} from "@codemirror/view";

/**
 * Markdown 编辑器装饰扩展 — Phase 3.1.polish A.2-a + A.2-b
 *
 * 三件事:
 *   1. fenced code block 顶部 chrome 条 (语言名 chip + 复制按钮)
 *   2. fenced code block 整段底色 + 圆角框
 *   3. 非光标行 markdown markup 字符 (# ** > ` 等) 隐藏 (Bear live preview)
 *
 * 多语言语法高亮: 通过 LanguageDescription 注入 5 个常用语言, 自动
 * 在 ```lang 之后切换高亮 (markdown extension 自带 codeLanguages 钩子).
 */

// 多语言支持 — 5 个最常用. 未列出语言走默认 monospace 无高亮.
export const codeLanguages: LanguageDescription[] = [
  LanguageDescription.of({
    name: "Python",
    alias: ["python", "py"],
    async load() {
      return python();
    },
  }),
  LanguageDescription.of({
    name: "JavaScript",
    alias: ["javascript", "js", "jsx"],
    async load() {
      return javascript({ jsx: true });
    },
  }),
  LanguageDescription.of({
    name: "TypeScript",
    alias: ["typescript", "ts", "tsx"],
    async load() {
      return javascript({ jsx: true, typescript: true });
    },
  }),
  LanguageDescription.of({
    name: "HTML",
    alias: ["html"],
    async load() {
      return html();
    },
  }),
  LanguageDescription.of({
    name: "CSS",
    alias: ["css"],
    async load() {
      return css();
    },
  }),
  LanguageDescription.of({
    name: "JSON",
    alias: ["json"],
    async load() {
      return json();
    },
  }),
];

// lezer-markdown markup node 速查
const MARKUP_NODES = new Set([
  "HeaderMark",
  "EmphasisMark",
  "QuoteMark",
  "ListMark",
  "LinkMark",
  "CodeMark",
  "CodeInfo",
  "StrikethroughMark",
]);

const hideDeco = Decoration.replace({});
const codeBlockLine = Decoration.line({ class: "cm-md-code-block-line" });
const codeBlockFirstLine = Decoration.line({
  class: "cm-md-code-block-line cm-md-code-block-line-first",
});
const codeBlockLastLine = Decoration.line({
  class: "cm-md-code-block-line cm-md-code-block-line-last",
});

/** 代码块顶部 chrome 条 widget — 语言 chip + 复制按钮 */
class CodeBlockChromeWidget extends WidgetType {
  constructor(
    readonly language: string,
    readonly code: string,
  ) {
    super();
  }

  // 让 CM 仅在内容真变时重建 DOM
  eq(other: CodeBlockChromeWidget): boolean {
    return other.language === this.language && other.code === this.code;
  }

  toDOM(): HTMLElement {
    const wrap = document.createElement("div");
    wrap.className = "cm-md-code-chrome";
    wrap.contentEditable = "false";

    const lang = document.createElement("span");
    lang.className = "cm-md-code-chrome-lang";
    lang.textContent = this.language.trim() || "code";
    wrap.appendChild(lang);

    const copy = document.createElement("button");
    copy.type = "button";
    copy.className = "cm-md-code-chrome-copy";
    copy.setAttribute("aria-label", "复制代码");

    // 用 DOM API 构造 SVG (避免 innerHTML, 即使内容是常量也走安全路径)
    const SVG_NS = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(SVG_NS, "svg");
    svg.setAttribute("width", "12");
    svg.setAttribute("height", "12");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("fill", "none");
    svg.setAttribute("stroke", "currentColor");
    svg.setAttribute("stroke-width", "2");
    svg.setAttribute("stroke-linecap", "round");
    svg.setAttribute("stroke-linejoin", "round");
    svg.setAttribute("aria-hidden", "true");
    const rect = document.createElementNS(SVG_NS, "rect");
    rect.setAttribute("width", "14");
    rect.setAttribute("height", "14");
    rect.setAttribute("x", "8");
    rect.setAttribute("y", "8");
    rect.setAttribute("rx", "2");
    rect.setAttribute("ry", "2");
    svg.appendChild(rect);
    const path = document.createElementNS(SVG_NS, "path");
    path.setAttribute("d", "M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2");
    svg.appendChild(path);
    copy.appendChild(svg);

    const label = document.createElement("span");
    label.textContent = "复制";
    copy.appendChild(label);

    const codeToCopy = this.code;
    copy.addEventListener("click", async (e) => {
      e.stopPropagation();
      e.preventDefault();
      try {
        await navigator.clipboard.writeText(codeToCopy);
        copy.classList.add("copied");
        label.textContent = "已复制";
        setTimeout(() => {
          copy.classList.remove("copied");
          label.textContent = "复制";
        }, 1400);
      } catch {
        // 非 secure context / 权限被拒, 静默
      }
    });
    wrap.appendChild(copy);

    return wrap;
  }

  // 让 widget 不接受 CodeMirror 内部事件 (点击不会进入编辑)
  ignoreEvent(): boolean {
    return true;
  }
}

function buildDecorations(view: EditorView): DecorationSet {
  const decorations: Range<Decoration>[] = [];
  const sel = view.state.selection.main;
  const cursorLine = view.state.doc.lineAt(sel.head).number;
  const anchorLine = view.state.doc.lineAt(sel.anchor).number;
  const selStart = Math.min(cursorLine, anchorLine);
  const selEnd = Math.max(cursorLine, anchorLine);

  for (const { from, to } of view.visibleRanges) {
    syntaxTree(view.state).iterate({
      from,
      to,
      enter: (node) => {
        // fenced code block — 顶部 chrome widget + 整段 line decoration
        if (node.name === "FencedCode") {
          const startLine = view.state.doc.lineAt(node.from);
          const endLine = view.state.doc.lineAt(node.to);

          // 提取 language (CodeInfo 子节点) 和 代码 (CodeText 子节点)
          let language = "";
          let codeText = "";
          const infoChild = node.node.getChild("CodeInfo");
          if (infoChild) {
            language = view.state.doc
              .sliceString(infoChild.from, infoChild.to)
              .trim();
          }
          const textChild = node.node.getChild("CodeText");
          if (textChild) {
            codeText = view.state.doc.sliceString(textChild.from, textChild.to);
          }

          // chrome widget 插在 first line 之前 (side -1)
          decorations.push(
            Decoration.widget({
              widget: new CodeBlockChromeWidget(language, codeText),
              block: true,
              side: -1,
            }).range(startLine.from),
          );

          // 整段每行 line decoration (底色 + 边框)
          for (let n = startLine.number; n <= endLine.number; n++) {
            const line = view.state.doc.line(n);
            const deco =
              n === startLine.number
                ? codeBlockFirstLine
                : n === endLine.number
                  ? codeBlockLastLine
                  : codeBlockLine;
            decorations.push(deco.range(line.from));
          }
          // 不 return — 继续 iterate children, 让 CodeMark / CodeInfo 被隐藏处理
        }

        // markup 隐藏 — 选区行 (含光标行) 之外才隐藏
        if (MARKUP_NODES.has(node.name)) {
          const nodeLine = view.state.doc.lineAt(node.from).number;
          if (nodeLine < selStart || nodeLine > selEnd) {
            decorations.push(hideDeco.range(node.from, node.to));
          }
        }
      },
    });
  }
  return Decoration.set(decorations, true);
}

export const markdownLiveDecorations = ViewPlugin.fromClass(
  class {
    decorations: DecorationSet;
    constructor(view: EditorView) {
      this.decorations = buildDecorations(view);
    }
    update(update: ViewUpdate) {
      if (update.docChanged || update.viewportChanged || update.selectionSet) {
        this.decorations = buildDecorations(update.view);
      }
    }
  },
  {
    decorations: (v) => v.decorations,
  },
);
