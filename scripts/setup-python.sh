#!/usr/bin/env bash
# PlutoLab — 在 WSL Ubuntu 装 uv (Python 包管理器)
set -e

echo '[1/4] uv 状态...'
if command -v uv &> /dev/null; then
  uv --version
  echo 'uv 已装好, 跳过安装'
else
  echo 'uv 未装, 开始下载安装脚本...'

  echo '[2/4] 装 uv (官方 installer)...'
  curl -LsSf --max-time 60 https://astral.sh/uv/install.sh | sh

  echo '[3/4] 永久加入 PATH (~/.bashrc)...'
  if ! grep -q '.local/bin' "$HOME/.bashrc"; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
  fi
fi

echo ''
echo '[4/4] 验证 uv...'
export PATH="$HOME/.local/bin:$PATH"
uv --version

echo ''
echo '=== Python 版本检查 ==='
python3 --version
echo ''
echo '=== DONE ==='
