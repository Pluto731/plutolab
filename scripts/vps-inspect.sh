#!/usr/bin/env bash
# 远程在 VPS 上跑, 看部署环境现状
echo '=== 工具版本 ==='
for c in git docker curl; do
  printf '%-10s ' "$c"
  $c --version 2>&1 | head -1 || echo 'NOT INSTALLED'
done
printf 'docker compose '
docker compose version 2>&1 | head -1 || echo 'NOT INSTALLED'

echo ''
echo '=== 已运行的 docker 容器 ==='
docker ps --format 'table {{.Names}}\t{{.Ports}}\t{{.Status}}' 2>&1 | head -20

echo ''
echo '=== 当前 listening 端口 ==='
sudo ss -tlnp 2>/dev/null | head -30 || ss -tlnp | head -30

echo ''
echo '=== docker compose project 列表 ==='
docker compose ls 2>&1 | head -10

echo ''
echo '=== /home/pluto 下已有什么 ==='
ls -la /home/pluto/ 2>&1 | head -10
