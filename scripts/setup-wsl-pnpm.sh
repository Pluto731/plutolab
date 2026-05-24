#!/usr/bin/env bash
# 在 WSL 装 pnpm + 在 WSL 里跑 pnpm install
set +e

echo '[1/5] Node.js 检查...'
if command -v node &> /dev/null; then
  node --version
else
  echo '装 Node.js (apt, 清华源应该已配)...'
  apt-get install -y nodejs npm 2>&1 | tail -3
fi

echo ''
echo '[2/5] 装 pnpm (npm 全局)...'
if command -v pnpm &> /dev/null; then
  pnpm --version
else
  npm install -g pnpm@latest --silent --registry=https://registry.npmmirror.com 2>&1 | tail -3
fi
pnpm --version

echo ''
echo '[3/5] 清掉 Windows 上的 node_modules (NTFS 上的)...'
cd /mnt/e/Learning/LLM/04-AI-Apps/plutolab
rm -rf node_modules apps/web/node_modules pnpm-lock.yaml 2>/dev/null
ls -la node_modules apps/web/node_modules 2>&1 | head -3 || echo 'cleared'

echo ''
echo '[4/5] WSL 里跑 pnpm install (走 npmmirror)...'
cd /mnt/e/Learning/LLM/04-AI-Apps/plutolab
time pnpm install 2>&1 | tail -15

echo ''
echo '[5/5] 验证 ...'
ls apps/web/node_modules/next/package.json 2>&1 | head -2
pnpm --filter @plutolab/web list --depth=0 2>&1 | tail -20

echo ''
echo '=== DONE ==='
