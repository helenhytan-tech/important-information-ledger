import json
from pathlib import Path
import tempfile
import unittest
from storage import Store, migrate_tables, TABLES

class TablesTest(unittest.TestCase):
    def test_migration_preserves_every_row_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'records.json'
            rows=[[v,'记录','','','','','','',''] for v in ['工作','重要','个人','其他','自定义','']]
            Store(path).write(rows,0)
            original=path.read_bytes()
            migrate_tables(path)
            groups={k:Store(Path(d)/'tables'/k/'records.json').read()['rows'] for k in TABLES}
            self.assertEqual(sum(map(len,groups.values())),len(rows))
            self.assertEqual(len(groups['general']),2)
            work=Store(Path(d)/'tables/work/records.json')
            work.write([['软件','新工作内容','','','','','','','']],1)
            migrate_tables(path)
            self.assertEqual(work.read()['rows'][0][0],'软件')
            self.assertEqual(path.read_bytes(),original)
            self.assertEqual(Store(Path(d)/'tables/personal/records.json').read()['rows'],groups['personal'])

    def test_backup_restore_isolated(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'records.json';migrate_tables(path)
            work=Store(Path(d)/'tables/work/records.json');personal=Store(Path(d)/'tables/personal/records.json')
            personal.write([['邮箱','个人内容','','','','','','','']],1)
            original=personal.raw()
            work.write([['邮箱','工作内容','','','','','','','']],1)
            snapshot=work.list_backups()[0]['id']
            work.write([],2)
            work.restore(work.get_backup(snapshot)['rows'],work.token())
            self.assertEqual(personal.raw(),original)
            self.assertEqual(work.read()['rows'][0][1],'工作内容')
