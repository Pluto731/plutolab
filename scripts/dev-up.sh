#!/usr/bin/env bash
# PlutoLab — 一键拉起开发环境 (用 setsid -f 真正 detach, 不会死)
set +e

cd /mnt/e/Learning/LLM/04-AI-Apps/plutolab

echo '[1/4] docker daemon...'
service docker start 2>&1 | tail -2
sleep 2

echo ''
echo '[2/4] docker compose up...'
docker compose up -d 2>&1 | tail -5

echo ''
echo '[3/4] FastAPI backend (setsid, port 8000)...'
pkill -9 -f 'uvicorn plutolab_api' 2>/dev/null
sleep 1
(cd apps/api && setsid -f ./.venv/bin/uvicorn plutolab_api.main:app --host 0.0.0.0 --port 8000 < /dev/null > /tmp/uvicorn.log 2>&1)

echo ''
echo '[4/4] Next.js dev (setsid, port 3000, 首次编译 ~30s)...'
pkill -9 -f 'next dev' 2>/dev/null
pkill -9 -f 'next-server' 2>/dev/null
sleep 1
(cd apps/web && setsid -f ./node_modules/.bin/next dev --hostname 0.0.0.0 --port 3000 < /dev/null > /tmp/next-dev.log 2>&1)

sleep 3
echo ''
echo '进程:'
pgrep -af 'uvicorn plutolab_api' | head -1
pgrep -af 'next-server|next dev' | head -2
echo ''
echo '=== launched, waiting for ready... ==='
