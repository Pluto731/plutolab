# 🪐 PlutoLab 新会话无缝接续交接备忘录 (Session Handover Memo)

> [!important] 新会话冷启动使用指南
> 当你在 Antigravity 或 Claude Code 中开启一个**全新会话**时，只需在第一条消息直接发送：
> 
> ```text
> 请读取 PlutoLab 项目的 SESSION_HANDOVER.md 以及 Obsidian 中的 Phase 4 执行手册，按照四阶段工作流继续进行下一个微切片开发。
> ```
> 
> 交接记录是进度索引；继续工作前核对当前 Git、代码与测试。访问或修改 Obsidian 须在当前授权范围内。

---

## 1. 项目基础与核心环境配置

- **本地仓库根目录**：`/Users/pluto/project/Pluto/plutolab`
- **Obsidian 笔记根目录**：`/Users/pluto/MyNotes/Projects/项目/PlutoLab`
  - [[Phase 4 切片清单 (执行手册)]]
  - [[Phase 4 - RAG 文档问答]]
  - [[Agent 架构升级与深度融合设计]]
  - [[里程碑与进度]]
- **Python 运行环境**：必须且仅使用 **`codex`** Conda 环境（2026-09-09 实测 Python 3.11.16）：
  `/opt/homebrew/Caskroom/miniconda/base/envs/codex/bin/python`
  测试使用该解释器的 `-m pytest`，安装依赖使用 `-m pip`。
- **前端工具链**：`pnpm` / Turbopack
- **远程 VPS 生产环境**：
  - 公网 IP: `107.175.190.218` (SSH: `ssh vps` 或 `ssh -p 52222 pluto@107.175.190.218`)
  - 远程代码路径: `/home/pluto/plutolab`
  - 容器服务: `plutolab-prod-caddy`, `plutolab-prod-web`, `plutolab-prod-api`, `plutolab-prod-postgres` (pgvector:pg16), `plutolab-prod-redis`
  - 线上访问入口:
    - 登录前台: `http://107.175.190.218/login` 或 `https://lab.pluto-universe.top/login`
    - Swagger API 文档: `http://107.175.190.218/docs`

---

## 2. 当前研发进度状态 (2026-09-09 本地核验)

### Slice 2：RAG UI alignment & scroll ergonomics（2026-09-10 本地验证完成，授权提交）

- **目标与实现**：`apps/web/src/app/(site)/rag/[id]/chat/components/chat-messages.tsx` 将用户头像 `text-white` 改为 `text-primary-foreground`；滚动事件记录距底部是否 ≤96px，仅在接近底部时跟随新增内容，阅读历史时保留位置，返回底部恢复跟随，切换会话重置。仅滚动聊天容器，每次更新使用即时滚动，避免逐 token 重启 smooth 动画。
- **页面对齐**：`apps/web/src/app/(site)/rag/page.tsx` 采用 Dashboard 的 `pt-20 md:pt-10`、横向留白与 `pb-24`，区块间距 `space-y-6`；标题/辅助文字与搜索、骨架、空态表面统一 semantic foreground/card/border tokens。移除这两个组件中未使用的默认 React 导入，以及 landing 的 Loader2。
- **回归**：新增 `apps/web/tests/chat-scroll.test.cjs`，使用现有 TypeScript 与 Node runner 执行真实组件的 effect/handler，覆盖历史位置保持、96/97px 边界、恢复跟随、会话切换、空会话开始流式回答。模拟 DOM 尺寸，不等同于浏览器视觉验收。
- **命令**（cwd=`apps/web`）：`node --test tests/rag.test.cjs tests/chat-scroll.test.cjs` → exit 0（`/tmp/slice2-checks.9pwdYK`）；`pnpm exec tsc --noEmit` → exit 0（`/tmp/slice2-typecheck.nwOiBE`）。另用 Node TypeScript compiler API 开启 noUnusedLocals/noUnusedParameters，过滤两个触及组件的全部诊断 → exit 0（`/tmp/slice2-unused.ImuImT`）。
- **Build**（仓库根目录）：`NEXT_TELEMETRY_DISABLED=1 pnpm --filter @plutolab/web build` → exit 0（`/tmp/slice2-build.5uMCTI`）；`git diff --check` → exit 0。未更改 API，未重跑后端；未执行浏览器明暗主题/移动端视觉验收。既有 `next lint` 脚本问题未在此切片处理。
- **边界与下一步**：Slice 1 已提交 `2be03ab3891d7f0e586b6af1d0e92896d2c417a8`；用户已授权提交 Slice 2 的两个组件、滚动回归测试与本交接文档，主题 `feat(rag-ui): fix dark contrast, token alignment, and scroll anchoring`，SHA 通过 `git log -1` 查询。未推送/部署，原有 Copilot 改动保持未暂存。下一步本地浏览器验收。

### Slice 1：RAG Correctness & Defect Remediation（本地验证完成，2026-09-10 授权提交）

- **目标与协议**：本轮优先修复运行时正确性。准备、生成、持久化失败输出 `error: {code, message}`；消息提交成功后才发送 `finish_reason: stop` 与 `[DONE]`。错误消息不包含底层异常或密钥，异常原因保留在服务异常链中。
- **Key**：`apps/api/src/plutolab_api/services/chat.py` 使用 `key_ciphertext`；字段读取、非空/类型验证及解密均在异常边界内。无记录仍返回 `None`；有记录但密文无效则显式失败。
- **Splitter**：`services/text_splitter.py` 对保留重叠与新片段合并后的真实 tokenizer 计数执行预算检查，并验证最终输出。回归覆盖原先 512 上限输出 565 tokens 的边界及中英文/emoji。
- **SSE**：更新 API `schemas/rag.py`、`services/chat.py`、Web `apps/web/src/lib/rag.ts`、`packages/types/src/rag.ts`。客户端意外 EOF、畸形 JSON、结构化错误触发一次 `onError` 并拒绝 Promise；主动取消不算成功或失败。上游提供商流也必须收到 `[DONE]`。
- **Document contract**：沿用后端 `error_msg`；同步 Web/共享类型及 `apps/web/src/app/(site)/rag/[id]/components/document-table.tsx` 的错误详情与状态提示。
- **回归文件**：新增 `apps/api/tests/test_rag_correctness.py`、`apps/web/tests/rag.test.cjs`；扩展 `apps/api/tests/test_text_splitter.py`。新增失败导入测试揭示测试后台 session 回滚会撤销用户 fixture，已在 `apps/api/tests/conftest.py` 增加 `join_transaction_mode="create_savepoint"`；未改生产 session 配置。
- **Python**：所有命令仅使用 `/opt/homebrew/Caskroom/miniconda/base/envs/codex/bin/python`（以下记为 `PY`）；API 命令 cwd=`apps/api`，Web 命令 cwd=`apps/web`。
- **定向验证**：`PY -m pytest tests/test_rag_correctness.py tests/test_rag_chat.py tests/test_text_splitter.py tests/test_rag_api.py tests/test_rag_schemas.py -q --junitxml=/tmp/slice1_targeted.xml` → exit 0，45 tests 全部通过（新增导入失败用例之前的定向结果）。日志 `/tmp/slice1_test.log`。
- **完整验证**：`PY -m pytest -q --junitxml=/tmp/slice1_full.xml` → exit 0，314 tests，0 failures/errors/skips；日志 `/tmp/slice1_full_test.log`。初次全量为 313 passed / 1 failed；修复上述 fixture 后，失败用例及全量重跑均通过。
- **Web**：`node --test tests/rag.test.cjs`、`pnpm exec tsc --noEmit` 均 exit 0；仓库根目录 `NEXT_TELEMETRY_DISABLED=1 pnpm --filter @plutolab/web build` → exit 0。日志分别为 `/tmp/slice1_web_test.log`、`/tmp/slice1_typecheck.log`、`/tmp/slice1_build.log`。
- **静态检查**：`PY -m ruff check --no-cache src/plutolab_api/services/chat.py tests/test_rag_correctness.py tests/test_text_splitter.py tests/conftest.py` → exit 0。对另两个触及文件 `services/text_splitter.py` 与 `schemas/rag.py` 的检查仍 exit 1，共 9 条既有诊断；修改前相同生产文件共 10 条，按文件/规则/消息比较无新增（`/tmp/slice1_ruff_before.json`、`/tmp/slice1_ruff_after.json`）。
- **格式与 diff**：上述六个触及 Python 文件 `ruff format --check` → exit 1，仅 `tests/conftest.py` 的既有第 76 行格式问题；对 HEAD 原文运行同一检查也 exit 1，保留无关格式。其余五个文件格式通过；`git diff --check` → exit 0。
- **提交与边界**：2026-09-10 用户授权仅提交 Slice 1 文件与本交接文档；提交主题 `fix(rag): resolve key decryption, chunk budgets, SSE errors and error_msg alignment`。提交后用 `git log -1` 获取 SHA；原有 Copilot 改动保留在工作区、不纳入提交，因此整体工作区不会 clean。未推送或部署，未修改 Obsidian/记忆文件。缺 key 时的 mock 模式、持久化 ingestion 调度及其他审计事项仍需独立切片；本轮未进行 UI 美化或无用导入清理。

### 接续核验快照（Slice 1 之前）

- **当前分支 / HEAD**：`refactor/rag-ui-and-ingestion` / `d82b2bc` (`feat(rag): add query routing and reflective retrieval retry`)；未核验远端同步状态。
- **Phase 4.5.d**：查询路由与低置信度检索重试已提交。历史上线记录不是本次生产状态证明。
- **Phase 4.5.e 首块**：本地未提交。Notes/Tasks HTTP 查询复用 `services/notes.py`、`services/tasks.py`；`services/copilot/` 提供 Pydantic 契约与显式 Registry，目前仅注册 `search_tasks`、`search_notes`。
- **能力边界**：工具接受调用方传入的用户 ID，查询按该 ID 隔离；尚无从认证上下文到工具调用的执行入口。`ToolProposal` 只是契约，提案生成、确认执行、持久化幂等与 RAG SSE 联动尚未实现。
- **本次修复**：`services/__init__.py` 的 I001 导入排序与 RUF022 导出排序；保留已有业务改动。
- **本地依赖**：Docker 29.4.0；Postgres/Redis 容器健康，测试配置指向 `localhost:5432`，fixture 使用独立 `pluto_test` 数据库及事务回滚。
- **验证命令**（cwd=`apps/api`；下文 `PY` 表示 `/opt/homebrew/Caskroom/miniconda/base/envs/codex/bin/python`）：
  - `PY -m pytest tests/test_copilot_tools.py tests/test_notes.py tests/test_tasks.py -q`：exit 0，`73 passed in 13.48s`；日志 `/tmp/plutolab-copilot-pytest.n72Cxe`。
  - `PY -m ruff check` 与 `PY -m ruff format --check`，目标为 `src/plutolab_api/api/v1/{notes,tasks}.py`、`src/plutolab_api/services/{__init__,notes,tasks}.py`、`src/plutolab_api/services/copilot`、`tests/test_copilot_tools.py`：均 exit 0；日志 `/tmp/plutolab-copilot-checks.letPgL`。首次 check 为 exit 1，修复上述两处后通过。
  - `PY -m pytest -q`：exit 0，`297 passed, 1 warning in 37.65s`；日志 `/tmp/plutolab-api-regression.KVFtfz`。警告来自 `test_token_signed_with_other_secret_is_rejected` 使用的 12 字节 HMAC 测试密钥（`InsecureKeyLengthWarning`）。
  - 仓库根目录 `git diff --check`：exit 0。
  - Web typecheck/build 本次未运行（未修改前端）；历史结果见下，不作为本次验证。
- **下一切片**：先核对既有 4.5.e 计划，再实现 `propose_create_task` 与用户确认执行器；验收须覆盖未确认不写入、幂等、跨用户拒绝、非法日期。当前只读首块通过不代表写入流程可用。
- **交付边界**：本次不提交、不推送、不部署；未连接 VPS，未修改 Obsidian 或记忆文件。`/tmp` 日志为本机临时证据。

### 2026-09-04 历史快照（非当前状态）

- **当前分支**：`main` (与 `origin/main` 保持最新同步)
- **最新 Git Commit**：`0ab12d3` (`fix(rag): remove p4 development badges, wire dashboard rag count, and enhance security`)
- **自动化测试状态**：
  - 后端 pytest 全量通过：**`287 passed, 1 warning`** (100% 满分无回退，覆盖全量 287 项用例，含 RAG 仪表盘计数与 413 大文件拦截)
  - 前端 `pnpm typecheck`：通过 (零错误)
  - 前端 `turbo run build`：通过 (Next.js 16 生产打包成功，20 条动静态路由全部通过编译)
- **生产数据库迁移版本**：`0012_create_rag_tables` (本地与 VPS 生产均已应用)
- **生产 VPS 状态**：`107.175.190.218` 运行正常，`plutolab-prod-web` 与 `plutolab-prod-api` 容器热更新重建完成，公网 HTTP 200 冒烟正常
- **收尾与安全排查**：
  - 彻底清理全局导航与界面的 `P4` / `Phase 4` 开发占位标识
  - 仪表盘 RAG 文档卡片完全对接数据库真实用户文档计数
  - 补充知识库 `chunk_count` 聚合与 `embedding_model` 契约，彻底消除前端数据显示缺失
  - 增加 50MB 实体过大前置拦截防御（HTTP 413）

### 阶段完成度速查

| 模块切片 | 名称 | 状态 | 交付物说明 |
| :--- | :--- | :---: | :--- |
| **Phase 0 ~ 3** | 基础设施、用户鉴权、全套业务组件 | ✅ 100% | 231 项测试基础底座 |
| **Phase 4.1.a** | SQLAlchemy 模型与 pgvector 向量字段 | ✅ 完成 | 5 张 RAG 表结构 (`rag.py`)，commit `5ba373d` |
| **Phase 4.1.b** | Alembic 0012 迁移 (HNSW + FTS) | ✅ 完成 | 向量余弦索引与 GIN 倒排索引，commit `ca73c17`/`ddb75b3` |
| **Phase 4.1.c** | Pydantic v2 请求/响应 Schemas | ✅ 完成 | 18 个 DTO、CitationItem 与 ORM 映射，commit `eb42a90` |
| **Phase 4.2.a** | 多格式文档解析器 (DocParser) | ✅ 完成 | 内存流解析 MD/TXT/PDF/DOCX，commit `189154c` |
| **Phase 4.2.b** | 递归语义分块器 (RecursiveSplitter) | ✅ 完成 | tiktoken 分词 + 512/64 滑动窗口 + 多页溯源，commit `3757df0` |
| **Phase 4.2.c** | Fernet 解密与向量化 (Embedder) | ✅ 完成 | 1536 维 OpenAI 批量向量化 + 确定性 Mock，commit `65b76df` |
| **Phase 4.3.a** | HNSW 向量 + 倒排混合检索 (HybridRetriever) | ✅ 完成 | pgvector `<=>` + GIN `to_tsvector` + RRF (k=60) 融合打分，commit `d4118b0` |
| **Phase 4.3.b** | 知识库管理与文件/笔记异步导入 API | ✅ 完成 | 知识库 CRUD、BackgroundTasks 异步切块、笔记一键导入、混合检索 API，commit `9d0afb2` |
| **Phase 4.3.c** | 流式 SSE 问答端点与 Citation 组装 | ✅ 完成 | 对话树追溯、原生 SSE 打字机流式输出、Citation 引用组装与持久化，commit `1a7d027` |
| **Phase 4.4.a** | 共享 TS 类型与前端 API Client | ✅ 完成 | packages/types 跨包契约，`apps/web/src/lib/rag.ts` 客户端与 SSE 打字机解析器，commit `d702a69` |
| **Phase 4.4.b** | 知识库主页与卡片网格 UI | ✅ 完成 | 替换 ComingSoon，毛玻璃网格卡片、新建弹窗、统计指标条与全局搜索，commit `551f500` |
| **Phase 4.4.c** | 文档拖拽上传与解析状态实时表格 | ✅ 完成 | 详情页 `/rag/[id]`、HTML5 拖拽上传、格式/体积拦截、自适应 2000ms 轮询状态表格与删除，commit `1bec643` |
| **Phase 4.4.d** | 现有笔记一键导入多选模态框 | ✅ 完成 | 检索 Phase 3.1 笔记、动态标签筛选、去重置灰防呆、批量提交切块向量化入库，commit `9e2e317` |
| **Phase 4.5.a** | 对话工作区双栏布局与会话历史树 | ✅ 完成 | 知识库问答页面 `/rag/[id]/chat`、左侧会话历史侧边栏（新建/重命名/删除）、右侧主视窗骨架，commit `d8f80d8` |
| **Phase 4.5.b** | 原生 SSE 打字机流式响应与 Markdown 渲染 | ✅ 完成 | 对接 `streamRAGMessage`，逐字打字机平滑渲染、Markdown 代码高亮与复制、中止生成，commit `3719ba8` |
| **Phase 4.5.c** | 行内引用角标与侧边原文高亮抽屉 | ✅ 完成 | 点击 `[^1]` 或引用胶囊滑出抽屉、原文切片高亮、余弦相似度与多条翻页，commit `c5fcb27` |
| **Phase 4.5.d** | 查询路由与自反思检索 | ✅ 已提交 | `d82b2bc`；生产状态本次未核验 |
| **Phase 4.5.e** | Copilot 工具层 | 🚧 本地首块 | 只读 Notes/Tasks 工具未提交；提案与确认执行待实现 |
| **Phase 4.6** | 交付与 VPS 生产验收 (回归+提交+上线) | ✅ 100% | 285 项 pytest 全绿、typecheck/build 零错误、Alembic 0012 (head)、公网全流程端到端冒烟通过 |
| **Phase 4.polish** | 生产收尾与安全排查 | ✅ 完成 | 移除全站 P4 标识、仪表盘真数据接通、切片数聚合补齐、50MB 上传防护，commit `0ab12d3` |
| **Phase 4 核心 / 扩展** | **RAG 智能文档问答与 Copilot** | 核心历史交付，扩展进行中 | 4.5.e 仅有本地只读首块；不能将核心交付状态扩展到 Copilot 写入流程 |

---

## 3. 四阶段工作流强制执行规则

每个微切片研发必须且严格遵循四个阶段：
1. **阶段 1：方案设计与计划记录（前置门禁）**
   - 在授权范围内查阅并续写 `/Users/pluto/MyNotes/Projects/项目/PlutoLab/开发日志/` 中已有切片日志；仅在无对应日志时新建。
   - 明确背景目标、代码设计蓝图、Checklist 与风险预案。未写笔记严禁动代码！
2. **阶段 2：规范编码与自查**
   - 编写实现代码与全覆盖单测，运行单测与全量回归确保 100% 绿灯。
3. **阶段 3：沉淀开发日志与复盘**
   - 详细回填开发日志：记录写了什么具体类/函数、做了什么关键事、ADR 决断。
   - 仅在当前会话明确授权时提交、推送或部署；历史上线说明不构成授权。本次仅本地核验与交接修正，不部署。
4. **阶段 4：执行复核与交付**
   - 逐项复核交付看板，更新执行手册与主需求笔记。
