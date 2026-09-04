"use client";

import { Check, Copy } from "lucide-react";
import React, { useState } from "react";

interface MarkdownMessageProps {
  content: string;
  isStreaming?: boolean;
  className?: string;
  onCitationClick?: (index: number) => void;
}

function CodeBlock({ language, code }: { language: string; code: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy code", err);
    }
  };

  return (
    <div className="my-3 overflow-hidden rounded-xl border border-zinc-200/80 bg-zinc-900 text-zinc-100 shadow-sm dark:border-white/[0.08]">
      {/* Code Header */}
      <div className="flex items-center justify-between border-b border-zinc-800 bg-zinc-950/70 px-3.5 py-1.5 text-xs text-zinc-400">
        <span className="font-mono text-[11px] font-medium text-zinc-300 lowercase">
          {language || "text"}
        </span>
        <button
          onClick={handleCopy}
          className="inline-flex items-center gap-1 rounded px-2 py-0.5 text-[11px] text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200 transition-colors"
        >
          {copied ? (
            <>
              <Check className="size-3 text-emerald-400" />
              <span className="text-emerald-400">已复制</span>
            </>
          ) : (
            <>
              <Copy className="size-3" />
              <span>复制</span>
            </>
          )}
        </button>
      </div>

      {/* Code Content */}
      <div className="overflow-x-auto p-3.5 font-mono text-xs leading-relaxed text-zinc-200">
        <pre>
          <code>{code}</code>
        </pre>
      </div>
    </div>
  );
}

/**
 * Parses inline formatting:
 * - Bold: `**bold**`
 * - Italic: `*italic*`
 * - Inline code: `` `code` ``
 * - Citation markers: `[^1]` or `[1]`
 */
function renderInline(text: string, onCitationClick?: (index: number) => void): React.ReactNode[] {
  // Regex to split by inline tokens
  const regex = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|\[\^?\d+\])/g;
  const parts = text.split(regex);

  return parts.map((part, i) => {
    if (!part) return null;

    // Bold
    if (part.startsWith("**") && part.endsWith("**") && part.length >= 4) {
      return (
        <strong key={i} className="font-semibold text-zinc-900 dark:text-zinc-100">
          {part.slice(2, -2)}
        </strong>
      );
    }

    // Italic
    if (part.startsWith("*") && part.endsWith("*") && part.length >= 2) {
      return (
        <em key={i} className="italic text-zinc-800 dark:text-zinc-200">
          {part.slice(1, -1)}
        </em>
      );
    }

    // Inline Code
    if (part.startsWith("`") && part.endsWith("`") && part.length >= 2) {
      return (
        <code
          key={i}
          className="rounded border border-zinc-200 bg-zinc-100 px-1.5 py-0.5 font-mono text-[11px] text-primary dark:border-zinc-800 dark:bg-zinc-800/60"
        >
          {part.slice(1, -1)}
        </code>
      );
    }

    // Citation badge: [^1] or [1]
    const citeMatch = part.match(/^\[\^?(\d+)\]$/);
    if (citeMatch) {
      const citeNum = parseInt(citeMatch[1], 10);
      return (
        <sup key={i} className="mx-0.5">
          <button
            type="button"
            onClick={() => onCitationClick?.(citeNum)}
            className="inline-flex size-4 items-center justify-center rounded-full bg-primary/10 font-mono text-[9px] font-bold text-primary hover:bg-primary/20 transition-colors"
            title={`查看引用来源 [${citeNum}]`}
          >
            {citeNum}
          </button>
        </sup>
      );
    }

    // Plain text
    return <React.Fragment key={i}>{part}</React.Fragment>;
  });
}

export function MarkdownMessage({
  content,
  isStreaming = false,
  className = "",
  onCitationClick,
}: MarkdownMessageProps) {
  // Normalize streaming markdown: if an unclosed ``` exists, close it for rendering
  let normalizedContent = content;
  const codeBlockMatches = content.match(/```/g);
  if (codeBlockMatches && codeBlockMatches.length % 2 !== 0) {
    normalizedContent += "\n```";
  }

  // Split by code blocks: ```lang ... ```
  const blockRegex = /(```[\s\S]*?```)/g;
  const segments = normalizedContent.split(blockRegex);

  return (
    <div className={`space-y-2 text-xs sm:text-sm leading-relaxed ${className}`}>
      {segments.map((segment, segIdx) => {
        if (!segment) return null;

        // Fenced Code Block
        if (segment.startsWith("```") && segment.endsWith("```")) {
          const lines = segment.slice(3, -3).split("\n");
          const language = lines[0]?.trim() || "";
          const code = (lines.length > 1 ? lines.slice(1).join("\n") : "").replace(/\n$/, "");
          return <CodeBlock key={segIdx} language={language} code={code} />;
        }

        // Regular Text & Paragraphs
        const paragraphs = segment.split("\n\n");
        return (
          <React.Fragment key={segIdx}>
            {paragraphs.map((p, pIdx) => {
              const trimmed = p.trim();
              if (!trimmed) return null;

              // Heading 1
              if (trimmed.startsWith("# ")) {
                return (
                  <h2 key={pIdx} className="text-base sm:text-lg font-bold text-zinc-900 dark:text-zinc-100 mt-4 mb-2">
                    {renderInline(trimmed.slice(2), onCitationClick)}
                  </h2>
                );
              }

              // Heading 2
              if (trimmed.startsWith("## ")) {
                return (
                  <h3 key={pIdx} className="text-sm sm:text-base font-bold text-zinc-900 dark:text-zinc-100 mt-3 mb-1.5">
                    {renderInline(trimmed.slice(3), onCitationClick)}
                  </h3>
                );
              }

              // Heading 3
              if (trimmed.startsWith("### ")) {
                return (
                  <h4 key={pIdx} className="text-xs sm:text-sm font-semibold text-zinc-900 dark:text-zinc-100 mt-2 mb-1">
                    {renderInline(trimmed.slice(4), onCitationClick)}
                  </h4>
                );
              }

              // Blockquote
              if (trimmed.startsWith("> ")) {
                return (
                  <blockquote
                    key={pIdx}
                    className="border-l-2 border-primary/50 pl-3 my-2 text-zinc-600 dark:text-zinc-400 italic text-xs"
                  >
                    {renderInline(trimmed.slice(2), onCitationClick)}
                  </blockquote>
                );
              }

              // Horizontal Rule
              if (trimmed === "---" || trimmed === "***") {
                return <hr key={pIdx} className="my-3 border-zinc-200 dark:border-white/[0.08]" />;
              }

              // List items (lines starting with - or * or number.)
              const lines = p.split("\n");
              const isList = lines.every((l) => /^(\s*[-*]|\s*\d+\.)\s+/.test(l.trim()));

              if (isList) {
                return (
                  <ul key={pIdx} className="my-2 list-disc list-inside space-y-1 pl-1">
                    {lines.map((l, lIdx) => {
                      const listText = l.replace(/^(\s*[-*]|\s*\d+\.)\s+/, "");
                      return (
                        <li key={lIdx} className="leading-relaxed">
                          {renderInline(listText, onCitationClick)}
                        </li>
                      );
                    })}
                  </ul>
                );
              }

              // Standard Paragraph with Line Breaks
              return (
                <p key={pIdx} className="leading-relaxed">
                  {lines.map((l, lIdx) => (
                    <React.Fragment key={lIdx}>
                      {renderInline(l, onCitationClick)}
                      {lIdx < lines.length - 1 && <br />}
                    </React.Fragment>
                  ))}
                </p>
              );
            })}
          </React.Fragment>
        );
      })}

      {/* Blinking Typewriter Cursor during streaming */}
      {isStreaming && (
        <span className="inline-block ml-0.5 h-3.5 w-1.5 animate-pulse bg-primary align-middle" />
      )}
    </div>
  );
}
