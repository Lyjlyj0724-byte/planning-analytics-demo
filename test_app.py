import csv
import io
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from contextlib import closing
from pathlib import Path
from http.server import ThreadingHTTPServer
from app import Store, analyze, handler, synthetic_rows, validate


class DemoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name)/'demo.sqlite')

    def tearDown(self):
        self.temp.cleanup()

    def test_weighted_completion(self):
        rows = synthetic_rows()[:2]
        rows[0].update(total=1, completed=1)
        rows[1].update(total=9, completed=0)
        metric = analyze(rows)['metrics'][-1]
        self.assertEqual(metric['value'], '10')
        self.assertEqual(metric['numerator'], 1)
        self.assertEqual(metric['denominator'], 10)

    def test_zero_denominator(self):
        self.assertIsNone(analyze([])['metrics'][-1]['value'])

    def test_invalid_counts(self):
        for value in (None, True, -1, 'NaN', 1.2):
            rows = synthetic_rows()
            rows[0]['material'] = value
            with self.assertRaises(ValueError):
                validate(rows)

    def test_success_and_filter_evidence(self):
        state = self.store.refresh('success')
        result = self.store.view(state['latest']['batch_id'], {'region': '演示东区'})
        self.assertEqual(result['analysis']['records'], 4)
        self.assertEqual(result['analysis']['metrics'][0]['value'], sum(r['material'] for r in result['rows']))
        self.assertEqual([e['stage'] for e in state['events']], ['collecting','validating','ingesting','succeeded'])

    def test_failures_do_not_fall_back(self):
        original = self.store.refresh('success')['latest']['batch_id']
        for scenario in ('auth_failure', 'validation_failure', 'storage_failure'):
            state = self.store.refresh(scenario)
            self.assertEqual(state['latest']['state'], 'failed')
            self.assertIsNone(state['latest']['batch_id'])
            self.assertEqual(state['last_success']['batch_id'], original)
        with closing(self.store.connect()) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM batches').fetchone()[0], 1)

    def test_empty_is_success_not_old_snapshot(self):
        self.store.refresh('success')
        state = self.store.refresh('empty')
        self.assertEqual(state['latest']['state'], 'succeeded')
        self.assertEqual(state['last_success']['rows'], 0)
        self.assertEqual(self.store.view(state['latest']['batch_id'], {})['rows'], [])

    def test_unknown_batch_and_filter_rejected(self):
        for batch, filters in (('', {}), ('missing', {}), ('x', {'sql': 'select 1'})):
            with self.assertRaises(ValueError):
                self.store.view(batch, filters)

    def test_no_snapshot_accumulation(self):
        first = self.store.refresh('success')['latest']['batch_id']
        second = self.store.refresh('success')['latest']['batch_id']
        self.assertNotEqual(first, second)
        self.assertEqual(self.store.view(second, {})['analysis']['records'], 12)

    def test_filtered_export_and_audit(self):
        batch = self.store.refresh('success')['latest']['batch_id']
        data = self.store.export(batch, {'region': '演示东区'}).decode('utf-8-sig')
        self.assertEqual(len(list(csv.reader(io.StringIO(data)))), 6)
        self.assertIn('SYNTHETIC ONLY', data)
        with closing(self.store.connect()) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM exports').fetchone()[0], 1)

    def test_persistence_and_interruption(self):
        self.store.refresh('success')
        with closing(self.store.connect()) as db, db:
            db.execute("INSERT INTO runs(id,state) VALUES('interrupted-test','collecting')")
        restored = Store(self.store.path).status()
        self.assertEqual(restored['latest']['state'], 'interrupted')
        self.assertEqual(restored['last_success']['rows'], 12)

    def test_concurrent_attempt_rejected(self):
        with self.store.lock:
            with self.assertRaises(ValueError):
                self.store.refresh('success')

    def test_unknown_scenario_rejected(self):
        with self.assertRaises(ValueError):
            self.store.refresh('live')
        self.assertIsNone(self.store.status()['latest'])

    def test_http_boundaries(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), handler(self.store, 'synthetic-test-token'))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        def request(path, body=None, headers=None):
            req = urllib.request.Request(base+path, data=json.dumps(body).encode() if body is not None else None,
                                         headers=headers or {})
            try:
                with opener.open(req, timeout=3) as response:
                    return response.status, response.read()
            except urllib.error.HTTPError as exc:
                return exc.code, exc.read()
        try:
            self.assertEqual(request('/')[0], 200)
            self.assertEqual(request('/api/status', headers={'Host': 'attacker.example'})[0], 403)
            self.assertEqual(request('/api/refresh', {'scenario': 'success'})[0], 403)
            self.assertEqual(request('/api/refresh', {'scenario': 'success'}, {'Origin': 'http://attacker.example', 'X-CSRF-Token': 'synthetic-test-token'})[0], 403)
            self.assertEqual(request('/../app.py')[0], 404)
            self.assertEqual(request('/.demo-data/demo.sqlite')[0], 404)
            self.assertEqual(request('/api/view?batch=missing')[0], 400)
            self.assertEqual(request('/api/view?batch=a&batch=b')[0], 400)
            good = {'Origin': base, 'X-CSRF-Token': 'synthetic-test-token'}
            self.assertEqual(request('/api/refresh', {'scenario': 'success', 'url': 'remote'}, good)[0], 400)
            self.assertIsNone(self.store.status()['latest'])
            code, body = request('/api/refresh', {'scenario': 'success'}, good)
            self.assertEqual(code, 200)
            self.assertEqual(json.loads(body)['latest']['rows'], 12)
        finally:
            server.shutdown()
            thread.join(timeout=3)
            server.server_close()


if __name__ == '__main__':
    unittest.main()
