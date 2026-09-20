#!/bin/zsh
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$HOME/Library/Application Support/重要信息记录系统"
LABEL="com.helentan.important-information-ledger"
PLIST_DIR="$HOME/Library/LaunchAgents"
PLIST="$PLIST_DIR/$LABEL.plist"
DATA_DIR="$ROOT/data"
if [[ -f "$ROOT/data-location.txt" ]]; then
  IFS= read -r DATA_DIR < "$ROOT/data-location.txt"
  DATA_DIR="${DATA_DIR/#\~/$HOME}"
else
  DATA_DIR="$APP_DIR/data"
fi
mkdir -p "$APP_DIR"
if [[ "$DATA_DIR" == "$APP_DIR/data" && ! -e "$DATA_DIR/records.json" && -e "$ROOT/data/records.json" ]]; then
  /bin/mkdir -p "$DATA_DIR/tables"
  if [[ -f "$ROOT/data/records.json" ]]; then /bin/cp -f "$ROOT/data/records.json" "$DATA_DIR/records.json"; fi
  for SOURCE_RECORD in "$ROOT"/data/tables/*/records.json; do
    [[ -f "$SOURCE_RECORD" ]] || continue
    TABLE_NAME="${SOURCE_RECORD:h:t}"
    /bin/mkdir -p "$DATA_DIR/tables/$TABLE_NAME"
    /bin/cp -f "$SOURCE_RECORD" "$DATA_DIR/tables/$TABLE_NAME/records.json"
  done
fi
mkdir -p "$PLIST_DIR" "$DATA_DIR"
for FILE in server.py storage.py exports.py index.html app.js core.js styles.css; do
  /bin/cp -f "$ROOT/$FILE" "$APP_DIR/$FILE"
done
/usr/bin/python3 - "$APP_DIR" "$DATA_DIR" "$PLIST" "$LABEL" <<'PY'
import plistlib, sys
root, data_dir, plist_path, label = sys.argv[1:]
plist = {
    'Label': label,
    'ProgramArguments': ['/usr/bin/python3', root + '/server.py', '--data-dir', data_dir],
    'WorkingDirectory': root,
    'RunAtLoad': True,
    'KeepAlive': True,
    'ThrottleInterval': 5,
    'StandardOutPath': '/tmp/important-information-ledger.log',
    'StandardErrorPath': '/tmp/important-information-ledger-error.log',
}
with open(plist_path, 'wb') as stream:
    plistlib.dump(plist, stream, sort_keys=False)
PY
/bin/launchctl bootout "gui/$(/usr/bin/id -u)" "$PLIST" 2>/dev/null || true
/bin/launchctl bootstrap "gui/$(/usr/bin/id -u)" "$PLIST"
/bin/launchctl kickstart -k "gui/$(/usr/bin/id -u)/$LABEL"
/usr/bin/open "http://127.0.0.1:8766/"
echo "已安装后台运行。以后登录 Mac 后会自动启动，服务异常时会自动重启。"
echo "现在可以在浏览器中把 http://127.0.0.1:8766/ 添加到收藏夹。"
