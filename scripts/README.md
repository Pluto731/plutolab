# Scripts

辅助脚本。全部在 **WSL Ubuntu** 内运行（Windows PowerShell 调用时用 `wsl -d Ubuntu -- bash <path>`）。

## 一键启动 (日常)

| 脚本 | 用途 |
|---|---|
| **`dev-up.sh`** | **一键拉起**: docker daemon + docker compose + FastAPI (uvicorn) + Next.js dev — 用 `setsid -f` 真正 detach |

```powershell
# Windows PowerShell 一行启动所有
wsl -d Ubuntu -- bash /mnt/e/Learning/LLM/04-AI-Apps/plutolab/scripts/dev-up.sh

# 30-60 秒后浏览器开:
# http://localhost:3000   PlutoLab 前端
# http://localhost:8000/docs   Swagger UI
# http://localhost:8080   Adminer (DB GUI)
```

## 安装 / 配置 (一次性)

| 脚本 | 用途 |
|---|---|
| `setup-python.sh` | 装 uv (Python 包管理器) |
| `setup-wsl-pnpm.sh` | 装 pnpm + 在 WSL 里跑 pnpm install (前端依赖) |
| `setup-docker-mirrors.sh` | 给 WSL docker daemon 配国内镜像源 + 拉 PlutoLab 镜像 |

## 验证 / 测试

| 脚本 | 用途 |
|---|---|
| `verify-stack.sh` | 启动 docker compose + 验证 postgres/pgvector/redis/adminer |
| `verify-api.sh` | `uv sync` + 启动 uvicorn + curl /health + pytest |
| `verify-db.sh` | `uv sync` + alembic upgrade + DB health + pytest |

## 调用模式

```powershell
# Windows PowerShell
wsl -d Ubuntu -- bash /mnt/e/Learning/LLM/04-AI-Apps/plutolab/scripts/<name>.sh
```

或在 WSL Ubuntu 内：

```bash
cd /mnt/e/Learning/LLM/04-AI-Apps/plutolab
bash scripts/<name>.sh
```

## 前提

WSL Ubuntu 里已装（参考 `setup-*.sh` 脚本）：
- `docker.io` + `docker-compose-v2` (apt, 清华源)
- `uv` (Python 包管理器, 官方 installer)
- `pnpm` + `node` + `npm` (npm 全局, npmmirror 国内源)

## 网络注意

| 操作 | TUN |
|---|---|
| `apt install` / `pip install` / `pnpm install` | **关 TUN**（走清华/npmmirror 国内源最快） |
| `git push origin` | **开 TUN**（SSH-over-443 走 GitHub） |
| 日常开发 (dev-up.sh + 浏览器) | 任意（不影响 localhost） |
