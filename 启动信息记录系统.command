#!/bin/zsh
cd "$(dirname "$0")"
DATA_DIR="$(dirname "$0")/data"
if [[ -f "$(dirname "$0")/data-location.txt" ]]; then
  IFS= read -r DATA_DIR < "$(dirname "$0")/data-location.txt"
  DATA_DIR="${DATA_DIR/#\~/$HOME}"
fi
if /usr/bin/curl -fsS http://127.0.0.1:8766/ > /dev/null 2>&1; then
  open http://127.0.0.1:8766
  exit 0
fi
/usr/bin/python3 server.py --data-dir "$DATA_DIR" &
SERVER_PID=$!
trap 'kill "$SERVER_PID" 2>/dev/null' EXIT INT TERM
for attempt in {1..40}; do
  if /usr/bin/curl -fsS http://127.0.0.1:8766/ > /dev/null 2>&1; then
    open http://127.0.0.1:8766
    break
  fi
  sleep 0.25
done
printf '使用期间请保留此窗口。关闭窗口会停止系统。\n'
wait "$SERVER_PID"
