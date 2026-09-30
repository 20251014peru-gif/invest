"""Read-only source collection for period bars. Never changes macro.json or records.
No date interpolation, zero filling, or collection-snapshot relabelling.
"""
import csv, io, json, os, pathlib, sys, time, datetime as dt, urllib.request, math
ROOT = pathlib.Path(__file__).resolve().parents[1]

def transform(rows, kind):
    by_period = {d[:7]:v for d,v in rows}
    result=[]
    for d,v in rows:
        if not math.isfinite(v): continue
        if kind in ('yoy','diff','mom_pct'):
            year,month=map(int,d[:7].split('-'))
            if kind=='yoy': prior=f'{year-1:04}-{month:02}'
            else: prior=f'{year-1:04}-12' if month==1 else f'{year:04}-{month-1:02}'
            old=by_period.get(prior)
            if old is None or (kind!='diff' and old==0): continue
            v=v-old if kind=='diff' else (v/old-1)*100
        result.append({'period':d,'value':round(v,4)})
    return result[-120:]

# ---- 수집 정책 ----
# 시리즈마다 전체 이력을 따로 받던 방식(요청 18건, 재시도 없음, 한 번의 시간초과가 곧 실패)을 바꿨다.
# 1) 기간(cosd)을 제한해 내려받는 양을 줄인다.  2) 같은 기간 그룹은 한 요청에 묶는다(FRED graph CSV의 id=A,B,C).
# 3) 묶음 요청이 실패하면 시리즈별로 재시도한다.  4) 시리즈마다 결과와 오류를 분리하고, 성공분은 즉시 파일에 저장한다.
# 5) 전체 제한시간(DEADLINE_SEC)에 걸리기 전에 중단하고, 남은 시리즈는 오류로 기록한다.
FRED_BASE = os.environ.get('FRED_BASE', 'https://fred.stlouisfed.org/graph/fredgraph.csv')
REQ_TIMEOUT = float(os.environ.get('FRED_REQ_TIMEOUT', '40'))
RETRIES = int(os.environ.get('FRED_RETRIES', '2'))
DEADLINE_SEC = float(os.environ.get('PERIODS_DEADLINE_SEC', '360'))
FORMULA = {'yoy': '(당월 지수 / 전년 같은 달 지수 − 1) × 100', 'diff': '당월 값 − 전월 값', 'mom_pct': '(당월 값 / 전월 값 − 1) × 100'}


def fetch_csv(ids, cosd):
    url = f"{FRED_BASE}?id={','.join(ids)}&cosd={cosd}"
    last = None
    for attempt in range(RETRIES + 1):
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (invest period charts)'})
            return url, urllib.request.urlopen(request, timeout=REQ_TIMEOUT).read().decode('utf-8')
        except Exception as error:  # 시간초과·연결 오류·HTTP 오류 모두 재시도 대상
            last = error
            if attempt < RETRIES:
                time.sleep(2 * (attempt + 1) ** 2)
    raise last


def parse_columns(raw, ids):
    """CSV 에서 시리즈별 (날짜, 값) 목록을 만든다. 없는 열은 결과에 넣지 않는다."""
    reader = csv.DictReader(io.StringIO(raw))
    out = {i: [] for i in ids if i in (reader.fieldnames or [])}
    for r in reader:
        d = r.get('observation_date') or r.get('DATE')
        if not d:
            continue
        dt.date.fromisoformat(d)
        for i in out:
            v = (r.get(i) or '').strip()
            if v and v != '.':
                value = float(v)
                if math.isfinite(value):
                    out[i].append((d, value))
    for i in out:
        out[i].sort()
    return out


def build_item(ind, rows, url):
    kind = ind.get('derive')
    points = transform(rows, kind)
    if not points:
        raise ValueError('No dated observations')
    return {'source_url': url, 'symbol': ind['symbol'], 'cycle': ind.get('cycle'), 'unit': ind.get('unit'),
            'formula': FORMULA.get(kind, '공식 원자료 값'), 'collected_at': dt.datetime.now(dt.timezone.utc).isoformat(),
            'last_observation': points[-1]['period'], 'points': points}


def collect(ind):
    """단일 시리즈 수집(다른 스크립트·시험용). 전체 이력 대신 기간을 제한한다."""
    cosd = window_start(ind)
    url, raw = fetch_csv([ind['symbol']], cosd)
    cols = parse_columns(raw, [ind['symbol']])
    if ind['symbol'] not in cols:
        raise ValueError('series column missing')
    return build_item(ind, cols[ind['symbol']], url)


def window_start(ind):
    days = 500 if ind.get('cycle') in ('D', 'W') else 4400  # 월간 파생(전년비)은 120개 결과에 약 11년 필요
    return (dt.date.today() - dt.timedelta(days=days)).isoformat()


def atomic_write(path, obj):
    tmp = path.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    os.replace(tmp, path)


def load_defs():
    defs = []
    for name in ['indicators.json', 'macro_extra_indicators.json']:
        defs.extend(json.loads((ROOT / 'data' / name).read_text(encoding='utf-8')).get('items', []))
    return [i for i in defs if i.get('source') == 'fred']


def main():
    path = ROOT / 'facts/macro_periods.json'
    old = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'schema': 'macro_periods/1', 'items': {}}
    old.setdefault('items', {})
    defs = load_defs()
    started = time.monotonic()
    errors, done = {}, []
    groups = {}
    for ind in defs:
        groups.setdefault(window_start(ind), []).append(ind)

    def save_state(final=False):
        attempted = dt.datetime.now(dt.timezone.utc).isoformat()
        n_ok, n_all = len(done), len(defs)
        old['status'] = 'complete' if n_ok == n_all else ('partial' if n_ok else 'failed')
        old['attempted_at'] = attempted
        if n_ok:
            old['collected_at'] = attempted
        old['errors'] = dict(errors)
        old['counts'] = {'defined': n_all, 'collected': n_ok, 'failed': len(errors), 'retained_items': len(old['items'])}
        old['finished'] = final
        atomic_write(path, old)

    def out_of_time():
        return time.monotonic() - started > DEADLINE_SEC

    for cosd, inds in groups.items():
        ids = [i['symbol'] for i in inds]
        cols, url = {}, None
        if not out_of_time():
            try:  # 1차: 묶음 한 요청
                url, raw = fetch_csv(ids, cosd)
                cols = parse_columns(raw, ids)
            except Exception as error:
                errors['batch:' + cosd] = type(error).__name__ + ': ' + str(error)[:120]
        for ind in inds:
            sid, sym = ind['id'], ind['symbol']
            if sym not in cols and not out_of_time():  # 2차: 묶음에서 빠졌거나 묶음이 실패한 시리즈만 개별 재시도
                try:
                    u, raw = fetch_csv([sym], cosd)
                    got = parse_columns(raw, [sym])
                    if sym in got:
                        cols[sym], url = got[sym], u
                except Exception as error:
                    errors[sid] = type(error).__name__ + ': ' + str(error)[:120]
            if sym in cols:
                try:
                    old['items'][sid] = build_item(ind, cols[sym], url)
                    done.append(sid)
                    errors.pop(sid, None)
                except Exception as error:
                    errors[sid] = type(error).__name__ + ': ' + str(error)[:120]
            elif sid not in errors:
                errors[sid] = 'DeadlineExceeded: 전체 제한시간 %ds 초과로 시도하지 않음' % DEADLINE_SEC if out_of_time() else 'MissingSeries: 응답에 열이 없음'
            save_state()  # 시리즈마다 중간 저장
    for k in [k for k in errors if k.startswith('batch:')]:
        # 묶음 요청 오류는 개별 재시도로 모든 시리즈가 채워졌다면 기록에서 뺀다
        if len(done) == len(defs):
            errors.pop(k)
    save_state(final=True)
    status, c = old['status'], old['counts']
    summary = f"macro_periods {status}: {c['collected']}/{c['defined']} 수집, 실패 {c['failed']}, 보존 {c['retained_items']}"
    print(json.dumps({'status': status, **c, 'errors': errors}, ensure_ascii=False))
    if status == 'failed':
        print('::error::' + summary)
    elif status == 'partial':
        print('::warning::' + summary)
    step = os.environ.get('GITHUB_STEP_SUMMARY')
    if step:
        with open(step, 'a', encoding='utf-8') as f:
            f.write('### macro_periods\n' + summary + '\n')
    return 0 if status != 'failed' else 1


if __name__ == '__main__':
    sys.exit(main())
