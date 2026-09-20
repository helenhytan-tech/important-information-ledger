from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED
from xml.sax.saxutils import escape
import json, os, threading, argparse, subprocess
from html import escape as html_escape

ROOT = Path(__file__).resolve().parent
from storage import Store, Conflict, FIELDS, validate, TABLES, migrate_tables, table_fields
from urllib.parse import urlsplit, parse_qs
LOCK = threading.Lock()

def workbook(rows, fields=FIELDS):
    def col(n):
        return chr(65+n)
    def xmltext(s):
        return escape(''.join(c for c in s if c in '\n\t\r' or ord(c) >= 32))
    content = []
    for i, row in enumerate([fields]+rows, 1):
        cells = ''.join(f'<c r="{col(j)}{i}" t="inlineStr"><is><t xml:space="preserve">{xmltext(v)}</t></is></c>' for j,v in enumerate(row))
        content.append(f'<row r="{i}">{cells}</row>')
    out = BytesIO()
    with ZipFile(out, 'w', ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
        z.writestr('_rels/.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr('xl/workbook.xml', '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="重要信息" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
        z.writestr('xl/worksheets/sheet1.xml', f'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><cols><col min="1" max="{len(fields)}" width="25" customWidth="1"/></cols><sheetData>'+''.join(content)+f'</sheetData><autoFilter ref="A1:{col(len(fields)-1)}{len(rows)+1}"/></worksheet>')
    return out.getvalue()

def workbook_bundle(tables):
    """Create one XLSX workbook with one worksheet per independent table."""
    def col(n): return chr(65+n)
    def xmltext(s): return escape(''.join(c for c in s if c in '\n\t\r' or ord(c) >= 32))
    sheets=[]
    for index,(key,title,fields,rows) in enumerate(tables,1):
        content=[]
        for row_no,row in enumerate([fields]+rows,1):
            cells=''.join(f'<c r="{col(j)}{row_no}" t="inlineStr"><is><t xml:space="preserve">{xmltext(v)}</t></is></c>' for j,v in enumerate(row))
            content.append(f'<row r="{row_no}">{cells}</row>')
        sheet='<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><cols><col min="1" max="%s" width="25" customWidth="1"/></cols><sheetData>%s</sheetData><autoFilter ref="A1:%s%d"/></worksheet>' % (len(fields),''.join(content),col(len(fields)-1),len(rows)+1)
        sheets.append((key,title,sheet))
    out=BytesIO()
    with ZipFile(out,'w',ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml','<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'+''.join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for i in range(1,len(sheets)+1))+'</Types>')
        z.writestr('_rels/.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        workbook_xml='<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'+''.join(f'<sheet name="{escape(title)}" sheetId="{i}" r:id="rId{i}"/>' for i,(_,title,_) in enumerate(sheets,1))+'</sheets></workbook>'
        rels='<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'+''.join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in range(1,len(sheets)+1))+'</Relationships>'
        z.writestr('xl/workbook.xml',workbook_xml);z.writestr('xl/_rels/workbook.xml.rels',rels)
        for i,(_,_,sheet) in enumerate(sheets,1): z.writestr(f'xl/worksheets/sheet{i}.xml',sheet)
    return out.getvalue()

class Handler(BaseHTTPRequestHandler):
    def reply(self, code, data, mime='application/json; charset=utf-8'):
        if not isinstance(data, bytes): data=json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', mime)
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Length',str(len(data)))
        self.end_headers()
        self.wfile.write(data)
    @property
    def store(self):
        key = self.headers.get('X-Ledger-Table')
        if key not in TABLES:
            raise ValueError('页面已升级为独立表格，请刷新页面后继续。')
        return Store(self.server.datafile.parent / 'tables' / key / 'records.json', table_fields(key))
    def read_data(self):
        return self.store.read()
    def all_tables(self):
        result=[]
        for key,title in TABLES.items():
            store=Store(self.server.datafile.parent / 'tables' / key / 'records.json', table_fields(key))
            result.append((key,title,table_fields(key),store.read()['rows']))
        return result
    def do_GET(self):
        route = urlsplit(self.path)
        if route.path in ('/api/records', '/api/backups', '/api/backup'):
            try:
                with LOCK:
                    if route.path == '/api/records':
                        data = self.read_data()
                    elif route.path == '/api/backups':
                        data = {'backups': self.store.list_backups(), 'token': self.store.token()}
                    else:
                        data = self.store.get_backup(parse_qs(route.query).get('id', [''])[0])
                self.reply(200, data)
            except Exception:
                self.reply(500, {'error': '无法读取记录，请打开“备份与恢复”选择可用备份。'})
            return
        allowed={'/':'index.html','/app.js':'app.js','/core.js':'core.js','/styles.css':'styles.css'}
        name=allowed.get(self.path)
        if not name: self.reply(404,{'error':'未找到'}); return
        mime={'html':'text/html; charset=utf-8','js':'text/javascript; charset=utf-8','css':'text/css; charset=utf-8'}[name.split('.')[-1]]
        self.reply(200,(ROOT/name).read_bytes(),mime)
    def do_HEAD(self):
        """Allow browser/network health checks to probe the local site."""
        route = urlsplit(self.path)
        if route.path not in ('/', '/app.js', '/core.js', '/styles.css'):
            self.send_error(404)
            return
        name = {'/':'index.html','/app.js':'app.js','/core.js':'core.js','/styles.css':'styles.css'}[route.path]
        mime = {'html':'text/html; charset=utf-8','js':'text/javascript; charset=utf-8','css':'text/css; charset=utf-8'}[name.split('.')[-1]]
        data = (ROOT/name).read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', mime)
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
    def do_POST(self):
        if self.headers.get('Origin') and self.headers['Origin'] != f'http://{self.headers.get("Host")}':
            self.reply(403,{'error':'不允许跨站请求'}); return
        if self.headers.get('Content-Type') != 'application/json':
            self.reply(415,{'error':'需要 JSON 数据'}); return
        try:
            size=int(self.headers.get('Content-Length','0'))
            if size>20_000_000: raise ValueError('内容过大，请分批保存')
            body=json.loads(self.rfile.read(size))
            if self.path == '/api/export-all':
                with LOCK:
                    tables=self.all_tables()
                fmt=body.get('format','xlsx')
                if fmt=='xlsx':
                    content=workbook_bundle(tables);mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                elif fmt=='html':
                    sections=[]
                    for _,title,fields,rows in tables:
                        table='<thead><tr>'+''.join('<th>'+html_escape(f)+'</th>' for f in fields)+'</tr></thead><tbody>'
                        table+=''.join('<tr>'+''.join('<td>'+html_escape(v)+'</td>' for v in row)+'</tr>' for row in rows)+'</tbody>'
                        sections.append('<section><h2>'+html_escape(title)+'</h2><p>共 '+str(len(rows))+' 条记录</p><div class="wrap"><table>'+table+'</table></div></section>')
                    content=('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>重要信息记录 · 全部表格</title><style>body{font:14px/1.6 system-ui;margin:32px;color:#302b38}section{break-after:page;margin-bottom:40px}table{border-collapse:collapse;min-width:1200px;width:100%}th,td{border:1px solid #e0d6e8;padding:12px;text-align:left;white-space:pre-wrap;overflow-wrap:anywhere;max-width:280px}th{background:#e2d4ed}tr:nth-child(even){background:#faf7fc}.wrap{overflow:auto}@media print{@page{size:A3 landscape}section{break-after:page}body{margin:0}table{min-width:0}thead{display:table-header-group}}</style><h1>重要信息记录 · 全部表格</h1>'+''.join(sections)+'</html>').encode('utf-8');mime='text/html; charset=utf-8'
                elif fmt in ('pdf','png'):
                    runtime=Path('/Users/helentan/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3')
                    payload={'tables':[{'title':title,'fields':fields,'rows':rows} for _,title,fields,rows in tables],'format':fmt}
                    result=subprocess.run([str(runtime),str(ROOT/'exports.py')],input=json.dumps(payload).encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=180,check=True)
                    content=result.stdout;mime='application/pdf' if fmt=='pdf' else 'application/zip'
                else: raise ValueError('不支持的导出格式')
                self.reply(200,content,mime);return
            fields=self.store.fields
            if self.path == '/api/restore':
                if body.get('table') and body['table'] != self.headers.get('X-Ledger-Table'):
                    raise ValueError('备份属于另一张表，请切换到对应表后恢复。')
                with LOCK:
                    if 'backupId' in body:
                        rows = self.store.get_backup(body['backupId'])['rows']
                    else:
                        if body.get('format') != 'information-ledger-v1' or body.get('fields') != fields:
                            raise ValueError('请选择本系统下载的 JSON 备份文件')
                        rows = validate(body.get('rows'), len(fields))
                    data = self.store.restore(rows, body.get('token'))
                self.reply(200, data)
                return
            rows=validate(body.get('rows'), len(fields))
            if self.path == '/api/export':
                fmt=body.get('format','xlsx')
                if fmt=='xlsx':
                    content=workbook(rows,fields);mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                elif fmt=='html':
                    table='<thead><tr>'+''.join('<th>'+html_escape(f)+'</th>' for f in fields)+'</tr></thead><tbody>'
                    table+=''.join('<tr>'+''.join('<td>'+html_escape(v)+'</td>' for v in row)+'</tr>' for row in rows)+'</tbody>'
                    content=('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>重要信息记录</title><style>body{font:14px/1.6 system-ui;margin:32px;color:#302b38}table{border-collapse:collapse;min-width:1200px;width:100%}th,td{border:1px solid #e0d6e8;padding:12px;text-align:left;white-space:pre-wrap;overflow-wrap:anywhere;max-width:280px}th{background:#e2d4ed}tr:nth-child(even){background:#faf7fc}.wrap{overflow:auto}@media print{@page{size:A3 landscape}body{margin:0}table{min-width:0}thead{display:table-header-group}}</style><h1>重要信息记录</h1><p>共 '+str(len(rows))+' 条记录</p><div class="wrap"><table>'+table+'</table></div></html>').encode('utf-8')
                    mime='text/html; charset=utf-8'
                elif fmt in ('pdf','png'):
                    runtime=Path('/Users/helentan/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3')
                    result=subprocess.run([str(runtime),str(ROOT/'exports.py')],input=json.dumps({'rows':rows,'format':fmt,'fields':fields,'title':TABLES[self.headers.get('X-Ledger-Table')]}).encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=180,check=True)
                    content=result.stdout
                    mime='application/pdf' if fmt=='pdf' else ('application/zip' if content.startswith(b'PK') else 'image/png')
                else:raise ValueError('不支持的导出格式')
                self.reply(200,content,mime); return
            if self.path != '/api/records': self.reply(404,{'error':'未找到'}); return
            with LOCK:
                data = self.store.write(rows, body.get('revision'))
            self.reply(200,{'revision':data['revision']})
        except Conflict as e: self.reply(409, {'error': str(e)})
        except (ValueError,TypeError,AttributeError) as e: self.reply(400,{'error':str(e)})
        except Exception: self.reply(500,{'error':'保存失败，内容仍留在页面中，请导出备份后重试。'})

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--port',type=int,default=8766); p.add_argument('--data',default=str(ROOT/'data'/'records.json')); p.add_argument('--data-dir',default=None,help='JSON 数据所在文件夹'); args=p.parse_args()
    if args.data_dir:
        args.data = str(Path(args.data_dir).expanduser() / 'records.json')
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    server.datafile=Path(args.data)
    migrate_tables(server.datafile)
    try:
        if server.datafile.exists():
            Store(server.datafile).snapshot(Store(server.datafile).read(), 'startup')
    except Exception:
        print('现有记录无法备份，请通过页面的备份与恢复检查。', flush=True)
    print(f'重要信息记录系统：http://127.0.0.1:{args.port}',flush=True)
    server.serve_forever()
