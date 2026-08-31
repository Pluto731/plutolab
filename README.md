<div align="center">

# 🪐 PlutoLab

**Your AI Workshop** — 一站式个人智能工作台与 AI 生产力中枢

[![CI](https://github.com/Pluto731/plutolab/actions/workflows/ci.yml/badge.svg)](https://github.com/Pluto731/plutolab/actions/workflows/ci.yml)
![Phase](https://img.shields.io/badge/phase-3.4%20(Daily%20Suite%20Ready)-emerald)
![License](https://img.shields.io/badge/license-Private-red)
![Stack](https://img.shields.io/badge/stack-Next.js%2015%20%7C%20FastAPI%20%7C%20pgvector-blue)

</div>

---

## 🎯 项目简介

**PlutoLab** 是面向个人的新一代全能智能工作台，兼具日常高频生产力工具（笔记、待办看板、链接收藏、番茄钟）与先进 AI 协同能力（RAG 知识库、代码评审、多 Agent 协作编排、AI 插画）。采用现代 Monorepo 全栈架构设计，提供极致丝滑的暗黑毛玻璃微光视觉与全键盘驱动体验。

---

## ✨ 核心特性

### 📝 1. 沉浸式智能笔记 (Notes · Phase 3.1)
- **实时行内预览**：基于 **CodeMirror 6** 打造的 Bear 风格编辑器，支持 Markdown 行内语法隐现渲染、数学公式与多语言代码高亮。
- **流畅自动保存**：1.5s 防抖无感保存 + `⌘S` 手动触发，支持 `⌘.` 全屏专注模式与 `⌘F` 内置搜索。
- **智能标签与检索**：自动解析提取 `#hashtag` 标签并聚合筛选，支持毫秒级跨笔记全文检索。

### ✅ 2. 待办与任务看板 (Tasks · Phase 3.2)
- **灵活任务管理**：支持高/中/低优先级标记、截止日期过滤（全部/今天/本周）与无限层级子任务。
- **流畅交互**：基于 `@dnd-kit` 实现平滑拖拽排序，状态与顺序即时持久化。

### 🔗 3. 智能链接收藏 (Links · Phase 3.3)
- **元数据自动解析**：输入 URL 后端异步抓取 OpenGraph 网页标题、描述、封面预览与 Favicon。
- **企业级安全**：内置严格的 **SSRF 防御系统**，杜绝内网 IP 穿透与 DNS 重绑定攻击。

### ⏱️ 4. 专注番茄钟 (Pomodoro · Phase 3.4)
- **多模式时钟**：25m 专注 / 5m 短休 / 15m 长休模式一键切换，倒计时精准无漂移。
- **任务深度联动**：专注时钟可直接关联未完成待办，支持系统原生桌面通知与历史数据归档。

### 🔐 5. 账户系统与 API Key 保险库 (Auth & Security · Phase 2)
- **全流程认证**：邮箱/密码注册登录（双 JWT Token 自动无感刷新）+ GitHub OAuth 2.0 快捷登录。
- **安全验证**：6 位 OTP 数字验证码邮箱验证与重置密码（带严格的防刷冷却与重试次数限制）。
- **多模型密匙库**：支持集中保存 Anthropic (Claude)、OpenAI、DeepSeek、Replicate API Keys，**服务端 Fernet 对称加密密文存储**，前端绝不明文暴露。

### 📊 6. 生产力仪表盘 (Dashboard · Phase 1)
- **全局控制台**：Bento Grid 动态布局，集成生产力活跃热力图、待办完成统计、近期笔记与 API 连通状态。
- **全站 `⌘K` 命令面板**：随时随地键盘极速检索路由与功能。

---

## 🗺️ Phase 开发路线图

- [x] **Phase 0.1 ~ 0.5** — Monorepo 骨架 / Docker Compose / FastAPI + Next.js 骨架 / GitHub CI ✅
- [x] **Phase 0.6** — VPS 生产部署配置 + Caddy 反向代理与自动 HTTPS ✅
- [x] **Phase 1** — 美观主框架 UI / Aurora 特效 / 响应式 Sidebar / ⌘K 命令面板 ✅
- [x] **Phase 2** — 账号体系 / 邮箱验证 / GitHub OAuth / API Key 保险库 ✅
- [x] **Phase 3** — 日常生产力套件（笔记 / 任务看板 / 链接收藏 / 番茄钟）✅
- [ ] **Phase 4** — 📚 **RAG 文档问答**（基于 pgvector 的文档切块向量化、语义检索与精准引用）*(进行中)*
- [ ] **Phase 5** — 🤖 **AI 代码评审**（GitHub PR / Commit 自动化审查）
- [ ] **Phase 6** — 🧩 **多 Agent 协作平台**（可视化工作流编排与多模型智能体协同）
- [ ] **Phase 7** — 🎨 **AI 图像生成**（文生图、图像编辑与多模态风格库）
- [ ] **Phase 8** — 📱 **移动端 PWA**（离线缓存与移动端适配）

---

## 🛠️ 技术栈一览

| 层次 | 技术选型 |
| :--- | :--- |
| **前端架构** | **Next.js 15** (App Router) · **React 19** · **TypeScript** · **Tailwind CSS v4** · **shadcn/ui** · **Framer Motion** · **TanStack Query** |
| **富文本与交互** | **CodeMirror 6** · **@dnd-kit** · **cmdk** · **Lucide Icons** |
| **后端架构** | **FastAPI** (Python 3.11+ 异步) · **Pydantic v2** · **SQLAlchemy 2 (asyncpg)** · **Alembic** · **structlog** |
| **数据库 & 缓存** | **PostgreSQL 16 + pgvector** · **Redis 7** |
| **安全机制** | **JWT (HS256)** · **Fernet 对称加密** · **bcrypt** · **Anti-SSRF** |
| **基础设施** | **pnpm Workspaces** · **Turborepo** · **Docker Compose** · **Caddy** · **GitHub Actions** |

---

## 📦 仓库目录结构

```
plutolab/
├── apps/
│   ├── web/                  # Next.js 15 前端主应用
│   ├── api/                  # FastAPI 异步后端服务
│   └── web-lab/              # 实验性 UI 探索页面
├── packages/
│   ├── types/                # 跨端共享 TypeScript 类型
│   └── ui/                   # 共享 UI 组件库
├── infra/
│   ├── docker/               # 后端及前端生产 Dockerfile
│   ├── caddy/                # Caddyfile 反向代理配置
│   └── deploy/               # 生产部署脚本 (deploy.sh)
└── .github/
    └── workflows/            # GitHub Actions CI/CD 流水线
```

---

## 🚀 本地快速启动

### 1. 环境准备
- **Node.js** $\ge 22$ (推荐 24)
- **pnpm** $\ge 11$
- **Python** $\ge 3.11$ (推荐安装 [`uv`](https://github.com/astral-sh/uv))
- **Docker** + Docker Compose (推荐 [OrbStack](https://orbstack.dev/) 或 Docker Desktop)

### 2. 步骤一：安装依赖
```bash
# 安装前端及 Monorepo 依赖
pnpm install

# 安装 Python 后端依赖 (推荐在 conda/venv 环境中)
cd apps/api
uv pip install -e ".[dev]"   # 或 pip install -e ".[dev]"
cd ../..
```

### 3. 步骤二：启动 Docker 中间件与数据库
```bash
# 启动 PostgreSQL 16 (带 pgvector)、Redis 7、MailHog、Adminer
pnpm db:up

# 执行数据库迁移
cd apps/api && alembic upgrade head && cd ../..
```

### 4. 步骤三：启动全栈开发服务
```bash
pnpm dev
```

- 🌐 **前端主站**: [http://localhost:3000](http://localhost:3000)
- 📖 **后端交互式 API 文档**: [http://localhost:8000/docs](http://localhost:8000/docs)
- 🗄️ **数据库管理后台 (Adminer)**: [http://localhost:8080](http://localhost:8080)
- ✉️ **本地邮件调试沙箱 (MailHog)**: [http://localhost:8025](http://localhost:8025)

### 5. 运行测试
```bash
# 运行后端 230+ 自动化单元测试
pytest apps/api/tests

# 运行前端类型检查
pnpm typecheck
```

---

## 📜 开源协议

Private License. © 2026 pluto. All rights reserved.
