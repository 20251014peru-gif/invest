# kr_investor_history.py — 외국인 KOSPI 순매수 일별 이력(facts/kr_investor_history.json). 방향 라벨(20일 기준)의 입력.
# 외국인 정의(2026-10-02 Claude 판단, 달님 위임): KOSPI '외국인'+'기타외국인' 합 = KRX 외국인 합계. 단위 억원, 순매수 현물.
# 매일: facts/kr_investor.json 의 days 를 이력에 합친다. 이력이 BACKFILL_MIN 일보다 적으면 pykrx 로 과거를 채운다(KOSPI 만, 1일 1회 호출).
# 실행: python -P scripts/kr_investor_history.py  (KRX_ID·KRX_PW 필요 — 백필할 때만). 실패해도 있는 값은 지우지 않는다.
import datetime as dt, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
OUT = P("facts", "kr_investor_history.json")
BACKFILL_MIN = 25
BACKFILL_DAYS = 45      # 달력일 기준 되짚는 길이


def load(path, default):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return default


def foreign_total(kospi):
    a, b = kospi.get("외국인"), kospi.get("기타외국인")
    return None if a is None or b is None else round(a + b, 1)


def merge_daily(hist, inv):
    for d in inv.get("days", []):
        k = d.get("KOSPI")
        if k and foreign_total(k) is not None:
            hist[d["date"]] = foreign_total(k)


def backfill(hist, today):
    sys.path[:] = [p for p in sys.path if os.path.abspath(p or ".") != os.path.dirname(os.path.abspath(__file__))]
    from pykrx import stock
    d = today
    for _ in range(BACKFILL_DAYS):
        d -= dt.timedelta(days=1)
        if d.weekday() >= 5 or d.isoformat() in hist:
            continue
        ds = d.strftime("%Y%m%d")
        df = stock.get_market_trading_value_by_investor(ds, ds, "KOSPI")
        if df is None or df.empty:
            continue      # 휴장
        col = "순매수" if "순매수" in df.columns else df.columns[-1]
        try:
            hist[d.isoformat()] = round((float(df.loc["외국인", col]) + float(df.loc["기타외국인", col])) / 1e8, 1)
        except KeyError:
            continue


def main():
    obj = load(OUT, {"schema": "kr_investor_history/1", "days": []})
    hist = {x["date"]: x["foreign"] for x in obj.get("days", [])}
    merge_daily(hist, load(P("facts", "kr_investor.json"), {}))
    err = ""
    if len(hist) < BACKFILL_MIN:
        try:
            backfill(hist, dt.date.today())
        except Exception as e:
            err = f"{type(e).__name__}: {e}"[:200]
    obj = {"schema": "kr_investor_history/1", "definition": "KOSPI 외국인+기타외국인 순매수(억원, 현물)",
           "days": [{"date": d, "foreign": hist[d]} for d in sorted(hist)], "backfill_error": err}
    json.dump(obj, open(OUT, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=2)
    print(f"이력 {len(hist)}일", ("백필 실패: " + err) if err else "")
    return 0


if __name__ == "__main__":
    sys.exit(main())
