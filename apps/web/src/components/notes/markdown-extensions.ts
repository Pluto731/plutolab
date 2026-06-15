"use client";

import { syntaxTree } from "@codemirror/language";
import { type Range } from "@codemirror/state";
import {
  Decoration,
  type DecorationSet,
  type EditorView,
  ViewPlugin,
  type ViewUpdate,
} from "@codemirror/view";

/**
 * Markdown 装饰扩展 — Phase 3.1.polish A.2-a 升级 (Bear 风格 live preview)
 *
 * 两件事:
 *   1. fenced code block 整段加底色 + 圆角框 + 等宽字
 *   2. 非光标行的 markdown markup 字符 (# / ** / > / ` / [ ] 等) 隐藏,
 *      只显示渲染后的视觉. 光标移到该行 → markup 显示出来让用户改.
 *
 * 实现: 一个 ViewPlugin, 监听 docChanged / viewportChanged / selectionSet,
 * 用 syntaxTree.iterate 找节点, 用 RangeSet 合并 line decoration + replace decoration.
 *
 * lezer-markdown 的 markup node 名速查:
 *   HeaderMark      → # / ## / ###
 *   EmphasisMark    → * / _ / ** / __
 *   QuoteMark       → >
 *   ListMark        → - / * / 1.
 *   LinkMark        → [ ] ( )
 *   CodeMark        → `
 *   CodeInfo        → ``` 后语言名
 *   StrikethroughMark → ~~
 */
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

function buildDecorations(view: EditorView): DecorationSet {
  const decorations: Range<Decoration>[] = [];
  const sel = view.state.selection.main;
  const cursorLine = view.state.doc.lineAt(sel.head).number;
  // 选区跨多行时, 选区内每行都视为"光标行" (markup 都显示)
  const anchorLine = view.state.doc.lineAt(sel.anchor).number;
  const selStart = Math.min(cursorLine, anchorLine);
  const selEnd = Math.max(cursorLine, anchorLine);

  for (const { from, to } of view.visibleRanges) {
    syntaxTree(view.state).iterate({
      from,
      to,
      enter: (node) => {
        // fenced code block — 给整段每行加底色 + 首/尾行加圆角边
        if (node.name === "FencedCode") {
          const startLine = view.state.doc.lineAt(node.from);
          const endLine = view.state.doc.lineAt(node.to);
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
          // 不 return — 继续 iterate children, 让 CodeMark (```) 也被隐藏处理
        }

        // markup 隐藏 — 非选区行 (含光标行) 才隐藏
        if (MARKUP_NODES.has(node.name)) {
          const nodeLine = view.state.doc.lineAt(node.from).number;
          if (nodeLine < selStart || nodeLine > selEnd) {
            decorations.push(hideDeco.range(node.from, node.to));
          }
        }
      },
    });
  }
  // sort=true 让 CM 自动按 from 排序 (line decoration + inline 交错时必须)
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
