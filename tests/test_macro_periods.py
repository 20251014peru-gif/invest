"""macro_periods.py 시험: 가짜 FRED 서버로 정상/묶음 실패/일부 실패/전체 시간초과 네 경우를 검사한다.
사용: python3 tests/test_macro_periods.py   (네트워크 불필요)"""
import http.server, json, os, shutil, subprocess, sys, tempfile, threading, time, datetime as dt, urllib.parse

SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
MODE = {'m': 'ok'}


def series_rows(sid, cosd):
    start = dt.date.fromisoformat(cosd)
    days = [start + dt.timedelta(days=k) for k in range((dt.date(2026, 9, 28) - start).days + 1)]
    days = [d for d in days if d.weekday() < 5]
    return [(d.isoformat(), 1.0 + (hash(sid) % 7) + 0.01 * i) for i, d in enumerate(days)]


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_GET(self):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        ids = q['id'][0].split(','); cosd = q.get('cosd', ['2020-01-01'])[0]
        m = MODE['m']
        if m == 'hang' or (m == 'batch_hang' and len(ids) > 1):
            time.sleep(3); return
        if m == 'partial' and 'SOFR' in ids and len(ids) == 1:
            self.send_response(500); self.end_headers(); return
        cols = [i for i in ids if not (m == 'partial' and i == 'SOFR')]
        lines = ['observation_date,' + ','.join(cols)]
        data = {i: dict(series_rows(i, cosd)) for i in cols}
        for d in sorted({d for i in cols for d in data[i]}):
            lines.append(d + ',' + ','.join(str(data[i].get(d, '.')) for i in cols))
        body = '\n'.join(lines).encode()
        self.send_response(200); self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)


def run(mode, tmp, port):
    MODE['m'] = mode
    env = dict(os.environ, FRED_BASE=f'http://127.0.0.1:{port}/fredgraph.csv', FRED_REQ_TIMEOUT='1', FRED_RETRIES='0', PERIODS_DEADLINE_SEC='60')
    r = subprocess.run([sys.executable, os.path.join(tmp, 'scripts/macro_periods.py')], env=env, capture_output=True, text=True)
    d = json.load(open(os.path.join(tmp, 'facts/macro_periods.json')))
    return r.returncode, d, r.stdout


def main():
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]
    tmp = tempfile.mkdtemp()
    for sub in ('scripts', 'data', 'facts'):
        shutil.copytree(os.path.join(SRC, sub), os.path.join(tmp, sub))
    seed = json.load(open(os.path.join(tmp, 'facts/macro_periods.json')))
    new4 = {'us30y', 'us_hy_oas', 'us_ccc_oas', 'sofr'}
    rc, d, _ = run('ok', tmp, port)
    assert rc == 0 and d['status'] == 'complete', d.get('errors')
    assert new4 <= set(d['items']) and all(d['items'][k]['last_observation'] == '2026-09-28' for k in new4)
    assert d['counts']['collected'] == d['counts']['defined'] and 'collected_at' in d
    rc, d, _ = run('batch_hang', tmp, port)  # 묶음 요청이 시간초과여도 개별 재시도로 모두 채운다
    assert rc == 0 and d['status'] == 'complete' and not [k for k in d['errors'] if not k.startswith('batch:')], d['errors']
    rc, d, _ = run('partial', tmp, port)  # SOFR 만 실패: 성공분은 저장되고 상태는 partial
    assert rc == 0 and d['status'] == 'partial' and 'sofr' in d['errors'], d
    assert d['counts']['collected'] == d['counts']['defined'] - 1 and 'us_hy_oas' in d['items']
    os.remove(os.path.join(tmp, 'facts/macro_periods.json'))
    json.dump(seed, open(os.path.join(tmp, 'facts/macro_periods.json'), 'w'))
    before = {k: v['collected_at'] for k, v in seed['items'].items()}
    rc, d, out = run('hang', tmp, port)  # 전부 시간초과: failed, 기존 자료 보존, 종료코드 1, 오류 주석
    assert rc == 1 and d['status'] == 'failed' and '::error::' in out, (rc, d['status'])
    assert {k: v['collected_at'] for k, v in d['items'].items() if k in before} == before
    print('OK: 4개 경우 통과 (ok / batch_hang / partial / hang)')


if __name__ == '__main__':
    main()
