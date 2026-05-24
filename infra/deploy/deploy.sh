#!/usr/bin/env bash
# PlutoLab — VPS 部署一键脚本
# 用法 (在 VPS 上, /home/pluto/plutolab 目录内):
#   bash infra/deploy/deploy.sh
#
# 行为:
#   1. git pull 最新代码
#   2. docker compose build (会因为 NTFS 跨界没 NTFS, Linux 原生快)
#   3. docker compose up -d
#   4. 等 healthcheck + 跑 alembic + curl 验证

set -euo pipefail

cd "$(dirname "$0")/../.."
ROOT=$(pwd)
COMPOSE_FILE=docker-compose.prod.yml

echo "════════════════════════════════════════"
echo "  PlutoLab Deploy — $(date -u +%FT%TZ)"
echo "════════════════════════════════════════"

echo ''
echo '[1/5] git pull...'
git fetch origin
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse @{u})
if [ "$LOCAL" = "$REMOTE" ]; then
  echo "  Already up to date: $(git log --oneline -1)"
else
  git pull --ff-only
  echo "  Updated: $LOCAL → $(git rev-parse HEAD)"
fi

echo ''
echo '[2/5] 检查 .env.prod...'
if [ ! -f .env.prod ]; then
  echo '  ⚠️  .env.prod 不存在, 用 .env.prod.example 作模板'
  cp .env.prod.example .env.prod
  echo '  请编辑 .env.prod 填入真实密码后重新跑此脚本'
  exit 1
fi

echo ''
echo '[3/5] docker compose build (首次 5-10 分钟, 后续增量很快)...'
docker compose -f "$COMPOSE_FILE" --env-file .env.prod build 2>&1 | tail -20

echo ''
echo '[4/5] docker compose up -d...'
docker compose -f "$COMPOSE_FILE" --env-file .env.prod up -d 2>&1 | tail -10

echo ''
echo '[5/5] 等服务 ready + 验证...'
for i in $(seq 1 30); do
  sleep 2
  if curl -sf --max-time 2 http://localhost/api/v1/health > /dev/null 2>&1; then
    echo "  ✅ API ready at [${i}*2s]"
    break
  fi
done

echo ''
echo '--- 容器状态 ---'
docker compose -f "$COMPOSE_FILE" ps

echo ''
echo '--- 验证 ---'
echo -n '  / (前端): '
curl -sI --max-time 3 http://localhost/ -o /dev/null -w 'HTTP %{http_code}\n' || echo FAIL
echo -n '  /api/v1/health (后端): '
curl -s --max-time 3 http://localhost/api/v1/health || echo FAIL
echo ''
echo -n '  /docs (Swagger): '
curl -sI --max-time 3 http://localhost/docs -o /dev/null -w 'HTTP %{http_code}\n' || echo FAIL

echo ''
echo '════════════════════════════════════════'
echo '  Deploy DONE — 浏览器开:'
echo "    http://$(curl -s ifconfig.me 2>/dev/null || echo 23.95.25.153)/"
echo '════════════════════════════════════════'
