"""Standalone synthetic planning analytics. Python standard library only.

No private imports, corporate endpoints, credentials, or outbound network calls.
"""
import argparse
import csv
import io
import json
import secrets
import sqlite3
import threading
from contextlib import closing
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_EVEN
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

ROOT = Path(__file__).resolve().parent
SOURCE_AT = '2026-01-15T09:00:00+00:00'
VERSION = 'synthetic-material-v1'
STAGES = {'material': '面料未完成个数', 'blank': '毛坯未完成个数', 'dye': '投染未完成个数'}
SCENARIOS = {'success', 'empty', 'auth_failure', 'validation_failure', 'storage_failure'}
ERRORS = {'auth_failure': '模拟登录失效；本次失败，不回退旧数据。',
          'validation_failure': '模拟数据校验失败；本次没有发布批次。',
          'storage_failure': '模拟入库失败；本次没有发布批次。'}


def now():
    return datetime.now(timezone.utc).isoformat()


def synthetic_rows():
    """Entirely invented labels and counts; no source snapshots are loaded."""
    return [dict(record_id=f'DEMO-{i+1:03}', region=['演示东区', '演示西区', '演示南区'][i % 3],
                 department=['演示甲组', '演示乙组'][i % 2], total=10+i,
                 completed=i % 5, material=8+i, blank=3+i % 4, dye=2+i % 3)
            for i in range(12)]


def validate(rows):
    for row in rows:
        for key in ('total', 'completed', *STAGES):
            value = row.get(key)
            if type(value) is not int or value < 0:
                raise ValueError('Invalid synthetic count')
        if row['completed'] > row['total']:
            raise ValueError('Completed exceeds total')


def analyze(rows):
    validate(rows)
    total = sum(r['total'] for r in rows)
    complete = sum(r['completed'] for r in rows)
    rate = (format((Decimal(complete)*100/total).quantize(Decimal('.0001'), rounding=ROUND_HALF_EVEN), 'f')
            .rstrip('0').rstrip('.') if total else None)
    metrics = [dict(id=k, label=v, value=sum(r[k] for r in rows), unit='原报表个数', formula=f'sum({k})')
               for k, v in STAGES.items()]
    metrics.append(dict(id='completion', label='合约个数加权完成率', value=rate, unit='%',
                        formula='100 × sum(completed) / sum(total)', numerator=complete, denominator=total))
    groups = []
    for region in sorted({r['region'] for r in rows}):
        subset = [r for r in rows if r['region'] == region]
        groups.append(dict(region=region, records=len(subset), amount=sum(r['material'] for r in subset)))
    return dict(records=len(rows), metrics=metrics, groups=groups, version=VERSION,
                approval='演示口径，待业务负责人审核；不是正式制度',
                caveats=['阶段可能重叠，不能相加为总缺口。', '源行不是去重合约；不跨快照累加。',
                         '完成率只适用于当前筛选；不代表部门整体。', '没有交期或责任规则，不判定逾期、原因或责任。'])


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        with closing(self.connect()) as db, db:
            db.executescript('''CREATE TABLE IF NOT EXISTS runs(
                id TEXT PRIMARY KEY, requested_at TEXT, finished_at TEXT, scenario TEXT,
                state TEXT, message TEXT, batch_id TEXT, source_at TEXT, rows INTEGER);
                CREATE TABLE IF NOT EXISTS batches(id TEXT PRIMARY KEY, payload TEXT);
                CREATE TABLE IF NOT EXISTS events(run_id TEXT, stage TEXT, at TEXT);
                CREATE TABLE IF NOT EXISTS exports(batch_id TEXT, filters TEXT, at TEXT);''')
            db.execute("UPDATE runs SET state='interrupted',message='演示进程中断；结果未确认，不自动重试。',finished_at=? WHERE state NOT IN ('succeeded','failed','interrupted')", (now(),))

    def connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        return db

    def refresh(self, scenario):
        if scenario not in SCENARIOS:
            raise ValueError('Unknown scenario')
        if not self.lock.acquire(blocking=False):
            raise ValueError('演示刷新正在进行中')
        rid = str(uuid4())
        try:
            with closing(self.connect()) as db, db:
                db.execute('INSERT INTO runs(id,requested_at,scenario,state,message) VALUES(?,?,?,?,?)',
                           (rid, now(), scenario, 'collecting', '生成合成数据'))
                db.execute('INSERT INTO events VALUES(?,?,?)', (rid, 'collecting', now()))
            rows = [] if scenario == 'empty' else synthetic_rows()
            try:
                if scenario == 'auth_failure':
                    raise ValueError(ERRORS[scenario])
                with closing(self.connect()) as db, db:
                    db.execute("UPDATE runs SET state='validating' WHERE id=?", (rid,))
                    db.execute('INSERT INTO events VALUES(?,?,?)', (rid, 'validating', now()))
                if scenario == 'validation_failure':
                    rows[0]['completed'] = rows[0]['total'] + 1
                validate(rows)
                with closing(self.connect()) as db, db:
                    db.execute("UPDATE runs SET state='ingesting' WHERE id=?", (rid,))
                    db.execute('INSERT INTO events VALUES(?,?,?)', (rid, 'ingesting', now()))
                bid = str(uuid4())
                # Snapshot and success receipt are committed atomically. Fault injection rolls back both.
                with closing(self.connect()) as db, db:
                    db.execute('INSERT INTO batches VALUES(?,?)', (bid, json.dumps(rows, ensure_ascii=False)))
                    if scenario == 'storage_failure':
                        raise ValueError(ERRORS[scenario])
                    db.execute("UPDATE runs SET state='succeeded',message=?,batch_id=?,source_at=?,rows=?,finished_at=? WHERE id=?",
                               ('合成刷新成功；不是实时业务数据。', bid, SOURCE_AT, len(rows), now(), rid))
                    db.execute('INSERT INTO events VALUES(?,?,?)', (rid, 'succeeded', now()))
            except ValueError:
                with closing(self.connect()) as db, db:
                    db.execute("UPDATE runs SET state='failed',message=?,finished_at=? WHERE id=?",
                               (ERRORS.get(scenario, '校验失败；未发布批次。'), now(), rid))
                    db.execute('INSERT INTO events VALUES(?,?,?)', (rid, 'failed', now()))
            return self.status()
        finally:
            self.lock.release()

    def status(self):
        with closing(self.connect()) as db:
            recent = [dict(r) for r in db.execute('SELECT * FROM runs ORDER BY rowid DESC LIMIT 20')]
            last = db.execute("SELECT * FROM runs WHERE state='succeeded' ORDER BY rowid DESC LIMIT 1").fetchone()
            events = [dict(r) for r in db.execute('SELECT stage,at FROM events WHERE run_id=? ORDER BY rowid',
                                                (recent[0]['id'],))] if recent else []
        return dict(latest=recent[0] if recent else None, last_success=dict(last) if last else None,
                    recent=recent, events=events, synthetic=True, scheduled=False)

    def view(self, batch, filters):
        if set(filters) - {'region', 'department'} or any(len(v) > 100 for v in filters.values()):
            raise ValueError('Unsupported filters')
        with closing(self.connect()) as db:
            found = db.execute('SELECT payload FROM batches WHERE id=?', (batch,)).fetchone()
        if found is None:
            raise ValueError('批次不存在；不回退其他批次')
        all_rows = json.loads(found['payload'])
        rows = [r for r in all_rows if all(r[k] == v for k, v in filters.items())]
        return dict(batch_id=batch, source_at=SOURCE_AT, filters=filters, rows=rows,
                    original_records=len(all_rows), analysis=analyze(rows),
                    options={k: sorted({r[k] for r in all_rows}) for k in ('region', 'department')})

    def export(self, batch, filters):
        result = self.view(batch, filters)
        output = io.StringIO()
        writer = csv.writer(output)
        columns = ['record_id', 'region', 'department', 'total', 'completed', *STAGES]
        writer.writerow(['SYNTHETIC ONLY', batch, SOURCE_AT, json.dumps(filters, ensure_ascii=False)])
        writer.writerow(columns)
        for row in result['rows']:
            writer.writerow([("'"+str(row[k])) if str(row[k]).startswith(('=', '+', '-', '@')) else row[k] for k in columns])
        with closing(self.connect()) as db, db:
            db.execute('INSERT INTO exports VALUES(?,?,?)', (batch, json.dumps(filters), now()))
        return output.getvalue().encode('utf-8-sig')


def handler(store, token):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send(self, value, code=200, kind='application/json; charset=utf-8'):
            raw = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False).encode()
            self.send_response(code)
            for key, val in {'Content-Type': kind, 'Content-Length': str(len(raw)), 'Cache-Control': 'no-store',
                             'X-Content-Type-Options': 'nosniff',
                             'Content-Security-Policy': "default-src 'self'; frame-ancestors 'none'; base-uri 'none'"}.items():
                self.send_header(key, val)
            self.end_headers()
            self.wfile.write(raw)

        def local(self):
            expected = '127.0.0.1:'+str(self.server.server_port)
            if self.headers.get('Host') != expected:
                raise PermissionError('Loopback Host required')
            return 'http://'+expected

        def do_GET(self):
            try:
                self.local()
                path = urlsplit(self.path)
                static = {'/': ('index.html', 'text/html; charset=utf-8'), '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                          '/style.css': ('style.css', 'text/css; charset=utf-8')}
                if path.path in static:
                    filename, kind = static[path.path]
                    return self.send((ROOT/filename).read_bytes(), kind=kind)
                if path.path == '/api/status':
                    return self.send({**store.status(), 'csrf': token})
                if path.path in ('/api/view', '/api/export'):
                    query = parse_qs(path.query, keep_blank_values=True)
                    if set(query) - {'batch', 'region', 'department'} or any(len(v) != 1 for v in query.values()):
                        raise ValueError('Unsupported query')
                    batch = query.pop('batch', [''])[0]
                    filters = {k: v[0] for k, v in query.items()}
                    if path.path == '/api/export':
                        return self.send(store.export(batch, filters), kind='text/csv; charset=utf-8')
                    return self.send(store.view(batch, filters))
                return self.send({'error': 'Not found'}, 404)
            except PermissionError:
                self.send({'error': 'Access denied'}, 403)
            except ValueError as exc:
                self.send({'error': str(exc)}, 400)

        def do_POST(self):
            try:
                origin = self.local()
                if self.headers.get('Origin') != origin or not secrets.compare_digest(self.headers.get('X-CSRF-Token', '')[:200], token):
                    raise PermissionError('CSRF validation required')
                if self.path != '/api/refresh':
                    return self.send({'error': 'Not found'}, 404)
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 1024:
                    raise ValueError('Invalid body size')
                body = json.loads(self.rfile.read(size))
                if not isinstance(body, dict) or set(body) != {'scenario'} or not isinstance(body['scenario'], str):
                    raise ValueError('Unsupported body')
                return self.send(store.refresh(body['scenario']))
            except PermissionError:
                self.send({'error': 'Access denied'}, 403)
            except (ValueError, TypeError) as exc:
                self.send({'error': str(exc)}, 400)
    return Handler


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8780)
    args = parser.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), handler(Store(ROOT/'.demo-data/demo.sqlite'), secrets.token_urlsafe(32)))
    print(f'SYNTHETIC ONLY: http://127.0.0.1:{args.port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
