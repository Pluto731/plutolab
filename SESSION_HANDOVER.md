# 🪐 PlutoLab 新会话无缝接续交接备忘录 (Session Handover Memo)

## 2026-09-10：VPS 分支协调合并（最新状态）

- **目标**：合并当前 `f547a15` 与 VPS 的 `9c0bd55`，共同祖先 `d82b2bc`；在 `/tmp/plutolab-reconcile` 隔离 worktree 验证，原 checkout 的 Notes/Tasks/Copilot 改动不纳入提交。
- **冲突决策**：保留 live UI（引用抽屉、导航、错误/空态与 reduced-motion）、限量读取上传、embedding 校验与 ingestion 边界；保留 Slice 1 key_ciphertext、512 token 预算及结构化错误，保留 Slice 2 96px 滚动跟随与间距。复用 live `rag-stream.ts` 并加入结构化 error 校验，后端错误同时输出 `finish_reason: error`，失败无 DONE。保留两侧回归测试并更新测试 transport/引用 fixture 适配严格解析。
- **API 验证**（cwd=`apps/api`）：`PYTHONPATH=/tmp/plutolab-reconcile/apps/api/src /opt/homebrew/Caskroom/miniconda/base/envs/codex/bin/python -m pytest -q --junitxml=/tmp/reconcile-api.xml` → exit 0，322 tests，0 failures/errors/skips；日志 `/tmp/reconcile-api.4KlOKW`。此计数来自仅含待提交代码的 worktree，不包括原 checkout 未提交 Copilot 测试。
- **Web 验证**（cwd=`apps/web`）：`node --test tests/rag.test.cjs tests/chat-scroll.test.cjs tests/rag-stream.test.mjs`、`pnpm exec tsc --noEmit`、`NEXT_TELEMETRY_DISABLED=1 pnpm build` 均 exit 0；日志 `/tmp/reconcile-web.kQJiVn`、`/tmp/reconcile-tsc.lcTYqe`、`/tmp/reconcile-build.3S5TkJ`。
- **静态验证**：codex `-m ruff check --no-cache` 对 chat/embedder/ingestion、api/v1/rag 与 test_rag_correctness/test_embedder/test_ingestion/test_rag_stream_errors 均 exit 0（`/tmp/reconcile-ruff.1r5bfh`）；`git diff --cached --check` exit 0。无新增迁移或部署配置修改；全仓既有 lint 债务不在此次范围。
- **授权部署计划**：提交 merge 并推送 `refactor/rag-ui-and-ingestion`，VPS fetch/checkout/pull --ff-only 后使用 production compose 和 `.env.prod`，仅 `up -d --build --no-deps web api`。验证非应用容器 ID/StartedAt 不变，检查 API 内网与公开 HTTP；不删除卷、不重启数据库。最终 deployed SHA/服务状态以本次交付卡为准；浏览器视觉验收由用户执行。

## 2026-09-09：RAG 本地重构交接（本节优先于下方历史环境/部署记录）

**状态：实现与回归验证完成；全仓 lint 门禁仍有基线债务，不能标记所有检查通过。**
2026-09-09 用户已验收本地结果并授权本切片 commit/push 与 VPS Web/API 受控部署。下文“未提交/未部署”为本地验收时点记录；最终 SHA 与线上证据回填 Obsidian `开发日志/2026-09-09 Phase 4 RAG 本地边界修复与交互对齐实施日志.md`。40 项未修改文件中的旧 lint 违规按本次明确要求保留，不纳入当前切片。
Worktree：`/Users/pluto/project/Pluto/plutolab-rag-refactor`；分支：`refactor/rag-ui-alignment-local`；基线：`d82b2bc`。修改未提交、未 push、未连接或部署 VPS。原 checkout 的 Notes/Tasks/Copilot 未提交工作保留。
本次及后续 Python 命令仅使用 `/opt/homebrew/Caskroom/miniconda/base/envs/codex/bin/python`；下方历史 `gemini` 环境记录不适用于当前任务。

### Plan → Implement：影响面与前后行为

| 文件（相对本 worktree） | 改动前 → 改动后 |
| --- | --- |
| `apps/api/src/plutolab_api/services/embedder.py` | 非类型化 provider JSON、错误包含响应正文 → 独立 `_embed_remote`，严格验证 1536 维、有限数值、非零向量、数量和索引；远程失败不会切换 mock；异常保留 cause、公开消息去敏。 |
| `apps/api/src/plutolab_api/services/ingestion.py` | 已有自主 session factory → 保留接口并核对文档 owner/KB；统一 logger，意外失败不写入原始异常；新增独立连接验证。 |
| `apps/api/src/plutolab_api/api/v1/rag.py` | 应用层无界读取上传文件、embedding 异常未映射 → 最多读取 50MB + 1 byte，保持 413；检索 embedding 失败返回 502。Multipart 层仍有自身缓冲。 |
| `apps/api/src/plutolab_api/services/chat.py` | async generator 外的无效 fallback 捕获、失败可能仍报告 stop/暴露异常 → 保留 keyless mock，远程生成/持久化失败发 `finish_reason=error`，日志只记录错误类型。SSE 字段形状不变。 |
| `apps/web/src/lib/rag.ts`、新增 `rag-stream.ts`、`packages/types/src/rag.ts` | 手写解析静默接受截断、metadata any、文档字段错误 → 可测试 UTF-8/SSE reader、异常事件验证、unknown metadata、对齐 `error_msg/file_size`。 |
| `apps/web/src/app/(site)/rag/[id]/chat/page.tsx` | 新会话缓存缺失、逐 token setState、旧流 finally 清除新控制器、完成气泡先清空 → 先写缓存再选择、按帧更新、控制器身份校验、读取已持久化消息后交接气泡；删除同步列表与 URL。 |
| 同目录 `components/chat-messages.tsx`、`chat-input.tsx` | 强制平滑滚动、越界引用指向最后一条、IME Enter 误发送 → 尊重阅读位置/减少动画偏好、只打开有效引用、组合输入保护、语义 token、无文档入口与输入按钮标签。 |
| 同目录 `components/citation-drawer.tsx`、`conversation-sidebar.tsx` | 自制引用遮罩、缺焦点/复制失败反馈、会话操作依赖 hover → 复用已有 Radix Dialog、焦点约束/Escape/恢复、引用导航、复制结果与失败提示；键盘选择会话、触屏操作、重命名错误反馈。 |
| `apps/web/src/components/ui/error-notice.tsx`（新增） | 统一可访问 `role=alert` 错误卡片，复用 Button 与 destructive token。 |
| `apps/web/src/components/nav.tsx` | 浏览器发现首页跳转应用页时 early return 越过 hooks，触发 Rendered fewer hooks → 将 pathname 隐藏判断移到 hooks 之后，保持调用顺序。 |
| `apps/web/src/app/(site)/rag/page.tsx`、`[id]/page.tsx` | 独立颜色/间距、重复 deletingId、搜索空状态操作不匹配 → 语义颜色与成熟模块内容宽度、mutation 派生删除状态、清空筛选、请求错误提示。 |
| `rag/[id]/components/document-table.tsx`、`document-upload-zone.tsx`、`import-notes-dialog.tsx`、`rag/components/create-kb-dialog.tsx` | 文档错误字段不匹配、20MB 文案、any catch → 实际错误可见、50MB 对齐、unknown narrowing、删除失败可恢复。 |
| `apps/api/tests/test_embedder.py`、新增 `test_ingestion.py`、`test_rag_stream_errors.py` | provider 响应异常、独立 session 成功/失败事务、意外错误去敏、远程流失败回归。 |
| `apps/web/tests/rag-stream.test.mjs`（新增）、`apps/web/package.json` | 增加无额外依赖的 Node 测试命令与 7 个 SSE 行为用例。 |

`git diff` 可直接审核所有已有文件的 before/after；新文件需要单独打开，未进行提交或 staging。格式化仅限修改文件，未改锁文件、数据库 schema 或 Agentic retrieval 实现。

### Verify：实际命令和结果

- API cwd `apps/api`：`DATABASE_URL=postgresql+asyncpg://pluto:local_rag_test@127.0.0.1:55432/pluto /opt/homebrew/Caskroom/miniconda/base/envs/codex/bin/python -m pytest -q`：**305 passed, 1 warning, 37.73s**；基线 293 passed。warning 为原有错误签名 JWT 测试的短 HMAC key。
- 根目录 `pnpm typecheck`：通过；`pnpm --filter @plutolab/web build`：通过，20 个页面生成完成。
- `pnpm --filter @plutolab/web test`：**7 passed**。覆盖分段中文/emoji、CRLF、末尾无换行、提前 EOF、JSON/引用/delta 错误、provider error、reader 解锁。Node 提示 package 未声明 module 类型，测试正常完成。
- codex `python -m ruff check` 和 `python -m ruff format --check` 对上表 7 个修改/新增 Python 文件：通过；Prettier 对全部修改/新增 TS/TSX/MJS/JSON：通过；`git diff --check`：通过。
- **非通过门禁**：`pnpm lint` 仍调用 Next 16 已移除的 `next lint`，报 `Invalid project directory .../apps/web/lint`；全 API `python -m ruff check . --statistics` 剩余 **40** 项，全部位于本次未修改文件。未屏蔽规则、未大范围自动修复。
- Playwright + 本地 `127.0.0.1:3100`、固定 API fixtures：桌面/390×844 深色引用抽屉、焦点约束、Escape 后焦点恢复、复制成功、无横向溢出通过；IME composition 不发送，503 错误及重试可见；首次提问只创建 1 个会话/发送 1 次请求，URL 正确，最终答案只显示 1 份。
- 浏览器截图：`/tmp/plutolab-rag-mobile-citation.png`、`/tmp/plutolab-rag-desktop.png`。浏览器 fixture 验证交互；真实数据库行为由 PostgreSQL 集成测试验证，未声称付费 provider 或完整浏览器到真实 API 链路已验证。
- 收尾发现并修复缓存已包含新会话时重复插入：按 id 去重，浏览器复验 1 行、0 duplicate-key warnings。首页经客户端链接进入 `/rag` 复验 0 uncaught errors。上述修复后再次通过 typecheck、7 个 SSE tests、production build 和修改文件格式检查。
- 实测工具链：codex Python 3.11.16、Node 26.8.1、pnpm 11.2.2；Node 满足 engines >=22，但高于 `.nvmrc` 的 24。build 有既有 tracingRoot / Node deprecation 提示。

### Handover：边界与下一切片

本次测试数据库为独立本地容器 `plutolab-rag-refactor-db`，只绑定 `127.0.0.1:55432`，不使用原开发库；任务结束停止此容器及本次前端进程，保留容器以便 `docker start plutolab-rag-refactor-db` 复验，未删除数据卷或其他服务。

后续可另立切片处理 Node 24/ESLint 工具链与持续浏览器回归（慢流切换、剪贴板拒绝、真实本地 API）；40 项基线规则违规本次保持原样。BackgroundTasks 仍不是持久化队列；mock 不是语义质量指标；非流式 chat 的历史 mock 实现仍保留。本次 Web/API 部署已获授权，其他生产变更不在授权范围。

---

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


## 2026-09-17：Phase 5 Slice 3 本地完成（当前 Phase 5 接续入口，未提交）

- [Scope] 4 个 review state 模型、jobs service、migration 0014、jobs tests；owner/installation 隔离、delivery/job 幂等、独立 analysis/publication、attempt lease、原子 outbox intent、findings/coverage/usage 持久化。原 installation/settings 类与 Slice 1 contracts 保留；domain migration 测试仅改为查询真实 Alembic head。
- [Command] cwd=`apps/api`；Python=`/opt/homebrew/Caskroom/miniconda/base/envs/codex/bin/python`；`python -m pytest tests/test_review_jobs.py -q --junitxml=/tmp/phase5-slice3-final-results.xml` exit 0，55 passed；`python -m pytest tests/test_review_jobs.py tests/test_review_domain.py -q --junitxml=/tmp/phase5-slice3-review-results.xml` exit 0，102 passed（47 domain + 55 jobs，最终 publication guard 修改后重跑 55 jobs）。
- [Command] `python -m ruff check --no-cache` / `python -m ruff format --check` scoped 6 文件 exit 0；日志 `/tmp/phase5-slice3-final.vv6uKo`、`/tmp/phase5-slice3-review-regression.59Ykzw`。最终 `git diff --check` exit 0；只读查询确认剩余 disposable review DB=0。
- [Verification] 新建 UUID loopback DB 验证 0013→0014→0013→0014、metadata/default 与旧 user/installation/settings 保留；并发重复、跨 owner、outbox 失败回滚、提交可见性、lease/retry、partial/superseded/publish_unknown 均通过。未执行全后端/Web build；不能据此宣告 M4 上线。
- [Isolation] OrbStack/既有 plutolab-postgres 原先停止，本次启动用于本地验证；无镜像拉取，不修改 compose。只删除本次创建的测试库，无 FORCE，无应用库/共享 pluto_test/生产迁移。快照 `/var/folders/5b/52_2bwvd5nvf8x0qcwr_dbsc0000gn/T/phase5-slice3-k3nea_20`；非目标文件指纹保持，原交接全文保留追加。
- [Boundary] 仅 outbox 持久意图，无 broker dispatch（Slice 9）；无外部网络、GitHub/provider/HTTP review route。head 先后须由上层核验，不按 webhook 到达顺序 supersede；真实 diff 定位/预算计费/发布 reconciliation 留后续 slice。confirm receipt 按 attempt 留存，未知发布禁止盲重试。
- [Docs] 已同步 vault `Phase 5 - AI 代码评审.md` 与 `Phase 5 AI 代码评审微切片实施计划.md`，后者为唯一连续实施日志。main=`5b6f7d5f7440e9d7ebbb4e648988102f0f3c6a93`，无 commit/push/deploy。
- [Next Step] Slice 4 GitHub App HTTP/凭据适配器待单独授权；建议 `/compact` 或新会话后读取本节及连续日志再接续。
- [Verification] 最终隔离/链接审计：21 个既有文件中 17 个逐字节不变；4 个目标文件仅 model/注册扩展、domain test head 兼容与交接追加。原 installation/settings 类 AST 不变、原 SESSION_HANDOVER 全文保留。仅新增 0014/jobs service/jobs tests；增量 diff 证据 `/tmp/phase5-slice3-reviewed.diff`，审计日志 `/tmp/phase5-slice3-delivery-audit.log`。

## 2026-09-18：Phase 5 Slice 4 本地完成（最新接续入口，未提交）

- [Scope] 新增 core/github_app.py、services/review/github_client.py、tests/test_github_app_client.py；config.py 仅 App ID/SecretStr 私钥/timeout 占位，不动 OAuth；JWT、installation token、只读 repo/PR/diff/编号分页。
- [Design] RS256：iat=now−60s、exp=now+540s；token 最多缓存 300s/256 installations、提前 60s 刷新、锁合并获取。固定 api.github.com，禁重定向/环境代理，不消费 payload URL/Link；响应限 5 MiB；凭据及上游异常诊断去敏。
- [Command] cwd=apps/api；P=/opt/homebrew/Caskroom/miniconda/base/envs/codex/bin/python；`$P -m pytest tests/test_github_app_client.py -q --junitxml=/tmp/phase5-slice4-results.xml` exit 0：77 passed。
- [Command] 最终断言计数：`PYTHONPATH=/tmp/phase5-slice4-9qz1i90k $P -X pycache_prefix=/tmp/phase5-slice4-9qz1i90k/pycache -m pytest tests/test_github_app_client.py -q -p slice4_assertion_audit -o enable_assertion_pass_hook=true --junitxml=/tmp/phase5-slice4-final-results.xml` exit 0：77 passed，1031 次 assert 成功执行（含循环；非独立测试数）。
- [Command] `$P -m ruff check --no-cache src/plutolab_api/core/github_app.py src/plutolab_api/services/review/github_client.py tests/test_github_app_client.py src/plutolab_api/core/config.py` exit 0；同四文件 `$P -m ruff format --check` exit 0；`git diff --check` exit 0。
- [Verification] cache acquisition/refresh/隔离/并发/清空，JWT claims/算法，401 单次刷新、403/404、429/5xx/timeout bounded backoff、无效响应/限额/压缩、分页/恶意 URL/重定向、DEBUG 凭据去敏均通过。socket/DNS 禁止，纯 MockTransport/fake signer，无 DB 或真实密钥生成。
- [Evidence] `/tmp/phase5-slice4-final.p4B1Sf`、`/tmp/phase5-slice4-assertions.json`、`/tmp/phase5-slice4-final-results.xml`；增量 diff `/tmp/phase5-slice4-reviewed.diff`，文件/链接审计 `/tmp/phase5-slice4-delivery-audit.json`。
- [Protection] 快照 `/tmp/phase5-slice4-9qz1i90k`；24 个既有未暂存文件中 23 个逐字节不变，SESSION_HANDOVER 原全文作前缀保留并追加。新增 repo 文件恰为 3 个；config 原本干净，仅批准字段修改。main=5b6f7d5f7440e9d7ebbb4e648988102f0f3c6a93；staging 空，无 commit/push/deploy。
- [Docs] 仅同步现有 Phase 5 AI 代码评审微切片实施计划.md（Slice 4 执行/验收与进度）；历史 Slice 3 日志保留。
- [Boundary] 未运行全后端/Web、真实签名验签或官方远端合同核对（本轮禁止外网）；2022-11-28 REST 合同需真实集成前核对。缓存仅进程内，owner/installation/撤销校验由未来调用层承担；没有 callback/webhook/worker/publisher 或真实 HTTP 调用。
- [Next Step] Slice 5 安装绑定与撤销 API 待独立授权；建议 `/compact` 或新会话后读本 Task Card 与连续日志。

## 2026-09-18：Phase 5 Slice 5 本地完成（最新接续入口，未提交）

- [Scope] 新增 api/v1/review.py、services/review/installations.py、tests/test_review_installations_api.py；router.py 仅 import/include。POST /review/installations/start、POST /callback、GET /{id}、DELETE /{id}（均 /api/v1 前缀，需 CurrentUser）。
- [Design] 32-byte entropy state，Redis SHA256 key + owner/github_id/app_id，NX/300s TTL/GETDEL 单次消费；App JWT 服务端 GET /app、/app/installations/{id} 校验 App/installation/account/suspension/最小权限，固定源，不信 query/body user_id。
- [Boundary] 本片个人安装 account.id 必须等于已关联 github_id；组织安装缺少用户授权证据时 fail closed，偏好询问未获扩展授权。现有 OAuth 不变；回跳导航须未来前端带本站 Bearer POST，无匿名 GET 绑定；Redis 需 GETDEL (6.2+)。
- [Revocation] 本地 revoke + rules disabled/version+1 原子提交，owner/history 保留，旧 pending callback 不可复活；既有 job gates 阻止新调度、分析、发布。无远端 uninstall；不声称撤销在途远端写入。
- [Command] cwd=apps/api；P=/opt/homebrew/Caskroom/miniconda/base/envs/codex/bin/python；`$P -m pytest tests/test_review_installations_api.py -q --junitxml=/tmp/phase5-slice5-results.xml` exit 0：50 passed；日志 `/tmp/phase5-slice5-final.yfMOOC`。
- [Command] `$P -m ruff check --no-cache src/plutolab_api/api/v1/review.py src/plutolab_api/api/v1/router.py src/plutolab_api/services/review/installations.py tests/test_review_installations_api.py` exit 0；同四文件 `$P -m ruff format --check` exit 0，日志 `/tmp/phase5-slice5-gates.O8yzpX`；`git diff --check` exit 0。
- [Verification] 正常流、state 缺失/过期/篡改/重放/并发/碰撞、跨租户和伪造归属、权限/暂停、上游/Redis 错误安全映射、撤销调度/发布阻断和故障回滚通过。真实 CurrentUser/本站 JWT，fake App signer/MockTransport/fakeredis；仅 UUID disposable loopback DB，现有迁移 head，未改共享 pluto_test；剩余 review DB=0。
- [Protection] 快照 `/tmp/phase5-slice5-e15vibuj`：28 个既有文件中 27 个 byte-identical，SESSION_HANDOVER 原全文前缀保持。原 Slice 1–4/Copilot 文件全保留，无 config/model/adapter/settings/jobs/旧测试修改；新增 repo 文件恰 3 个，router 原本干净。
- [Evidence] `/tmp/phase5-slice5-results.xml`、`/tmp/phase5-slice5-db-cleanup.json`、`/tmp/phase5-slice5-delivery-audit.json`、`/tmp/phase5-slice5-reviewed.diff`。首轮测试 mock 全局 JWT 导致 401，修正为只 mock App signer 后通过；未运行全后端/Web 或远端合同核对。
- [Docs] 已追加并同步 canonical Phase 5 AI 代码评审微切片实施计划.md 的 Slice 5 日志与进度；历史日志保留。main=5b6f7d5f7440e9d7ebbb4e648988102f0f3c6a93，staging 空，无外网、真实密钥、生产、commit/push/deploy。
- [Next Step] Slice 6 仓库与规则 API 待单独授权；建议 /compact 或新会话后先读本 Task Card 与连续日志。

## 2026-09-18：Phase 5 Slice 6 进行中（max_pr_lines 文件保护边界待确认，未完成）

- [Scope] review.py + settings.py：安装归属/active 检查，repo 稳定 ID 访问核验，GET repositories q/page/per_page，GET/PUT settings，默认 disabled 同步、严格 glob/focus_areas/min 阈值、预期版本并发保护；新增 test_review_settings_api.py。
- [Contract] PUT 完整替换且 expected_rules_version 必填；focus_areas 映射 focus，真实变更 +1/no-op 不变；job policy/version 不修改。每次 settings 访问实时 mock 核验权限，HTTP 后加锁检查撤销，页同步原子回滚；搜索完整枚举上限 10000，超限 422，不执行正则/外部 Link。
- [Command] cwd=apps/api，P=/opt/homebrew/Caskroom/miniconda/base/envs/codex/bin/python；`$P -m pytest tests/test_review_settings_api.py -q --junitxml=/tmp/phase5-slice6-scope-results.xml` exit 0：50 passed；日志 `/tmp/phase5-slice6-scope.mbHDlB`。
- [Command] `$P -m pytest tests/test_review_settings_api.py tests/test_review_domain.py tests/test_review_jobs.py tests/test_review_installations_api.py -q --junitxml=/tmp/phase5-slice6-regression-results.xml` exit 0：202 passed；日志 `/tmp/phase5-slice6-regression.y0EpEW`。未运行全后端/Web。
- [Command] `$P -m ruff check --no-cache src/plutolab_api/api/v1/review.py src/plutolab_api/services/review/settings.py tests/test_review_settings_api.py` exit 0；同三文件 `$P -m ruff format --check` exit 0；日志 `/tmp/phase5-slice6-gates.ElCB19`；最终 `git diff --check` exit 0。
- [Verification] HTTP 仅 MockTransport；复用 UUID loopback test DB，剩余 0（/tmp/phase5-slice6-db-cleanup.json）。listing/权限/IDOR/422/版本/撤销竞态/原子同步/job快照/溢出验证通过；不把未实现 max_pr_lines 算入验收。
- [Blocker] max_pr_lines 当前无持久字段；与用户要求原 27 个未暂存文件 byte-for-byte 有冲突，已异步询问是否允许 model/jobs 必要增量与新迁移，尚未答复；该部分不得根据超时擅自执行。
- [Proposal] `/tmp/phase5-slice6-meugimyq/max-pr-lines-proposal.patch` 未应用：model nullable max column + max≥min constraint、settings/API 字段/校验、jobs budget cap、0015 migration；语法已解析，行为与 migration 未测试。
- [Protection] snapshot `/tmp/phase5-slice6-meugimyq`；原 32 个文件中 29 个逐字节保持，仅获准 review.py/settings.py 变更，SESSION_HANDOVER 原全文追加。model/jobs/旧测试/config/OAuth/adapter 均未动，新增 repo 文件仅 settings API tests；审计 `/tmp/phase5-slice6-delivery-audit.json`，增量 `/tmp/phase5-slice6-reviewed.diff`。
- [Docs] canonical 微切片实施计划已追加部分执行/验收/阻塞记录；Slice 6 checkbox 保持未完成。main=5b6f7d5f7440e9d7ebbb4e648988102f0f3c6a93；无外网/生产/commit/push/deploy，staging 空。
- [Next Step] 等待用户确认上述 model/jobs/0015 的 scoped exception，再实施 max 字段、隔离 migration roundtrip/对应测试并重跑受影响门禁。不得开始 Slice 7。

## 2026-09-18：Phase 5 Slice 6 本地完成（最新接续入口，未提交）

- [Scope] Repository search/pagination/sync + GET/PUT rules API、owner/installation/实时 repo 访问核验、严格 glob/focus/数值、expected_rules_version；批准补齐 nullable max_pr_lines model/API/domain、job cap guard 和 migration 0015。
- [Contract] 旧 max=None 不改变原预算；max 正整数≤SQL int 且≥min；真实变化 version+1/no-op 不变。job budget 可更严格但不可超过 cap，历史 policy/version 保留。搜索最多完整枚举 10000 仓库后 filter/page，超限拒绝；PUT 完整替换，expected_rules_version 必填。
- [Authorization] 本节 supersedes 上一节待确认状态：用户已批准 model/migration/job 必要增量；Slice 5 个人安装/拒绝组织也已明确确认。Slice 7 尚未授权。
- [Command] cwd=apps/api，P=/opt/homebrew/Caskroom/miniconda/base/envs/codex/bin/python；`$P -m pytest tests/test_review_settings_api.py -q --junitxml=/tmp/phase5-slice6-complete-results.xml` exit 0：61 passed；日志 `/tmp/phase5-slice6-complete.6QxWIg`。
- [Command] `$P -m pytest tests/test_review_settings_api.py tests/test_review_domain.py tests/test_review_jobs.py tests/test_review_installations_api.py -q --junitxml=/tmp/phase5-slice6-final-regression-results.xml` exit 0：213 passed（61+47+55+50）；日志 `/tmp/phase5-slice6-final-regression.e0UJ5a`。
- [Command] `$P -m ruff check --no-cache src/plutolab_api/api/v1/review.py src/plutolab_api/services/review/settings.py src/plutolab_api/models/review.py src/plutolab_api/services/review/jobs.py alembic/versions/0015_add_review_max_pr_lines.py tests/test_review_settings_api.py tests/test_review_jobs.py` exit 0；同 7 文件 `ruff format --check` exit 0；`git diff --check` exit 0。
- [Verification] cap 持久化/清空/版本/边界、job cap与快照、IDOR/失权/revoke竞态/原子sync回滚通过；0014→0015→0014→0015 在 UUID disposable DB 验证受影响 metadata/constraint/旧行保留；剩余 review DB=0（/tmp/phase5-slice6-final-db-cleanup.json），无应用/共享 pluto_test/生产迁移。
- [Compatibility] test_review_jobs.py 仅 migration roundtrip 用 SQL seed 旧 schema、expected head 改动态查询；其他测试函数保持。models 仅 ReviewSettings 新列/constraint；jobs 仅 enqueue cap guard，其他类/函数 AST 保持；API/settings 累积 Slice 6 增量均在授权内。
- [Protection] 续接快照 `/tmp/phase5-slice6-approved-4jpgqnh9`：33 个既有文件中 26 个 byte-identical、6 个批准目标增量、handover 原前缀追加；原 Slice 6 快照 `/tmp/phase5-slice6-meugimyq` 保留。整片新增仅 settings API tests + migration0015。
- [Evidence] `/tmp/phase5-slice6-complete-audit.json`、`/tmp/phase5-slice6-complete-reviewed.diff`；canonical 微切片实施计划已标 Slice 6 完成并追加最终验收。main=5b6f7d5f7440e9d7ebbb4e648988102f0f3c6a93；staging 空。
- [Boundary] GitHub 仅 MockTransport；无外网/真实密钥/GitHub mutation/生产/commit/push/deploy，未运行全后端/Web 或远端官方合同核验。
- [Next Step] Slice 7 安装/仓库设置 Web 待单独授权；建议 /compact 或新会话后读取本 Task Card 与连续日志。


## 2026-09-18：Phase 5 Slice 7 本地完成（最新接续入口，未提交）
- [Scope] `/review/settings` 安装状态/个人身份/显式 callback/解绑确认、仓库分页搜索、规则表单与版本冲突恢复；`/review` 提供入口；无新 UI/test 依赖。
- [Authorization] 用户另行批准最小 authenticated GET `/api/v1/review/installations` discovery + focused API tests；只读 owner 行/当前 verified GitHub ID，无 GitHub HTTP、schema/migration/OAuth 修改。旧 Slice 7 未授权状态已被取代。
- [Contract] min/max 为正 SQL int，max nullable 且≥min；有界 relative globs；full PUT+expected_rules_version。409 留草稿，读取最新后显式选择再保存；回调 query 立即移除，state 仅内存，确认后单次 authenticated POST，真实一次性/归属由后端验证。
- [Command] cwd=apps/web：`node --experimental-strip-types --test tests/*.test.mjs tests/*.test.cjs` 64 passed exit 0；`pnpm typecheck` exit 0；scoped `pnpm exec prettier --check`（本片 9 Web files，完整命令在 canonical log）exit 0；`/tmp/phase5-slice7-web-final.7nBftM`。
- [Browser] `tests/review-settings.browser.js` 对 :3007 本地 build + 全 route mocks：15 scenarios passed/0 failed（含 390px/键盘、callback/撤销/冲突）；`/tmp/phase5-slice7-browser-results.json`。Playwright 工具执行，无 shell exit code。
- [Command] repo：`NEXT_TELEMETRY_DISABLED=1 NEXT_FONT_GOOGLE_MOCKED_RESPONSES=/tmp/phase5-slice7-fonts.cjs NODE_OPTIONS='--require=/tmp/phase5-slice7-network-guard.cjs' pnpm --filter @plutolab/web exec next build --webpack` exit 0；`/tmp/phase5-slice7-build-final.camHkC`。
- [Command] cwd=apps/api，P=/opt/homebrew/Caskroom/miniconda/base/envs/codex/bin/python：`$P -m pytest tests/test_review_installation_list_api.py tests/test_review_installations_api.py tests/test_review_settings_api.py -q --junitxml=/tmp/phase5-slice7-api-results.xml` 115 passed exit 0；`/tmp/phase5-slice7-api.HHqedJ`。
- [Command] `$P -m ruff check --no-cache src/plutolab_api/api/v1/review.py tests/test_review_installation_list_api.py` + 同两文件 `ruff format --check` exit 0；`git diff --check` exit 0。
- [Protection] 34 个既有未暂存文件中 32 unrelated byte-identical；API 获准增量且所有原定义 AST 保持；handover 原全文追加；新文件 9。快照 pointer `/tmp/phase5-slice7-snapshot-path`；审阅 diff `/tmp/phase5-slice7-reviewed.diff`，audit `/tmp/phase5-slice7-audit.json`。
- [Isolation] disposable UUID loopback PostgreSQL 已清理，remaining=0（`/tmp/phase5-slice7-db-cleanup.json`）；测试 server 已停止；无外网、真实 GitHub、生产、commit/push/deploy；main=5b6f7d5f7440e9d7ebbb4e648988102f0f3c6a93，staging 空。
- [Limits] Next16 已移除旧 `next lint`、未安装 ESLint：使用 scoped Prettier+TS，不宣称 ESLint 通过。Build 使用离线字体 fixture；未验证 live GitHub/setup/真实字体/完整后端回归。远端 App setup URL 应指向 Web `/review/settings`，本片未改远端设置。
- [Next Step] Slice 8 webhook/inbox 待单独授权；建议 /compact 或新会话后读取本节与 canonical 连续日志。


## 2026-09-18：Phase 5 Slice 8 进行中（持久化扩展待确认，未完成）
- [Scope] 新增 `services/review/webhook.py` bounded verifier/PR parser 与 `tests/test_review_webhook_api.py`；1 MiB chunk-before-append、HMAC compare_digest、GUID/header/JSON/identity validation；尚未挂载 webhook endpoint。
- [Command] cwd=apps/api，P=/opt/homebrew/Caskroom/miniconda/base/envs/codex/bin/python；`$P -m pytest tests/test_review_webhook_api.py -q` 32 passed exit 0；同两文件 scoped `ruff check --no-cache` / `ruff format --check` exit 0；`git diff --check` exit 0。`/tmp/phase5-slice8-parser-gates.0RGAYG`。
- [Blocker] ReviewDelivery 的非空 job/owner、PR-only/opened+synchronize constraints 无法支持 ignored/reopened。已询问用户是否允许 scoped model/migration0016/jobs/config 增量；尚无答复。这四类目标未改，不能把已授权 parser 工作当完整 Slice 8。
- [Proposal] `/tmp/phase5-slice8-scoped-proposal.diff`、`/tmp/phase5-slice8-migration-proposal.py`、`/tmp/phase5-slice8-webhook-service-draft.py`；完整未应用目标位于快照 proposed/。迁移草案保旧行、遇新型 inbox 行拒绝 downgrade；显式预算/模型、preview_only；无外部 dispatch。
- [Protection] 快照 `/tmp/phase5-slice8-yibd4id1`（pointer `/tmp/phase5-slice8-snapshot-path`）；44 个既有文件除授权 handover 追加外保持 byte-identical；audit `/tmp/phase5-slice8-pending-audit.json`。原安装/API/router/model/jobs/config/OAuth/Web均未改变。
- [Boundary] 目前仅 parser tests；尚未跑 HTTP endpoint/DB commit/dedupe/job/outbox/migration gates。未创建测试DB，无外网/真实GitHub/生产/commit/push/deploy，staging 空，main=5b6f7d5f7440e9d7ebbb4e648988102f0f3c6a93。
- [Next Step] 收到上述 scoped additions 确认后核对快照、应用方案并补接收路由和 disposable DB tests，完成整片门禁/日志。Slice 8 未完成，不进入 Slice 9。


## 2026-09-18：Phase 5 Slice 8 本地完成（最新接续入口，未提交）
- [Scope] POST `/api/v1/review/webhook`：1 MiB streaming limit、raw HMAC compare_digest、严格 GUID/header/JSON/PR identity、durable ignored/accepted inbox、opened/synchronize/reopened；owner 由 installation 派生，无 payload URL/sender authority。
- [Approval] 用户明确批准 model/migration0016/jobs/config scoped additions；前节待确认/parser-only 状态 superseded。原 /tmp 草案已应用，以 repo 当前实现为准，勿重复 apply。
- [Transaction] delivery GUID advisory lock + hash/event/action conflict fence；accepted delivery/job/outbox 同事务 commit 后202，ignored commit后200。并发仅一条；commit失败503；ACK丢失重投发现 durable duplicate。无原始PR/body持久化，无 broker/provider/GitHub调用。
- [Config] GITHUB_APP_WEBHOOK_SECRET SecretStr；REVIEW_WEBHOOK_MODEL + REVIEW_WEBHOOK_BUDGETS 显式配置，缺配置 fail closed；REVIEW_WEBHOOK_MAX_ATTEMPTS默认1。规则当前 version/focus/paths/min/cap 快照；preview_only，不启用外部发布。
- [Command] cwd=apps/api，P=/opt/homebrew/Caskroom/miniconda/base/envs/codex/bin/python；`$P -m pytest tests/test_review_webhook_api.py -q --junitxml=/tmp/phase5-slice8-webhook-results.xml` 72 passed exit0；`/tmp/phase5-slice8-final-gates.v96o3x`。
- [Command] `$P -m pytest tests/test_review_webhook_api.py tests/test_review_domain.py tests/test_review_jobs.py tests/test_review_installations_api.py tests/test_review_installation_list_api.py tests/test_review_settings_api.py -q --junitxml=/tmp/phase5-slice8-regression-results.xml` 289 passed exit0；`/tmp/phase5-slice8-regression.yRfNpX`。
- [Command] scoped `ruff check --no-cache` / `ruff format --check`（review API/webhook/model/jobs/config/0016/new tests，同7文件，canonical log有完整命令）均exit0；`git diff --check` exit0。
- [Migration] 0015→0016→0015→0016 + legacy行/metadata通过；downgrade遇ignored/reopened历史拒绝，不自动删数据。UUID disposable DB已清理，remaining0（/tmp/phase5-slice8-db-cleanup.json），未迁移应用/共享/生产DB。
- [Protection] 快照 `/tmp/phase5-slice8-approved-jeoicrmt`：39 unrelated既有文件byte-identical，原API handlers/其他models/job functions源码保持、config原字段保持、handover原前缀追加；初始快照44文件保留。整片diff `/tmp/phase5-slice8-reviewed.diff`，audit `/tmp/phase5-slice8-complete-audit.json`。
- [Boundary] main=5b6f7d5f7440e9d7ebbb4e648988102f0f3c6a93，未提交、staging空；无外网/真实GitHub/commit/push/deploy；未运行全backend/Web/live webhook验收。
- [Next Step] Slice 9 Celery/outbox派发待单独授权；建议 /compact 或新会话后读本节与canonical连续日志。


## 2026-09-19：Phase 5 Slice 9 实施完成，单项回归兼容修正待确认（最新接续入口）
- [Scope] worker.py/broker.py/0017/test_review_worker.py；ReviewOutbox scoped retry/claim fields。用户已批准 Redis Streams 替代 Celery及模型迁移；无依赖安装，其他生产代码未改。
- [Flow] durable claim commit→loopback XADD→ACK后 dispatched；消费者 lease commit→注入 handler→result commit→ACK。复用 attempt.lease_until、version fence、预算默认拒绝重试、bounded backoff/reaper；无真实 diff/provider/publisher 接线。
- [Command] cwd=apps/api，P=/opt/homebrew/Caskroom/miniconda/base/envs/codex/bin/python；`$P -m pytest tests/test_review_worker.py -q --junitxml=/tmp/phase5-slice9-worker-results.xml` 51 passed exit0；`/tmp/phase5-slice9-final-tests.FwUzz3`。
- [Regression] domain/jobs/webhook/installations/installation_list/settings 六文件pytest：288 passed、1 failed exit1，`/tmp/phase5-slice9-regression.Eu9ILP`；完整命令/结果在 canonical Slice9 log。勿报全部通过。
- [Pending approval] 原 Slice8 test_migration_downgrade_refuses_to_delete_inbox_history 的 upgrade head 与硬编码0016冲突；拟仅 setup pin0016。`/tmp/phase5-slice9-test-compatibility.diff` 尚未应用，已向用户询问原文件byte保护例外；其他内容不变。不能自行假定答复。
- [Gates] scoped Ruff check/format同5文件 exit0，`/tmp/phase5-slice9-final-lint.8zgHjC`；git diff --check exit0。0017 roundtrip/旧行保留/failed或claimed拒绝downgrade已测。
- [Runtime] Redis7.4.11 loopback真实stream验证、AOF已启用；未重启Redis或验证断电恢复。用 RedisStreamsBroker.local→initialize，再注入 sessions/handler/budget_gate 后 run_worker；不以假handler消费真实job。
- [Protection] /tmp/phase5-slice9-approved-89vnmx0_ 49文件快照；45 unrelated byte-identical，模型其他class源码保持，handover仅追加。初始47文件快照 /tmp/phase5-slice9-ujt6k9ef。DB/UUID test stream均0，/tmp/phase5-slice9-cleanup.json。
- [Boundary] main=5b6f7d5f7440e9d7ebbb4e648988102f0f3c6a93，未提交/staging空；无外网/GitHub/provider/生产/commit/push/deploy。canonical已续写准确待确认状态。
- [Next Step] 等上述一行test修正许可；批准后应用proposal、重跑相关回归/静态门禁/cleanup，追加最终验收。Slice10仍待单独授权。


## 2026-09-19：Phase 5 Slice 9 本地完成（最新接续入口，未提交）
- [Scope] Redis Streams broker、事务outbox派发、lease/reaper、bounded retries、0017；用户批准Redis替代Celery及模型迁移。未来diff/provider/publisher尚未接线。
- [Approval] 本次获准仅将Slice8 test_migration_downgrade_refuses_to_delete_inbox_history的upgrade head改为0016；全文其他内容不变，已应用。前节待确认状态已取代，勿重复apply proposal。
- [Command] cwd=apps/api，P=/opt/homebrew/Caskroom/miniconda/base/envs/codex/bin/python；既有 `$P -m pytest tests/test_review_worker.py -q --junitxml=/tmp/phase5-slice9-worker-results.xml` 51 passed exit0；/tmp/phase5-slice9-final-tests.FwUzz3，worker未再改。
- [Command] `$P -m pytest tests/test_review_domain.py tests/test_review_jobs.py tests/test_review_webhook_api.py tests/test_review_installations_api.py tests/test_review_installation_list_api.py tests/test_review_settings_api.py -q --junitxml=/tmp/phase5-slice9-regression-results.xml` 289 passed exit0；/tmp/phase5-slice9-approved-regression.tpkGXP。
- [Gates] 原5文件Ruff check/format exit0；本次webhook test Ruff check --no-cache/format --check exit0；git diff --check exit0。两组共340测试用例通过，非assert执行计数。
- [Verification] 真实loopback Redis+隔离PostgreSQL；claim/lease并发、提交前后可见性、ACK/DB失败、恢复/预算/退避；0017升降级/旧行保留/保护性拒绝降级。AOF开启，未测Redis重启/断电恢复。
- [Protection] /tmp/phase5-slice9-approved-89vnmx0_：44 unrelated字节一致；获准test仅一行，非ReviewOutbox class不变；handover追加。DB/UUID stream剩余0，/tmp/phase5-slice9-final-cleanup.json。
- [Evidence] /tmp/phase5-slice9-complete-reviewed.diff、/tmp/phase5-slice9-complete-audit.json；canonical计划已同步Slice1–9完成、Slice10待授权和最终验收。/tmp可能丢失，命令/结论已写文档。
- [Boundary] main HEAD=5b6f7d5f7440e9d7ebbb4e648988102f0f3c6a93；未提交/staging空；无外网、GitHub/provider、生产、commit/push/deploy。
- [Next Step] 建议 /compact 或新会话后读本节；Slice10 Diff获取/过滤/定位需单独授权，不自动执行。


## 2026-09-19：Phase 5 Slice 10 本地完成（最新接续入口，未提交）
- [Scope] 新增 services/review/diff.py、schemas/review_diff.py、tests/test_review_diff.py；canonical 计划已追加最终验收并同步 Slice1–10 完成/Slice11待授权。
- [Contract] ReviewDiffGitHubClient 复用固定 origin adapter；repository ID + PR head 校验→固定 base...head compare diff→metadata 再校验→PreparedDiff。使用 job frozen policy；不读取 webhook URL/live rules、不接 worker/provider。
- [Behavior] bounded unified diff parser，added/deleted/rename/UTF8，line/side/position/comment_context；DP glob、lock/binary/generated heuristics；min/max lines/files/context、missing coverage/truncation。included 是 selected changed lines，不是实际 LLM 分析；坏/超大输入 fail closed。
- [Command] cwd=apps/api；P=/opt/homebrew/Caskroom/miniconda/base/envs/codex/bin/python；`$P -m pytest tests/test_review_diff.py tests/test_github_app_client.py -q --junitxml=/tmp/phase5-slice10-results.xml`：155 passed exit0（78+77）；/tmp/phase5-slice10-final.sBkFs3。
- [Gates] `$P -m ruff check --no-cache src/plutolab_api/services/review/diff.py src/plutolab_api/schemas/review_diff.py tests/test_review_diff.py`；同三文件 `ruff format --check`；`git diff --check` 均 exit0。
- [Protection] 开工51 dirty/untracked文件，/tmp/phase5-slice10-utf6wjv3；50非handover既有文件byte-identical，handover只追加。无DB/stream创建或遗留，无外网/真实GitHub/私钥/生产修改，无commit/push/deploy。
- [Evidence] /tmp/phase5-slice10-final-audit.json、/tmp/phase5-slice10-code.diff、/tmp/phase5-slice10-results.xml；临时证据可能丢失，核心命令/结果已写canonical。
- [Boundary] 全部HTTP为MockTransport；没有真实GitHub行为验收、files分页补全/目标全文上下文、provider预算分块/worker编排。compare固定SHA防mutable diff竞态；生成代码检测启发式。
- [Next Step] 建议 /compact 或新会话；Slice11 provider-aware chunk/费用预算仍需独立授权。复用 fetch_review_diff(client, ReviewIdentity) 与 PreparedDiff；后续编排处理 stale_head，不自动推进 slice。


## 2026-09-19：Phase 5 Slice 11 本地完成（最新接续入口，未提交）
- [Scope] 新增 services/review/chunking.py、services/review/budget.py、tests/test_review_chunking_budget.py；canonical已同步Slice1–11完成/Slice12待授权并追加验收。
- [Contract] plan_chunks(PreparedDiff, ReviewPolicy, ProviderProfile, system_prompt=..., owner_remaining_usd=...) → immutable ChunkPlan。profile必须显式model/价格版本/输入输出价格/context/output cap/framing；测试仅synthetic，无真实provider配置。
- [Behavior] 同文件相邻hunk greedy packing、源顺序优先；过大hunk显式跳过、允许后续较小hunk；old/new path/range/line/side/position不丢。JSON excerpts而非完整可apply patch，Slice10已丢行不臆造定位。
- [Budget] UTF8 byte conservative estimate + 全payload/prompt/metadata + framing + 每chunk output reserve；per-request/context/chunk/total token与Decimal微美元向上取整费用硬门禁。拒绝不改totals；owner余额由可信caller提供，非持久/并发跨job扣费账本，非真实usage校准。
- [Coverage] admitted chunks + 全hunk/file included/skipped_budget/skipped_filter；精确Fraction比例及省略reason。reviewed_line_ratio是计划选入，不是provider已执行；尚未接worker/provider。
- [Command] cwd=apps/api，P=/opt/homebrew/Caskroom/miniconda/base/envs/codex/bin/python；`$P -m pytest tests/test_review_chunking_budget.py -q --junitxml=/tmp/phase5-slice11-results.xml`：57 passed exit0；/tmp/phase5-slice11-final-tests.1siMNP。
- [Regression] `$P -m pytest tests/test_review_diff.py -q --junitxml=/tmp/phase5-slice11-regression.xml`：78 passed exit0；/tmp/phase5-slice11-regression.wO6isP；合计135用例，非assert计数。
- [Gates] `$P -m ruff check --no-cache src/plutolab_api/services/review/chunking.py src/plutolab_api/services/review/budget.py tests/test_review_chunking_budget.py`；同文件 `ruff format --check`、git diff --check均exit0；/tmp/phase5-slice11-final-lint.UaFFFO。
- [Protection] 开工54既有dirty/untracked，/tmp/phase5-slice11-de2wo9zx；53非handover文件byte-identical、handover只追加。无DB/stream创建、外网/LLM/GitHub/production、commit/push/deploy。
- [Evidence] /tmp/phase5-slice11-final-audit.json、/tmp/phase5-slice11-code.diff 与两份JUnit；/tmp可能丢失，核心结果/命令已写canonical。
- [Next Step] 建议 /compact 或新会话；Slice12需单独授权。真实provider profile/价格/framing、usage与执行/重试持久预留待后续核验；不因本地planner通过而自动调用LLM或开始下一slice。

## 2026-09-23：Phase 5 Slice 12 本地完成；验收日志按日整理（最新接续入口，未提交）
- [Scope] 新增 schemas/review_analysis.py、services/review/analyzer.py、services/review/linter.py、tests/test_review_analysis.py；严格结构化 findings、已验证 diff line 映射/显式 clamp、注入式异步 provider、可选有界 Python AST 语法检查。
- [Behavior] Provider JSON 限 256KB/200 findings，拒绝重复 key、坏 JSON、额外字段/危险路径；错误与 timeout 降为 partial 并继续其他 chunk。Static check 只 parse 调用方提供的 changed .py 源码，不执行。
- [Tests] cwd=apps/api，codex Python -m pytest tests/test_review_analysis.py -q --junitxml=/tmp/phase5-slice12-results.xml：12 passed，exit0；日志 /tmp/phase5-slice12-tests.CiAjRZ。
- [Gates] scoped 四文件 Ruff check、Ruff format check、repo git diff --check 均 exit0；无数据库/Redis/外网/真实 provider/GitHub。
- [Docs] 新增 MyNotes/Projects/项目/PlutoLab/Logs/2026-09-23-Phase5-Execution.md，承接 Slice1–11 原始验收记录并追加 Slice12；主计划缩为概览/状态/相对日志链接，保持 YAML 与 wikilinks；本条同步执行记录。
- [Protection] 开工快照57个既有 dirty/untracked 路径 /tmp/phase5-slice12-preserve/manifest.json；既有代码/测试字节保持一致，handover 仅追加；计划重组与新日志为获准文档改动。无 commit/push/deploy。
- [Boundary] 本地 mocks only；不接 Slice13 pipeline/ReviewJob persistence，不声称真实 provider 输出、价格或 usage 已验收。
- [Next Step] Slice13 仍需单独授权；建议 /compact 或新会话，从本卡及 Phase5 每日执行日志继续。

## 2026-09-23: Phase 5 Slice 13 本地完成；Slice 14 仍需独立授权

- [Scope] 新增 `apps/api/src/plutolab_api/services/review/orchestrator.py` 与 `apps/api/tests/test_review_orchestrator.py`；把 pinned diff、budget/chunk、structured analysis 串为现有 worker Consumer 可注入 handler，结果交还既有 `finish_analysis` 持久化。
- [State/Recovery] 通过 `ReviewAttempt.evidence` 写入短事务阶段 checkpoint；按 head/payload hash 复用完整与 partial chunk 结果；新 head 抢占后标记 `superseded`；chunk retry 有界并计入 token/cost 上限。analysis 不触发 publication。
- [Tests] codex `python -m pytest tests/test_review_orchestrator.py -q --junitxml=/tmp/phase5-slice13-orchestrator-results.xml`：5 passed，exit 0；Ruff check/format 与 repo `git diff --check` exit 0。测试为本地 fake provider/GitHub 与 mock checkpoint。
- [DB Boundary] 曾尝试 Slice 3/9 风格隔离 PostgreSQL fixture，但 loopback `localhost:5432` 在 disposable DB 创建前超时；没有数据库创建/遗留。本轮没有重跑 DB-backed worker/persistence 套件。
- [Protection] 开工快照 61 个 dirty/untracked 路径：`/tmp/phase5-slice13-preserve/manifest.json`；只新增上述两个文件，既有代码与测试维持原字节；本交接只追加。Phase 5 Obsidian 执行记录已归并至 `开发日志/2026-09-23 Phase 5 AI 代码评审实施日志.md`，计划已改为相对链接，冗余 `Logs/` 已清理。无外部网络、真实 provider/GitHub、migration、commit/push/merge/deploy。
- [Next Step] Slice 14 评论映射/发布预览等待独立授权；建议在下一切片前 `/compact` 并核对最新交接与工作区。

## 2026-09-23: Phase 5 Slice 14 本地完成；真实发布仍未执行

- [Scope] 新增 `apps/api/src/plutolab_api/services/review/publisher.py`、`schemas/review_publication.py` 与 `tests/test_review_publisher.py`。按已验证 pinned diff 精确映射 inline 评论；summary 汇总风险、coverage、跳过原因及 findings，并保留稳定 job/head marker。
- [Idempotency/State] 查询已有 PR review 与 issue comments，marker 命中即复用 receipt；inline 422 安全回退到 top-level summary 并记为 `partially_published`。发布 attempt 与 receipt 经过现有 guarded jobs 状态服务；`analysis_status` 不变，timeout/未知写入标为 `publish_unknown`。
- [Tests] cwd=apps/api，codex Python `-m pytest tests/test_review_publisher.py -q`：5 passed，exit 0；仅本地 fake GitHub。
- [Gates] 三个新增文件 scoped Ruff check/format check、repo `git diff --check` 均 exit 0；新文件 no-index whitespace checks clean。
- [Protection] 开工快照 63 个 dirty/untracked 路径 `/tmp/phase5-slice14-preserve/manifest.json`；代码基线文件逐字节一致，handover/log 仅追加。无外网、真实 GitHub/LLM、DB、commit/push/deploy。
- [Next Step] Slice 14 本地实现完成；真实 GitHub 发布与运行时适配仍未执行，需独立授权及 adapter 接线。建议 `/compact` 或新会话后核对工作区与 handover。

## 2026-09-23: Phase 5 Slice 15 本地完成；Job Read API 待后续实现

- [Scope] 新增 `/review/jobs` 与 `/review/jobs/[jobId]` 页面、列表/详情 client components、`review-jobs.ts` 展示 helpers、authenticated read client 与 Node interaction/SSR 测试。任务列表支持安装/仓库选择、仓库搜索、PR 编号筛选和分页；详情含任务指标、coverage/truncation、severity/focus findings、已验证 diff reference、suggestion 与 publication state。
- [UI States] 安装/仓库无数据 empty state，loading skeleton、接口错误与重试；partial delivery 明确提示，只有 API 提供 `fallback_reason=diff_position_mismatch` 才标识 422 fallback，避免推断原因。
- [Tests] `pnpm --filter @plutolab/web test`：58 passed，exit 0（新增 7）；`pnpm --filter @plutolab/web typecheck`、Slice15 scoped Prettier check、`git diff --check` 均 exit 0。
- [Integration Gap] 当前 `apps/api/src/plutolab_api/api/v1/review.py` 未实现 jobs list/detail GET routes；新 read client 所用路径是明确的 owner-scoped contract。UI 对 404 提供说明与 retry，但真实任务数据需待授权实现后端读取端点。当前 publisher receipt 不包含 fallback reason，422 专属文案暂依赖后端补充该字段。
- [Protection] 开工快照 66 个 dirty/untracked 路径 `/tmp/phase5-slice15-preserve/manifest.json`；既有文件 SHA-256 全部相同；本 handover 与开发日志仅追加。无外网、真实 GitHub、commit/push/deploy。
- [Next Step] 若需真实任务数据，后续独立授权增加 owner-scoped job list/detail API 与持久化 422 fallback reason；Slice15 Web 合约和本地 mock 验收已完成。建议 `/compact` 或新会话接续。

## 2026-09-23: Phase 5 Integration — Owner-Scoped Job Reads & Fallback Persistence

- [Scope] Implemented authenticated `GET /api/v1/review/jobs` and `GET /api/v1/review/jobs/{job_id}`. Both enforce active installation ownership; detail reads conceal cross-owner and revoked-installation jobs with 404. List supports bounded pagination, status, installation, repository and PR filters.
- [Persistence/Contract] Added `ReviewJob.publication_fallback_reason` and Alembic 0018 with a constrained nullable value. Publisher receipts and idempotent markers preserve exact `diff_position_mismatch` telemetry. Web API/types consume the same routes and top-level field. `verified_diff` is nullable and currently null because stable diff positions are not persisted yet.
- [Verification] `python -m pytest tests/test_review_jobs_api.py tests/test_review_jobs.py tests/test_review_publisher.py -q`: 64 passed, exit 0. API migration test upgraded to head, downgraded to 0017, re-upgraded and cleaned up its disposable database. `pnpm test`: 58 passed, exit 0; `pnpm typecheck`: exit 0; scoped Ruff and formatting checks: exit 0; scoped Prettier: exit 0. `git diff --check` completed in this handover.
- [Protection] Existing unrelated dirty files were preserved against the pre-edit SHA-256 manifest; only the authorized API/model/schema/service, migration/test, and Web job-contract files were changed. No outbound calls, real GitHub operations, commits, pushes or deployments.
- [Next Step] Integration endpoints and fallback persistence are locally verified. Inline verified-diff references need a future persistence contract before the Web UI can display exact GitHub positions. Suggested `/compact` or fresh session for the next authorized slice.


## 2026-09-23: Phase 5 Slice 16 Local Completion

- [Scope] Added migration 0019 and a bounded, head-bound `ReviewJob.verified_diff` snapshot. Orchestrator emits exact finding line/side/position/context mappings; result persistence stores them atomically with findings; owner-scoped detail returns only mappings matching the finding.
- [E2E] `apps/api/tests/test_review_e2e_pipeline.py` passes the signed webhook → outbox dispatcher → worker lease → diff/filter/budget → mock analysis/AST → mocked 422 fallback publisher → authenticated detail read chain. Web SSR covers `verified_diff: null` without a rendering error.
- [Gates] Backend `python -m pytest tests/test_review_*.py -q`: 503 passed, exit 0. Web tests: 58 passed, exit 0; Web typecheck, scoped Ruff/format, Prettier and `git diff --check`: exit 0. Migration 0019 upgrade/downgrade/re-upgrade passed on a disposable PostgreSQL database, dropped by its fixture.
- [Compatibility] With user approval, updated only the legacy Slice 8 migration fixture to insert a schema-0015 job using 0015 columns; its 0015↔0016 data-preservation assertions remain.
- [Boundary] Local fake broker and mock GitHub/provider only; zero leftover disposable review databases and 451 temporary migration/test log artifacts removed; no outbound service calls, commits, pushes or deployments. Phase 5 local scope is signed off; real service sandbox and PR/main closure remain out of scope.
- [Next Step] No further local Phase 5 implementation gates remain for the approved scope. Suggested `/compact` or a fresh session before unrelated work.

## 2026-09-23: Phase 5 Closure Archive and Workspace Audit

- [Sign-off] Phase 5 local implementation and full-chain verification are signed off and archived. This sign-off covers local mocks and local acceptance only; sandbox GitHub App installation, live webhook delivery, real PR publication, CI on a remote branch, merge, and deployment remain future operational milestones requiring their own authorization.
- [Inventory] The 70 Phase 5-associated worktree paths are: Alembic `0013_create_review_settings.py` through `0019_add_review_verified_diff.py`; API `api/v1/review.py`, `api/v1/router.py`, `core/config.py`, `core/github_app.py`, `models/__init__.py`, `models/review.py`, schemas `review.py`, `review_analysis.py`, `review_diff.py`, `review_jobs.py`, `review_publication.py`; services `services/review/{__init__,analyzer,broker,budget,chunking,diff,github_client,installations,jobs,linter,orchestrator,publisher,settings,webhook,worker}.py`; tests `test_github_app_client.py` plus fourteen files `test_review_analysis.py`, `test_review_chunking_budget.py`, `test_review_diff.py`, `test_review_domain.py`, `test_review_e2e_pipeline.py`, `test_review_installation_list_api.py`, `test_review_installations_api.py`, `test_review_jobs.py`, `test_review_jobs_api.py`, `test_review_orchestrator.py`, `test_review_publisher.py`, `test_review_settings_api.py`, `test_review_webhook_api.py`, `test_review_worker.py`; Web routes `apps/web/src/app/(site)/review/page.tsx`, `apps/web/src/app/(site)/review/settings/page.tsx`, `apps/web/src/app/(site)/review/jobs/page.tsx`, `apps/web/src/app/(site)/review/jobs/loading.tsx`, `apps/web/src/app/(site)/review/jobs/error.tsx`, `apps/web/src/app/(site)/review/jobs/[jobId]/page.tsx`, `apps/web/src/app/(site)/review/jobs/[jobId]/loading.tsx`, `apps/web/src/app/(site)/review/jobs/[jobId]/error.tsx`; components `repository-browser.tsx`, `review-job-detail.tsx`, `review-jobs.tsx`, `review-settings.tsx`, `rule-editor.tsx`; libraries `review-jobs-api.ts`, `review-jobs.ts`, `review-rules.ts`, `review.ts`; tests `review-jobs.test.mjs`, `review-settings.browser.js`, `review-settings.test.mjs`; shared contract `packages/types/src/review.ts`; and this handover. `apps/api/src/plutolab_api/services/__init__.py` and other Copilot/Notes/Tasks paths are unrelated/mixed work and are deliberately excluded from the Phase 5 proposal.
- [Audit] Before this closure entry, the worktree had 82 unstaged/untracked paths and zero staged paths. Nineteen enumerated Python cache directories (`__pycache__`, pytest, Ruff, mypy) were removed. No repository SQLite/Postgres log artifacts or Phase 5-named temporary logs were found; disposable migration databases were dropped by the verified test fixtures. No source, test, migration, or user-created database file was cleaned.
- [Verification Evidence] The signed-off full-chain record above remains authoritative: backend `tests/test_review_*.py` 503 passed; Web 58 passed; Web typecheck, scoped Ruff/format, Prettier, migration 0019 round-trip, and `git diff --check` exit 0. No verification was rerun during this audit.
- [Commit Proposal — NOT EXECUTED] Backend: `feat(review): add owner-scoped review pipeline`; files are the seven migrations `apps/api/alembic/versions/0013_create_review_settings.py` through `0019_add_review_verified_diff.py`, `apps/api/src/plutolab_api/api/v1/review.py`, `apps/api/src/plutolab_api/api/v1/router.py`, `apps/api/src/plutolab_api/core/config.py`, `apps/api/src/plutolab_api/core/github_app.py`, `apps/api/src/plutolab_api/models/__init__.py`, `apps/api/src/plutolab_api/models/review.py`, all five `apps/api/src/plutolab_api/schemas/review*.py` files, and all fifteen `apps/api/src/plutolab_api/services/review/*.py` files. Do not stage `services/__init__.py`.
- [Commit Proposal — NOT EXECUTED] Web: `feat(web): add review settings and job views`; files are all Phase 5 files under `apps/web/src/app/(site)/review/`, `apps/web/src/components/review/`, `apps/web/src/lib/review*.ts`, all three `apps/web/tests/review*.{mjs,js}` files, and `packages/types/src/review.ts`.
- [Commit Proposal — NOT EXECUTED] Tests: `test(review): cover lifecycle and recovery`; files are `apps/api/tests/test_github_app_client.py` and the fourteen `apps/api/tests/test_review_*.py` files listed in the inventory above.
- [Commit Proposal — NOT EXECUTED] Docs: `docs(review): archive Phase 5 local sign-off`; stage only the new closure/archive hunk from `SESSION_HANDOVER.md`, preserving its earlier unrelated history. The proposed commands and exact paths are for review only; no `git add`, commit, push, or deployment was run.
- [Next Milestones] 1) Prepare an isolated GitHub App sandbox with least-privilege permissions and test repository; 2) validate CI on a review branch using local fixture secrets/mocks and approved sandbox credentials; 3) obtain separate approval before any live webhook/PR publication; 4) define and authorize the next phase after sandbox findings. Do not infer production readiness from local sign-off.
- [Next Step] Review the proposed commit boundaries and explicitly authorize staging/commits if desired; until then, leave the complete worktree unstaged. Suggested `/compact` or a fresh session before the next phase.
