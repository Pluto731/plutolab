# plutolab-api

PlutoLab 后端 — **FastAPI** + Pydantic v2 + structlog + uvicorn。

> 🧪 当前状态: **Phase 0.3.a** —— 仅 `/health` 路由，DB 接入留到 Phase 0.3.b。

## 目录结构

```
apps/api/
├── pyproject.toml        # uv 项目配置
├── .python-version       # 3.11
├── .env / .env.example   # 环境变量
├── src/plutolab_api/
│   ├── main.py           # FastAPI app 入口
│   ├── core/
│   │   ├── config.py     # Pydantic Settings (读 .env)
│   │   └── logging.py    # structlog 配置
│   └── api/v1/
│       ├── router.py     # v1 路由聚合
│       └── health.py     # GET /api/v1/health
└── tests/
    └── test_health.py    # smoke test
```

## 本地开发 (在 WSL Ubuntu 内)

```bash
cd /mnt/e/Learning/LLM/04-AI-Apps/plutolab/apps/api

# 装依赖 (uv 自动拉 Python 3.11 + 建 .venv + 锁版本)
uv sync

# 启动开发服务器 (reload on file change)
uv run uvicorn plutolab_api.main:app --reload --host 0.0.0.0 --port 8000

# 验证
curl http://localhost:8000/api/v1/health
# {"status":"ok","version":"0.0.1","env":"development"}

# 文档
# Swagger:  http://localhost:8000/docs
# ReDoc:    http://localhost:8000/redoc
```

## 测试

```bash
uv run pytest -v
```

## Lint / format

```bash
uv run ruff check .
uv run ruff format .
```

## 从根目录调用

根 `package.json` 已加快捷脚本：

```powershell
pnpm api:install   # 等价 uv sync
pnpm api:dev       # 启动开发服务器
pnpm api:test      # 跑 pytest
```
