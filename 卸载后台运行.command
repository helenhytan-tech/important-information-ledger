#!/bin/zsh
set -e
LABEL="com.helentan.important-information-ledger"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
/bin/launchctl bootout "gui/$(/usr/bin/id -u)" "$PLIST" 2>/dev/null || true
/bin/rm -f "$PLIST"
echo "已停止后台运行；数据文件不会被删除。"
