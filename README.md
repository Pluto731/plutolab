<div align="center">

# 🪐 PlutoLab

**Your AI Workshop** — 一站式智能工作台

![Phase](https://img.shields.io/badge/phase-0.1-yellow)
![License](https://img.shields.io/badge/license-Private-red)
![Stack](https://img.shields.io/badge/stack-Next.js%20%7C%20FastAPI-blue)

</div>

---

## 🎯 项目简介

PlutoLab 是面向个人的 AI 全能工作台，集成：

- 📚 **RAG 文档问答** — 上传文档，自然语言提问
- 🤖 **AI 代码评审** — GitHub PR 自动审查
- 🧩 **多 Agent 协作** — 可视化编排 AI 工作流
- 📝 **日常工具** — 笔记 / 任务看板 / 链接收藏 / 番茄钟
- 🎨 **AI 插画** — 文生图 + 编辑 + 风格库

## 🛠️ 技术栈

| 层 | 技术 |
|---|---|
| 前端 | Next.js 15 · TypeScript · Tailwind v4 · shadcn/ui · Framer Motion |
| 后端 | FastAPI · Pydantic v2 · SQLAlchemy 2 · Celery · Redis |
| 数据库 | PostgreSQL 16 + pgvector |
| LLM | Anthropic Claude (Opus 4.7 / Sonnet 4.6 / Haiku 4.5) |
| 部署 | Docker Compose · Caddy · GitHub Actions |

完整设计见 Obsidian 笔记（项目主页：`PlutoLab - 项目主页`）。

## 📦 仓库结构

```
plutolab/
├── apps/
│   ├── web/          # Next.js 前端 (Phase 0.4)
│   └── api/          # FastAPI 后端 (Phase 0.3)
├── packages/
│   ├── types/        # 共享 TypeScript 类型
│   └── ui/           # shadcn 组件共享库
├── infra/
│   ├── docker/       # Dockerfile
│   ├── caddy/        # 反向代理配置
│   └── deploy/       # 部署脚本
└── .github/
    └── workflows/    # CI/CD (Phase 0.5)
```

## 🚀 本地开发

> ⚠️ 当前处于 **Phase 0.1（仓库骨架）**。`apps/web` 与 `apps/api` 将在 Phase 0.3 / 0.4 填充实际代码。

### 环境要求

- **Node.js** ≥ 22 (推荐 24)
- **pnpm** ≥ 9
- **Python** ≥ 3.11
- **Docker** + Docker Compose
- **PostgreSQL 16** (Phase 0.2 用 Docker 拉起，无需本机安装)

### 启动

```powershell
# 安装依赖（Phase 0.3+ 才需要）
pnpm install

# 启动所有服务（Phase 0.2 后可用）
pnpm dev
```

## 🗺️ Phase 路线图

- [x] **Phase 0.1** — 仓库初始化 ✅
- [ ] **Phase 0.2** — Docker Compose 开发环境
- [ ] **Phase 0.3** — FastAPI 后端骨架
- [ ] **Phase 0.4** — Next.js 前端骨架
- [ ] **Phase 0.5** — GitHub Actions CI
- [ ] **Phase 0.6** — VPS 部署 + 自动 HTTPS
- [ ] **Phase 1** — 美观主框架 UI
- [ ] **Phase 2** — 账号系统
- [ ] **Phase 3** — 日常功能
- [ ] **Phase 4** — RAG 文档问答
- [ ] **Phase 5** — AI 代码评审
- [ ] **Phase 6** — 多 Agent 平台
- [ ] **Phase 7** — AI 图像生成
- [ ] **Phase 8** — 移动 PWA

## 📜 License

Private. © 2026 pluto.
