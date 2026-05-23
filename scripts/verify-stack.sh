#!/usr/bin/env bash
# PlutoLab — 启动 docker compose + 验证 postgres/pgvector/redis/adminer
set +e

cd /mnt/e/Learning/LLM/04-AI-Apps/plutolab

echo '[1/6] docker compose up -d...'
docker compose up -d 2>&1 | tail -10

echo ''
echo '[2/6] 等 healthcheck 通过 (最长 60 秒)...'
for i in $(seq 1 30); do
  STATUS=$(docker compose ps --format json 2>/dev/null | grep -oE '"Health":"[^"]+"' | sort -u)
  HEALTHY=$(echo "$STATUS" | grep -c 'healthy')
  TOTAL=$(echo "$STATUS" | grep -cE 'healthy|starting|unhealthy')
  echo "  [${i}*2s] healthy/$TOTAL: $STATUS"
  if [ "$HEALTHY" -ge 2 ]; then
    echo "  ✅ at least 2 services healthy"
    break
  fi
  sleep 2
done

echo ''
echo '[3/6] docker compose ps...'
docker compose ps

echo ''
echo '[4/6] 验证 postgres + pgvector + 其他扩展...'
docker compose exec -T postgres psql -U pluto -d pluto -c "SELECT extname, extversion FROM pg_extension ORDER BY extname;" 2>&1

echo ''
echo '[5/6] 验证 redis ping...'
docker compose exec -T redis redis-cli ping

echo ''
echo '[6/6] Adminer 自检 (HTTP 200 = OK)...'
curl -sI --max-time 5 http://localhost:8080 -o /dev/null -w 'HTTP %{http_code}\n'

echo ''
echo '=== STACK READY ==='
echo '🌐 Adminer:  http://localhost:8080  (System=PostgreSQL  Server=postgres  User=pluto  DB=pluto)'
echo '🗄️  Postgres: localhost:5432  (pluto / pluto)'
echo '🔥 Redis:    localhost:6379'
