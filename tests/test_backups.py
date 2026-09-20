import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from storage import Store, Conflict

A = [['工具', '原始记录', '邮箱', 'test@example.com', '00123', '', '', '多行\n备注', '']]
B = [['工具', '新记录', '', '', '+86123', '', '', '', '']]

class BackupsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name) / 'records.json')

    def test_delete_restore_and_undo_restore(self):
        self.store.write(A, 0)
        backup = self.store.list_backups()[0]['id']
        self.store.write([], 1)
        self.store.restore(self.store.get_backup(backup)['rows'], self.store.token())
        self.assertEqual(self.store.read()['rows'], A)
        self.assertTrue(any(self.store.get_backup(b['id'])['rows'] == [] for b in self.store.list_backups()))
        self.assertEqual(Store(self.store.path).read()['rows'], A)

    def test_backup_failure_keeps_main_unchanged(self):
        self.store.write(A, 0)
        original = self.store.raw()
        with patch.object(self.store, 'snapshot', side_effect=OSError('disk full')):
            with self.assertRaises(OSError): self.store.write(B, 1)
        self.assertEqual(self.store.raw(), original)

    def test_replace_failure_keeps_original_and_backup(self):
        self.store.write(A, 0)
        original = self.store.raw()
        import storage
        real_replace = storage.os.replace
        def fail_main(source, target):
            if target == self.store.path: raise OSError('write failure')
            return real_replace(source, target)
        with patch('storage.os.replace', side_effect=fail_main):
            with self.assertRaises(OSError): self.store.write(B, 1)
        self.assertEqual(self.store.raw(), original)
        self.assertTrue(any(self.store.get_backup(b['id'])['rows'] == B for b in self.store.list_backups()))

    def test_corrupt_file_can_recover_and_preserves_bytes(self):
        self.store.write(A, 0)
        self.store.path.write_bytes(b'{broken data')
        with self.assertRaises(ValueError): self.store.write(B, 1)
        self.store.restore(A, self.store.token())
        self.assertEqual(self.store.read()['rows'], A)
        self.assertEqual(next(self.store.backups.glob('*.damaged')).read_bytes(), b'{broken data')

    def test_missing_main_does_not_silently_reset(self):
        self.store.write(A, 0)
        self.store.path.unlink()
        with self.assertRaises(ValueError): self.store.read()
        self.store.restore(A, self.store.token())
        self.assertEqual(self.store.read()['rows'], A)

    def test_conflicts_and_invalid_import_do_not_mutate(self):
        self.store.write(A, 0)
        token = self.store.token()
        self.store.write(B, 1)
        original = self.store.raw()
        with self.assertRaises(Conflict): self.store.restore(A, token)
        with self.assertRaises(Conflict): self.store.write(A, 1)
        with self.assertRaises(ValueError): self.store.restore([['bad']], self.store.token())
        self.assertEqual(self.store.raw(), original)
        with self.assertRaises(ValueError): self.store.get_backup('../records.json')

    def test_retention_and_latest_kept(self):
        self.store.write(A, 0)
        old = next(self.store.backups.glob('*.json'))
        long_ago = time.time() - 31 * 86400
        os.utime(old, (long_ago, long_ago))
        self.store.prune()
        self.assertTrue(old.exists())
        self.store.write(B, 1)
        self.assertFalse(old.exists())
        self.assertGreaterEqual(len(self.store.list_backups()), 1)

    def test_damaged_snapshot_does_not_skip_backup(self):
        self.store.write(A, 0)
        next(self.store.backups.glob('*.json')).write_bytes(b'broken')
        self.store.write(B, 1)
        good = [b for b in self.store.list_backups() if b['valid']]
        self.assertTrue(any(self.store.get_backup(b['id'])['rows'] == A for b in good))

    def test_legacy_record_is_preserved(self):
        self.store.path.write_text(json.dumps({'revision': 42, 'rows': A}))
        self.store.write(B, 42)
        self.assertTrue(any(self.store.get_backup(b['id'])['rows'] == A for b in self.store.list_backups()))

if __name__ == '__main__': unittest.main()
