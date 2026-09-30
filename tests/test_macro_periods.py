"""macro_periods.py 시험 (가짜 FRED 서버, 네트워크 불필요, Windows·Ubuntu 공통).
사용: python3 tests/test_macro_periods.py
검사: 정상 / 묶음 실패 후 개별 성공 / 한 시리즈만 실패 / 전체 시간초과 / 기존 자료 보존 / 종료코드 /
      counts 일치 / 시리즈별 source_url / 부분 실패 시 새 자료와 옛 자료 공존."""
import http.server, json, os, shutil, subprocess, sys, tempfile, threading, time, datetime as dt, urllib.parse

for _s in (sys.stdout, sys.stderr):  # Windows 기본 코드페이지에서도 한글 출력이 예외가 되지 않게
    try:
        _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
SRC = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
MODE = {'m': 'ok'}
NEW4 = ('us30y', 'us_hy_oas', 'us_ccc_oas', 'sofr')


def series_rows(sid, cosd):
    start = dt.date.fromisoformat(cosd)
    days = [start + dt.timedelta(days=k) for k in range((dt.date(2026, 9, 28) - start).days + 1)]
    return [(d.isoformat(), 1.0 + (sum(map(ord, sid)) % 7) + 0.01 * i) for i, d in enumerate(d for d in days if d.weekday() < 5)]


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        ids = q['id'][0].split(','); cosd = q.get('cosd', ['2020-01-01'])[0]
        m = MODE['m']
        if m == 'hang' or (m == 'batch_fail' and len(ids) > 1):
            time.sleep(2); return
        if m == 'partial' and ids == ['SOFR']:
            self.send_response(500); self.end_headers(); return
        cols = [i for i in ids if not (m == 'partial' and i == 'SOFR')]
        data = {i: dict(series_rows(i, cosd)) for i in cols}
        lines = ['observation_date,' + ','.join(cols)]
        for d in sorted({d for i in cols for d in data[i]}):
            lines.append(d + ',' + ','.join(str(data[i].get(d, '.')) for i in cols))
        body = '\n'.join(lines).encode('utf-8')
        self.send_response(200); self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)


def jload(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def run(mode, tmp, port):
    MODE['m'] = mode
    env = dict(os.environ, FRED_BASE=f'http://127.0.0.1:{port}/fredgraph.csv', FRED_REQ_TIMEOUT='0.5', FRED_RETRIES='0', PERIODS_DEADLINE_SEC='120')
    r = subprocess.run([sys.executable, os.path.join(tmp, 'scripts', 'macro_periods.py')], env=env, capture_output=True, text=True, encoding='utf-8')
    return r.returncode, jload(os.path.join(tmp, 'facts', 'macro_periods.json')), r.stdout


def check_counts(d):
    c = d['counts']
    assert c['collected'] + c['series_failed'] == c['defined'], c
    assert c['series_failed'] == len(d['errors']), (c, d['errors'])
    assert c['retained_items'] == len(d['items']), c
    assert set(c) == {'defined', 'collected', 'series_failed', 'batch_fallbacks', 'retained_items'}, c


def check_urls(d, single):
    for sid, it in d['items'].items():
        ids = it['source_url'].split('id=')[1].split('&')[0].split(',')
        assert it['symbol'] in ids, (sid, it['source_url'])
        if single:
            assert ids == [it['symbol']], (sid, it['source_url'])


def main():
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]
    tmp = tempfile.mkdtemp()
    try:
        for sub in ('scripts', 'data', 'facts'):
            shutil.copytree(os.path.join(SRC, sub), os.path.join(tmp, sub))
        target = os.path.join(tmp, 'facts', 'macro_periods.json')
        seed = jload(target)

        rc, d, _ = run('ok', tmp, port)  # 1 정상
        assert rc == 0 and d['status'] == 'complete' and d['errors'] == {} and d['batch_errors'] == {}, d.get('errors')
        assert d['counts']['batch_fallbacks'] == 0
        assert all(d['items'][k]['last_observation'] == '2026-09-28' for k in NEW4)
        check_counts(d); check_urls(d, single=False)

        rc, d, _ = run('batch_fail', tmp, port)  # 2 묶음 실패 후 개별 성공: complete, 실패 0, 묶음 실패는 fallback/경고로만
        assert rc == 0 and d['status'] == 'complete' and d['counts']['series_failed'] == 0 and d['errors'] == {}, d['errors']
        assert d['counts']['batch_fallbacks'] >= 1 and d['batch_errors'], d['counts']
        check_counts(d); check_urls(d, single=True)  # 10 시리즈별 source_url 정확

        prev = jload(target)['items']
        rc, d, _ = run('partial', tmp, port)  # 3·8 한 시리즈만 실패: 성공분은 새 자료, 실패분은 기존 자료 보존
        assert rc == 0 and d['status'] == 'partial' and list(d['errors']) == ['sofr'], d['errors']
        assert d['counts']['series_failed'] == 1
        check_counts(d); check_urls(d, single=False)
        assert d['items']['sofr']['collected_at'] == prev['sofr']['collected_at']  # 옛 자료 그대로
        assert d['items']['us_hy_oas']['collected_at'] > prev['us_hy_oas']['collected_at']  # 새 자료

        before = json.loads(json.dumps(d['items']))
        rc, d, out = run('hang', tmp, port)  # 4·5·6 전체 시간초과: failed, 종료코드 1, 기존 정상 자료 그대로
        assert rc == 1 and d['status'] == 'failed' and '::error::' in out, (rc, d['status'])
        assert d['items'] == before
        assert d['counts']['collected'] == 0 and d['counts']['series_failed'] == d['counts']['defined']
        check_counts(d)

        # 옛 시드(신규 4개 없음)에서 전체 실패해도 종료코드 1이고 시드 항목은 그대로
        with open(target, 'w', encoding='utf-8') as f:
            json.dump(seed, f, ensure_ascii=False, indent=2)
        rc, d, _ = run('hang', tmp, port)
        assert rc == 1 and d['items'] == seed['items'] and not (set(NEW4) & set(d['items']))
        print('OK: macro_periods 시험 통과 (정상 / 묶음 실패 후 개별 / 한 시리즈 실패 / 전체 시간초과 / 보존 / 종료코드 / counts / source_url)')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    main()
