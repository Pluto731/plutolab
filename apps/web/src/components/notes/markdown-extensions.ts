"use client";

import { css } from "@codemirror/lang-css";
import { html } from "@codemirror/lang-html";
import { javascript } from "@codemirror/lang-javascript";
import { json } from "@codemirror/lang-json";
import { python } from "@codemirror/lang-python";
import { LanguageDescription, syntaxTree } from "@codemirror/language";
import { type Range, RangeSetBuilder } from "@codemirror/state";
import {
  Decoration,
  type DecorationSet,
  type EditorView,
  ViewPlugin,
  type ViewUpdate,
  WidgetType,
} from "@codemirror/view";

/**
 * Markdown 编辑器扩展 — Phase 3.1.polish A.2-a + A.2-b 稳定重写
 *
 * 设计要点 (回应上一版 6494fce 浏览器崩页问题):
 *   1. line decoration (代码块底色 + markup 隐藏) 和 widget block (chrome 条) 拆到
 *      两个独立 ViewPlugin, 避免同一 position 两类 decoration 的排序冲突.
 *   2. 每个 plugin 的 buildXxxDecorations 全包 try/catch, 抛错时返 Decoration.none
 *      不让整个编辑器崩 (用户最多看不到装饰, 不会整页挂).
 *   3. line decoration 用 RangeSetBuilder + 显式升序遍历, 替代 Decoration.set(_, true)
 *      自动 sort, 排除自动排序边界异常.
 */

// 多语言注册 — 5 个最常用. 未列出语言走默认 monospace 无高亮.
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

// lezer-markdown markup node 名速查
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

/* ─── Plugin 1: markup 隐藏 + 代码块行底色 (line decoration only) ─── */

function buildLineDecorations(view: EditorView): DecorationSet {
  const items: { from: number; to: number; deco: Decoration; orderKey: number }[] = [];
  try {
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
          if (node.name === "FencedCode") {
            const startLine = view.state.doc.lineAt(node.from);
            const endLine = view.state.doc.lineAt(node.to);
            for (let n = startLine.number; n <= endLine.number; n++) {
              const line = view.state.doc.line(n);
              const d =
                n === startLine.number
                  ? codeBlockFirstLine
                  : n === endLine.number
                    ? codeBlockLastLine
                    : codeBlockLine;
              items.push({ from: line.from, to: line.from, deco: d, orderKey: 0 });
            }
          }
          if (MARKUP_NODES.has(node.name)) {
            const nodeLine = view.state.doc.lineAt(node.from).number;
            if (nodeLine < selStart || nodeLine > selEnd) {
              items.push({
                from: node.from,
                to: node.to,
                deco: hideDeco,
                orderKey: 1,
              });
            }
          }
        },
      });
    }
  } catch (err) {
    console.error("[markdown line decorations]", err);
    return Decoration.none;
  }

  // 严格按 from 升序; 同 from 时 line decoration (orderKey 0) 在前
  items.sort((a, b) => a.from - b.from || a.orderKey - b.orderKey || a.to - b.to);
  const builder = new RangeSetBuilder<Decoration>();
  for (const { from, to, deco } of items) {
    builder.add(from, to, deco);
  }
  return builder.finish();
}

export const markdownLiveDecorations = ViewPlugin.fromClass(
  class {
    decorations: DecorationSet;
    constructor(view: EditorView) {
      this.decorations = buildLineDecorations(view);
    }
    update(update: ViewUpdate) {
      if (update.docChanged || update.viewportChanged || update.selectionSet) {
        this.decorations = buildLineDecorations(update.view);
      }
    }
  },
  {
    decorations: (v) => v.decorations,
  },
);

/* ─── Plugin 2: 代码块顶部 chrome (widget block only) ─── */

class CodeBlockChromeWidget extends WidgetType {
  constructor(
    readonly language: string,
    readonly code: string,
  ) {
    super();
  }

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
    path.setAttribute(
      "d",
      "M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2",
    );
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

  ignoreEvent(): boolean {
    return true;
  }
}

function buildChromeDecorations(view: EditorView): DecorationSet {
  const items: Range<Decoration>[] = [];
  try {
    for (const { from, to } of view.visibleRanges) {
      syntaxTree(view.state).iterate({
        from,
        to,
        enter: (node) => {
          if (node.name !== "FencedCode") return;

          let language = "";
          let codeText = "";
          const fullNode = node.node;
          const infoChild = fullNode.getChild("CodeInfo");
          if (infoChild) {
            language = view.state.doc
              .sliceString(infoChild.from, infoChild.to)
              .trim();
          }
          const textChild = fullNode.getChild("CodeText");
          if (textChild) {
            codeText = view.state.doc.sliceString(textChild.from, textChild.to);
          }

          const startLine = view.state.doc.lineAt(node.from);
          items.push(
            Decoration.widget({
              widget: new CodeBlockChromeWidget(language, codeText),
              block: true,
              side: -1,
            }).range(startLine.from),
          );
        },
      });
    }
  } catch (err) {
    console.error("[markdown chrome widget]", err);
    return Decoration.none;
  }
  items.sort((a, b) => a.from - b.from);
  return Decoration.set(items);
}

export const codeBlockChromeDecorations = ViewPlugin.fromClass(
  class {
    decorations: DecorationSet;
    constructor(view: EditorView) {
      this.decorations = buildChromeDecorations(view);
    }
    update(update: ViewUpdate) {
      if (update.docChanged || update.viewportChanged) {
        this.decorations = buildChromeDecorations(update.view);
      }
    }
  },
  {
    decorations: (v) => v.decorations,
  },
);
