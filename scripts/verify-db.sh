#!/usr/bin/env bash
# PlutoLab — 验证 Phase 0.3.b: 装依赖 + 跑 migration + 启动 + curl /db/health + pytest
set +e

export PATH="$HOME/.local/bin:$PATH"
cd /mnt/e/Learning/LLM/04-AI-Apps/plutolab/apps/api

echo '[1/6] uv sync (装新依赖: sqlalchemy / asyncpg / alembic)...'
time uv sync 2>&1 | tail -10

echo ''
echo '[2/6] alembic upgrade head (创建 users 表)...'
uv run alembic upgrade head 2>&1 | tail -15

echo ''
echo '[3/6] 验证 users 表已建...'
docker compose -f /mnt/e/Learning/LLM/04-AI-Apps/plutolab/docker-compose.yml exec -T postgres psql -U pluto -d pluto -c "\d users" 2>&1 | head -20

echo ''
echo '[4/6] 后台启动 uvicorn...'
uv run uvicorn plutolab_api.main:app --host 0.0.0.0 --port 8000 > /tmp/uvicorn.log 2>&1 &
UVICORN_PID=$!
echo "uvicorn PID: $UVICORN_PID"

echo ''
echo '[5/6] 等启动 + curl /api/v1/db/health...'
for i in $(seq 1 15); do
  sleep 1
  if curl -sf --max-time 2 http://localhost:8000/api/v1/db/health > /dev/null 2>&1; then
    echo "  [${i}s] ready"
    break
  fi
done

echo ''
echo '--- /api/v1/health ---'
curl -s --max-time 3 http://localhost:8000/api/v1/health | python3 -m json.tool

echo ''
echo '--- /api/v1/db/health ---'
curl -s --max-time 3 http://localhost:8000/api/v1/db/health | python3 -m json.tool

echo ''
echo '--- uvicorn startup log (前 8 行, 看 DB connected) ---'
head -8 /tmp/uvicorn.log

kill $UVICORN_PID 2>/dev/null
wait $UVICORN_PID 2>/dev/null

echo ''
echo '[6/6] pytest...'
uv run pytest -v 2>&1 | tail -25

echo ''
echo '=== DONE ==='
