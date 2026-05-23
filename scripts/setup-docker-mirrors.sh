#!/usr/bin/env bash
# PlutoLab — 给 WSL 里的 docker daemon 配国内镜像源, 重启, 拉镜像
set +e

echo '[1/4] 写入 /etc/docker/daemon.json...'
mkdir -p /etc/docker
cat > /etc/docker/daemon.json <<'EOF'
{
  "registry-mirrors": [
    "https://docker.1ms.run",
    "https://docker.m.daocloud.io",
    "https://hub-mirror.c.163.com",
    "https://docker.mirrors.ustc.edu.cn"
  ]
}
EOF
cat /etc/docker/daemon.json

echo ''
echo '[2/4] 重启 docker daemon...'
service docker restart
sleep 3
service docker status 2>&1 | head -3

echo ''
echo '[3/4] 确认镜像源已加载...'
docker info --format 'Registry Mirrors: {{json .RegistryConfig.Mirrors}}'

echo ''
echo '[4/4] 拉 PlutoLab 三个镜像 (postgres+pgvector / redis / adminer)...'
cd /mnt/e/Learning/LLM/04-AI-Apps/plutolab
docker compose pull 2>&1 | tail -20

echo ''
echo '=== DONE ==='
