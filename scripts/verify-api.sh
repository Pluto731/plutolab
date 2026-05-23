#!/usr/bin/env bash
# PlutoLab — 装 API 依赖 + 启动 + curl 验证 + pytest
set +e

export PATH="$HOME/.local/bin:$PATH"
cd /mnt/e/Learning/LLM/04-AI-Apps/plutolab/apps/api

echo '[1/5] uv sync (装依赖, 首次需要拉 Python 3.11)...'
time uv sync 2>&1 | tail -15

echo ''
echo '[2/5] 后台启动 uvicorn...'
uv run uvicorn plutolab_api.main:app --host 0.0.0.0 --port 8000 > /tmp/uvicorn.log 2>&1 &
UVICORN_PID=$!
echo "uvicorn PID: $UVICORN_PID"

echo ''
echo '[3/5] 等待启动 (最长 15 秒)...'
for i in $(seq 1 15); do
  sleep 1
  if curl -sf --max-time 2 http://localhost:8000/api/v1/health > /dev/null 2>&1; then
    echo "  [${i}s] ready"
    break
  fi
done

echo ''
echo '[4/5] 验证 /api/v1/health...'
echo '--- HTTP status ---'
curl -sI --max-time 3 http://localhost:8000/api/v1/health -o /dev/null -w 'HTTP %{http_code}\n'
echo '--- JSON body ---'
curl -s --max-time 3 http://localhost:8000/api/v1/health | python3 -m json.tool

echo ''
echo '--- OpenAPI 文档 ---'
curl -sI --max-time 3 http://localhost:8000/docs -o /dev/null -w '/docs:       HTTP %{http_code}\n'
curl -sI --max-time 3 http://localhost:8000/openapi.json -o /dev/null -w '/openapi.json: HTTP %{http_code}\n'

echo ''
echo '关闭 uvicorn...'
kill $UVICORN_PID 2>/dev/null
wait $UVICORN_PID 2>/dev/null

echo ''
echo '[5/5] pytest...'
uv run pytest -v 2>&1 | tail -20

echo ''
echo '=== DONE ==='
