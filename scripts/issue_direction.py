# issue_direction.py — 이슈 방향 라벨(유지/약화/반전/재강화/보합) 규칙 계산. 판단·예측 아님: 20거래일 변화(x20)와 5거래일 변화(x5)의 비율만 본다.
# r = 4*x5/x20 (x5 가 x20 의 1/4 속도면 r=1). r<0 반전 · 0≤r<0.5 약화 · 0.5≤r<1.5 유지 · r≥1.5 재강화. |x20| 이 문턱 미만이면 '보합'.
# 문턱값·구간은 임시값(달님 확정 대기). 입력: facts/macro_history.json(일별), facts/kr_investor_history.json(외국인 일별).
# 실행: python -P scripts/issue_direction.py  → facts/issue_direction.json
import datetime as dt, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
KST = dt.timezone(dt.timedelta(hours=9))
# (id, 이름, 방식, 문턱) — 방식 'pct' = 20일 변화율(%) 문턱 / 'abs' = 수준 차이 문턱 / 'flow' = 20일 누적(억원) 문턱
# 문턱 = 1년(약 250거래일) 일별 자료로 잰 '20거래일 변화 절대값의 중앙값'(2026-10-02 계산, 달님 제안 채택): WTI 7.1% · 미10Y 0.10%p · SOX 6.9% · 미 HY OAS 0.13%p.
# 외국인 5,000억은 임시값 — 이력이 34일뿐이라 중앙값을 못 구함(1년 이력 쌓이면 교체). 한 달 써 보고 라벨이 너무 자주/안 바뀌면 조정.
# 주의: macro_history 의 credit_spread 는 한국 AA-회사채-국고3년 차이라 CREDIT-01(미 HY)과 무관 → FRED BAMLH0A0HYM2 를 직접 받는다.
SPECS = [
    ("OIL-01", "WTI", "macro:wti", "pct", 7.1),
    ("RATES-01", "미 10년물(%)", "macro:us10y", "abs", 0.10),
    ("HBM-01", "SOX", "macro:sox", "pct", 6.9),
    ("CREDIT-01", "미 HY OAS(%p)", "fred:BAMLH0A0HYM2", "abs", 0.13),
    ("FLOW-01", "외국인 KOSPI 순매수(억원)", "flow:foreign", "flow", 5000.0),
]


def label(x20, x5, thr):
    """(라벨, r). x20 이 문턱 미만이면 보합."""
    if x20 is None or x5 is None:
        return "이력부족", None
    if abs(x20) < thr:
        return "보합", None
    r = 4.0 * x5 / x20
    if r < 0:
        return "반전", round(r, 2)
    if r < 0.5:
        return "약화", round(r, 2)
    if r < 1.5:
        return "유지", round(r, 2)
    return "재강화", round(r, 2)


def level_changes(vals, kind):
    """vals: 거래일 순 수준값 리스트. 20·5 거래일 전 대비 변화(문턱과 같은 단위)."""
    if len(vals) < 21:
        return None, None
    last = vals[-1]
    ch = (lambda a: (last / a - 1) * 100) if kind == "pct" else (lambda a: last - a)
    return ch(vals[-21]), ch(vals[-6])


def flow_changes(vals):
    """vals: 거래일 순 일별 순매수. 20일 누적 / 5일 누적."""
    if len(vals) < 20:
        return None, None
    return sum(vals[-20:]), sum(vals[-5:])


def macro_series(key):
    days = json.load(open(P("facts", "macro_history.json"), encoding="utf-8")).get("days", {})
    out = []
    for d in sorted(days):
        if dt.date.fromisoformat(d).weekday() >= 5:
            continue      # 주말 행은 직전값 복제라 제외(공휴일은 아직 못 거름 — 한계)
        v = days[d].get(key)
        if isinstance(v, (int, float)):
            out.append(v)
    return out


FRED_ERR = {}


def fred_series(sid):
    """FRED 일별 CSV(키 없음). 실패하면 빈 리스트 → '이력부족'. 값을 만들어 채우지 않는다."""
    import csv, urllib.request
    start = (dt.date.today() - dt.timedelta(days=60)).isoformat()
    try:
        req = urllib.request.Request(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}&cosd={start}", headers={"User-Agent": "Mozilla/5.0"})
        rows = list(csv.reader(urllib.request.urlopen(req, timeout=60).read().decode().splitlines()))[1:]
    except Exception as e:
        FRED_ERR[sid] = f"{type(e).__name__}: {e}"[:120]
        return []
    out = []
    for r in rows:
        try:
            out.append(float(r[1]))
        except (ValueError, IndexError):
            pass      # FRED 빈칸(.)은 건너뜀
    return out


def flow_series():
    try:
        days = json.load(open(P("facts", "kr_investor_history.json"), encoding="utf-8")).get("days", [])
    except Exception:
        return []
    return [x["foreign"] for x in sorted(days, key=lambda x: x["date"]) if x.get("foreign") is not None]


def run():
    res = []
    for iid, name, src, kind, thr in SPECS:
        typ, key = src.split(":")
        if typ == "flow":
            vals = flow_series(); x20, x5 = flow_changes(vals)
        elif typ == "fred":
            vals = fred_series(key); x20, x5 = level_changes(vals, kind)
        else:
            vals = macro_series(key); x20, x5 = level_changes(vals, kind)
        lab, r = label(x20, x5, thr)
        res.append({"id": iid, "name": name, "label": lab, "r": r, "x20": None if x20 is None else round(x20, 2),
                    "x5": None if x5 is None else round(x5, 2), "thr": thr, "n": len(vals), "err": FRED_ERR.get(key, "")})
    obj = {"schema": "issue_direction/1", "computed": dt.datetime.now(KST).replace(microsecond=0).isoformat(),
           "rule": "r=4*x5/x20; r<0 반전, <0.5 약화, <1.5 유지, 그 이상 재강화; |x20|<문턱=보합 (임시값)", "items": res}
    os.makedirs(P("facts"), exist_ok=True)
    json.dump(obj, open(P("facts", "issue_direction.json"), "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=2)
    for x in res:
        print(x["id"], x["label"], x["r"], x["x20"], x["x5"], f"n={x['n']}")
    return 0


if __name__ == "__main__":
    sys.exit(run())
