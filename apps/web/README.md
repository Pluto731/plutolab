# @plutolab/web

PlutoLab 前端 — Next.js 16 (App Router) + TypeScript + Tailwind CSS v4 + next-themes + TanStack Query.

> Phase 0.4 状态: 主框架就位（暗黑切换 + Backend API 状态卡）。shadcn/ui 留到 Phase 1 接入。

## 目录结构

```
apps/web/
├── package.json              # @plutolab/web
├── next.config.ts
├── tsconfig.json
├── postcss.config.mjs        # Tailwind v4 PostCSS
├── .env.local / .env.example # NEXT_PUBLIC_API_URL
├── public/                   # 静态资源
└── src/
    ├── app/
    │   ├── layout.tsx        # ThemeProvider + QueryProvider 包裹
    │   ├── page.tsx          # 首页 (Hero + ApiStatus + 进度行)
    │   └── globals.css       # Tailwind v4 + .dark class + CSS 变量
    ├── components/
    │   ├── theme-provider.tsx   # next-themes 包装
    │   ├── theme-toggle.tsx     # 右上角太阳/月亮按钮
    │   ├── query-provider.tsx   # TanStack Query Provider
    │   └── api-status.tsx       # fetch backend /api/v1/health
    └── lib/
        ├── api.ts            # fetch wrapper
        └── utils.ts          # cn() = clsx + tailwind-merge
```

## 本地开发

### 前提
- 后端在 `:8000` 跑（`apps/api`）— 否则 ApiStatus 显示 error
- Docker postgres + redis + adminer 跑着

### 启动

```powershell
# 在 monorepo 根
pnpm install
pnpm --filter @plutolab/web dev

# 浏览器
# http://localhost:3000
```

### 其他脚本

```bash
pnpm --filter @plutolab/web build       # 生产构建
pnpm --filter @plutolab/web start       # 生产启动
pnpm --filter @plutolab/web typecheck   # tsc --noEmit
pnpm --filter @plutolab/web lint        # next lint
```

## 后续 Phase

- **Phase 1** — 主框架 UI: shadcn/ui 接入 + 着陆页 / 命令面板 / Framer Motion 动效
- **Phase 2** — 账号系统: NextAuth.js + 注册登陆页 + 仪表盘
- **Phase 3+** — 业务功能（笔记 / RAG / 评审 / Agent / 图像）
