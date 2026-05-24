import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";

import { BackgroundOrbs } from "@/components/background-orbs";
import { CommandPalette } from "@/components/command-palette";
import { Nav } from "@/components/nav";
import { PageTransition } from "@/components/page-transition";
import { QueryProvider } from "@/components/query-provider";
import { ScrollProgress } from "@/components/scroll-progress";
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
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="relative min-h-full overflow-x-hidden">
        <ThemeProvider
          attribute="class"
          defaultTheme="dark"
          enableSystem
        >
          <QueryProvider>
            {/* 全站共用: 背景光球 + 顶部滚动进度条 + sticky 导航 + ⌘K 命令面板 */}
            <BackgroundOrbs />
            <ScrollProgress />
            <Nav />
            <CommandPalette />
            <PageTransition>{children}</PageTransition>
          </QueryProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
