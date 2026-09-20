"""Local records with validated, atomic writes and recoverable snapshots."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import time
import uuid

FIELDS = ['分类','名称','登录方式/名称','登录/绑定邮箱','登录/绑定电话','密码提示','昵称','备注','其他']


def validate(rows, columns=9):
    if not isinstance(rows, list) or len(rows) > 20000:
        raise ValueError('记录数量不正确（最多 20000 行）')
    if any(not isinstance(r, list) or len(r) != columns or any(not isinstance(v, str) or len(v) > 32767 for v in r) for r in rows):
        raise ValueError(f'每条记录应包含 {columns} 个文本字段，每格最多 32767 字')
    return rows


def validate_document(data, columns=9):
    if not isinstance(data, dict) or type(data.get('revision')) is not int or data['revision'] < 0:
        raise ValueError('记录文件格式不正确')
    validate(data.get('rows'), columns)
    return data


def atomic_write(path, raw):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name('.' + path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with open(tmp, 'xb') as f:
            os.chmod(tmp, 0o600)
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


class Store:
    def __init__(self, path, fields=None):
        self.fields = fields or FIELDS
        self.path = Path(path)
        self.backups = self.path.parent / 'backups'

    def raw(self):
        return self.path.read_bytes() if self.path.exists() else b''

    def token(self):
        return hashlib.sha256(self.raw()).hexdigest()

    def read(self):
        raw = self.raw()
        if not raw and not self.path.exists():
            # A missing main file must not silently replace existing history.
            if self.backups.exists() and any(self.backups.glob('*.json')):
                raise ValueError('正式记录文件缺失，请从备份恢复')
            return {'revision': 0, 'rows': []}
        return validate_document(json.loads(raw), len(self.fields))

    def snapshot(self, data, reason):
        validate_document(data, len(self.fields))
        raw = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
        digest = hashlib.sha256(raw).hexdigest()[:16]
        # Same revision and content need only one durable copy.
        existing = list(self.backups.glob(f'*-{data["revision"]}-{digest}.json')) if self.backups.exists() else []
        for candidate in existing:
            if candidate.read_bytes() == raw:
                return candidate.name
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        name = f'{stamp}-{reason}-{data["revision"]}-{digest}.json'
        atomic_write(self.backups / name, raw)
        return name

    def list_backups(self):
        result = []
        for path in sorted(self.backups.glob('*.json'), reverse=True):
            try:
                data = validate_document(json.loads(path.read_bytes()), len(self.fields))
                result.append({'id': path.name, 'time': datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
                               'count': sum(any(r) for r in data['rows']), 'valid': True})
            except (ValueError, OSError):
                result.append({'id': path.name, 'valid': False})
        return result

    def get_backup(self, name):
        if not isinstance(name, str) or Path(name).name != name or not name.endswith('.json'):
            raise ValueError('备份名称不正确')
        return validate_document(json.loads((self.backups / name).read_bytes()), len(self.fields))

    def prune(self):
        # Keep 30 days; always retain the newest snapshot even after long inactivity.
        paths = sorted(self.backups.glob('*.json'), reverse=True)
        for path in paths[1:]:
            if path.stat().st_mtime < time.time() - 30 * 86400:
                path.unlink()

    def write(self, rows, revision):
        validate(rows, len(self.fields))
        old = self.read()
        if old['revision'] != revision:
            raise Conflict('另一个窗口已修改记录。请先下载当前内容备份，再刷新页面。')
        if self.path.exists():
            self.snapshot(old, 'before-save')
        data = {'revision': old['revision'] + 1, 'rows': rows}
        # If either backup fails, do not touch the main file.
        self.snapshot(data, 'saved')
        atomic_write(self.path, json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8'))
        try:
            self.prune()
        except OSError:
            pass  # Retaining extra backups is safer than reporting a failed save.
        return data

    def restore(self, rows, token):
        validate(rows, len(self.fields))
        if token != self.token():
            raise Conflict('预览期间记录已改变，请重新打开备份与恢复后再试。')
        raw = self.raw()
        try:
            old = self.read()
        except (ValueError, UnicodeError):
            old = None
        if raw or self.path.exists():
            if old is not None:
                self.snapshot(old, 'before-restore')
            else:
                # Preserve corrupt bytes as evidence; never delete the original silently.
                atomic_write(self.backups / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.damaged'), raw)
        # Millisecond revision stays within JavaScript's safe integer range.
        data = {'revision': max(int(time.time() * 1000), (old or {}).get('revision', 0) + 1), 'rows': rows}
        self.snapshot(data, 'restored')
        atomic_write(self.path, json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8'))
        return data


class Conflict(ValueError):
    pass

TABLES = {'general': '信息记录', 'work': '工作', 'important': '重要', 'personal': '个人', 'other': '其他', 'computer': '电脑操作'}
COMPUTER_FIELDS = ['产品', '名称', '操作方式', '快捷键', '备注', '其他']
def table_fields(key):
    return COMPUTER_FIELDS if key == 'computer' else FIELDS

def migrate_tables(datafile):
    """Publish all migrated tables together, keeping the legacy file intact."""
    datafile = Path(datafile)
    destination = datafile.parent / 'tables'
    if destination.exists():
        computer = destination / 'computer'
        if not computer.exists():
            staging = datafile.parent / ('.computer-' + uuid.uuid4().hex)
            Store(staging / 'records.json', COMPUTER_FIELDS).write([], 0)
            os.replace(staging, computer)
        return
    legacy = Store(datafile)
    old = legacy.read()
    if datafile.exists():
        legacy.snapshot(old, 'before-table-migration')
    staging = datafile.parent / ('.tables-' + uuid.uuid4().hex)
    groups = {key: [] for key in TABLES}
    labels = {label: key for key, label in TABLES.items() if key not in ('general', 'computer')}
    for row in old['rows']:
        groups[labels.get(row[0], 'general')].append(row)
    try:
        for key, rows in groups.items():
            store = Store(staging / key / 'records.json', table_fields(key))
            store.write(rows, 0)
        os.replace(staging, destination)
    finally:
        if staging.exists():
            import shutil
            shutil.rmtree(staging)
