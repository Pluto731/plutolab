# 🪐 PlutoLab 新会话无缝接续交接备忘录 (Session Handover Memo)

> [!important] 新会话冷启动使用指南
> 当你在 Antigravity 或 Claude Code 中开启一个**全新会话**时，只需在第一条消息直接发送：
> 
> ```text
> 请读取 PlutoLab 项目的 SESSION_HANDOVER.md 以及 Obsidian 中的 Phase 4 执行手册，按照四阶段工作流继续进行下一个微切片开发。
> ```
> 
> AI 读完本文件与对应手册，将在 5 秒内 100% 满血加载全部上下文记忆，无需从头介绍项目！

---

## 1. 项目基础与核心环境配置

- **本地仓库根目录**：`/Users/pluto/project/Pluto/plutolab`
- **Obsidian 笔记根目录**：`/Users/pluto/MyNotes/Projects/项目/PlutoLab`
  - [[Phase 4 切片清单 (执行手册)]]
  - [[Phase 4 - RAG 文档问答]]
  - [[Agent 架构升级与深度融合设计]]
  - [[里程碑与进度]]
- **Python 运行环境**：必须且仅使用 **`gemini`** Conda 环境：
  `/opt/homebrew/Caskroom/miniconda/base/envs/gemini/bin/python`
  `/opt/homebrew/Caskroom/miniconda/base/envs/gemini/bin/pytest`
- **前端工具链**：`pnpm` / Turbopack
- **远程 VPS 生产环境**：
  - 公网 IP: `107.175.190.218` (SSH: `ssh vps` 或 `ssh -p 52222 pluto@107.175.190.218`)
  - 远程代码路径: `/home/pluto/plutolab`
  - 容器服务: `plutolab-prod-caddy`, `plutolab-prod-web`, `plutolab-prod-api`, `plutolab-prod-postgres` (pgvector:pg16), `plutolab-prod-redis`
  - 线上访问入口:
    - 登录前台: `http://107.175.190.218/login`
    - Swagger API 文档: `http://107.175.190.218/docs`

---

## 2. 当前研发进度状态 (截至 2026-09-04)

- **当前分支**：`main` (与 `origin/main` 保持最新同步)
- **最新 Git Commit**：`65b76df` (`feat(rag): implement Fernet key decryption and EmbeddingService (phase 4.2.c)`)
- **自动化测试状态**：
  - 后端 pytest 全量通过：**`267 passed, 265 warnings`** (100% 满分无回退)
  - 前端 `pnpm typecheck`：通过 (零错误)
- **生产数据库迁移版本**：`0012_create_rag_tables` (本地与 VPS 生产均已应用)

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
| **Phase 4.3.a** | HNSW 向量 + 倒排混合检索 (HybridRetriever) | ⏳ **下一目标** | 结合 pgvector `<=>` 与 `to_tsvector`，RRF (k=60) 融合打分 |

---

## 3. 四阶段工作流强制执行规则

每个微切片研发必须且严格遵循四个阶段：
1. **阶段 1：方案设计与计划记录（前置门禁）**
   - 必须先在 `/Users/pluto/MyNotes/Projects/项目/PlutoLab/开发日志/` 新建对应切片日志。
   - 明确背景目标、代码设计蓝图、Checklist 与风险预案。未写笔记严禁动代码！
2. **阶段 2：规范编码与自查**
   - 编写实现代码与全覆盖单测，运行单测与全量回归确保 100% 绿灯。
3. **阶段 3：沉淀开发日志与复盘**
   - 详细回填开发日志：记录写了什么具体类/函数、做了什么关键事、ADR 决断。
   - 提交 Git Commit 并推送，SSH 到 VPS 执行更新部署。
4. **阶段 4：执行复核与交付**
   - 逐项复核交付看板，更新执行手册与主需求笔记。
