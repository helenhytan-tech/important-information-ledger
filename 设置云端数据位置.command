#!/bin/zsh
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
echo "请输入云盘中用于存放 JSON 数据的文件夹路径。"
echo "例如：/Users/你的用户名/Library/Mobile Documents/com~apple~CloudDocs/重要信息记录系统数据"
read "DATA_DIR?路径： "
if [[ -z "$DATA_DIR" ]]; then
  echo "未设置路径。"
  exit 1
fi
DATA_DIR="${DATA_DIR/#\~/$HOME}"
mkdir -p "$DATA_DIR"
print -r -- "$DATA_DIR" > "$ROOT/data-location.txt"
echo "已设置。以后双击启动信息记录系统.command，数据会保存在：$DATA_DIR"
