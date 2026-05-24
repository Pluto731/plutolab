# CI Workflows

GitHub Actions 持续集成配置。

## `ci.yml`

每次 `push` 到 main 或 `pull_request` 到 main 触发。两个 job 并行跑：

### Backend (FastAPI)

- **服务**: `pgvector/pgvector:pg16`（5432 端口暴露 + healthcheck）
- **步骤**:
  1. checkout
  2. 装 uv (含缓存, key = `apps/api/uv.lock`)
  3. 拉 Python 3.11
  4. `uv sync --frozen` (锁版本)
  5. 在 postgres 服务里建 4 个扩展 (vector / pgcrypto / unaccent / pg_trgm)
  6. `ruff check` + `ruff format --check`
  7. `alembic upgrade head` (验证 migration)
  8. `pytest -v --tb=short` (3 个 smoke test)

### Frontend (Next.js)

- **步骤**:
  1. checkout
  2. 装 pnpm 11
  3. 装 Node 22 (含 pnpm store 缓存)
  4. `pnpm install --frozen-lockfile`
  5. `pnpm --filter @plutolab/web typecheck` (tsc --noEmit)
  6. `pnpm --filter @plutolab/web build` (Next.js production build)

## 优化

- **`concurrency` 取消旧 job**: 同一 PR push 新 commit 时，旧 job 立即取消，省 GH minutes
- **uv 自带缓存**: setup-uv 用 lock 文件 hash 作 cache key
- **pnpm store 缓存**: `actions/setup-node` 的 `cache: pnpm` 自动处理

## Badge

仓库主页 README 显示 CI 状态:

```markdown
![CI](https://github.com/Pluto731/plutolab/actions/workflows/ci.yml/badge.svg)
```

## 失败排查

- **psql command not found**: ubuntu-latest 默认装 postgresql-client，应该有
- **uv 找不到**: 检查 `astral-sh/setup-uv` 版本，可能要 pinned 版本号
- **pnpm install 失败**: 看是不是 `pnpm-lock.yaml` 过期 (在本地 `pnpm install` 再 commit lockfile)
- **pytest DB 连接失败**: postgres 服务还没 ready，health check 已经在了应该 OK
