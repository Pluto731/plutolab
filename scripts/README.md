# Scripts

辅助脚本。在 **WSL Ubuntu** 内运行（不是 Windows PowerShell）。

| 脚本 | 用途 | 何时跑 |
|---|---|---|
| `setup-docker-mirrors.sh` | 给 WSL docker daemon 配国内镜像源 + 拉 PlutoLab 三个镜像 | 第一次 setup / docker daemon.json 丢失时 |
| `verify-stack.sh` | 启动 docker compose + 验证 postgres/pgvector/redis/adminer | 每次开机后 / 修改 compose.yml 后 |

## 使用

```bash
# 在 WSL Ubuntu 内
cd /mnt/e/Learning/LLM/04-AI-Apps/plutolab
sudo bash scripts/setup-docker-mirrors.sh     # 首次
sudo bash scripts/verify-stack.sh             # 日常
```

或在 Windows PowerShell 里一行调用：

```powershell
wsl -d Ubuntu -- bash /mnt/e/Learning/LLM/04-AI-Apps/plutolab/scripts/verify-stack.sh
```

## 前提

WSL Ubuntu 里已装：
- `docker.io` (Ubuntu 维护版 Docker Engine)
- `docker-compose-v2`

装法：`sudo apt install docker.io docker-compose-v2`（清华源会很快）。
