#!/bin/zsh
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="$ROOT/../重要信息记录系统-Mac-$STAMP.zip"
cd "$ROOT"
/usr/bin/zip -qr "$OUT" . \
  -x './.git/*' './.DS_Store' './data/*' './__pycache__/*' './tests/__pycache__/*' './*.log'
echo "已生成：$OUT"
echo "解压到另一台 Mac 后，按 README.md 配置 data-location.txt，再双击启动信息记录系统.command。"
