import type { Metadata } from "next";
import { Geist, Geist_Mono, Lora } from "next/font/google";

import { QueryProvider } from "@/components/query-provider";
import { ThemeProvider } from "@/components/theme-provider";

import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

// Phase 3.1.polish A.1-4: 笔记标题用 Lora 衬线字, 读书感
// 中文 fallback 到系统衬线 (Songti / 宋体), Lora 不含中文 glyph
const lora = Lora({
  variable: "--font-serif",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "PlutoLab — Your AI Workshop",
  description: "一站式 AI 工作台：RAG 问答 / AI 代码评审 / 多 Agent / 笔记 / 画作收藏",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="zh-CN"
      suppressHydrationWarning
      className={`${geistSans.variable} ${geistMono.variable} ${lora.variable} h-full antialiased`}
    >
      <body className="relative min-h-full overflow-x-hidden">
        <ThemeProvider
          attribute="class"
          defaultTheme="dark"
          enableSystem
        >
          {/* 视觉外壳 (Nav / 背景光球 / 命令面板) 在 (site) 分组 layout; (auth) 分组保持全屏干净 */}
          <QueryProvider>{children}</QueryProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
