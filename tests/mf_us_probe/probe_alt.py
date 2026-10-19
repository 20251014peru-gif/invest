# -*- coding: utf-8 -*-
"""
미국 멀티팩터 대체 출처 프로브 (1회성 · 읽기 전용)
배경: 야후(yfinance)는 GitHub Actions 에서 429/빈 결과로 막혔다(2026-10-19 probe.py 결과).
목적: 클라우드에서 닿는 대체 출처가 있는지 확인한다.
  - 재무: SEC EDGAR 공식 XBRL API (data.sec.gov/api/xbrl/companyfacts) — 매출·영업이익·순이익·자본
  - 주가: Stooq 일별 CSV (stooq.com/q/d/l/)
  - 참고: FinanceDataReader 의 미국 주가(DataReader) 가 닿는지
SEC 는 요청자를 알리는 User-Agent 를 요구한다 → 공개 저장소 주소만 쓴다(개인 이메일은 보내지 않는다).
원칙: 비밀값·프록시·쿠키 없음 · 저장소에 아무것도 쓰지 않음 · 공개 결과에 응답 본문·예외 원문 없음.
판정: received(수신) 와 valid(필요 항목 충족) 를 나눈다. valid 는 값이 맞다는 뜻이 아니다(정확성은 미검증).
"""
import os, sys, io, json, time, csv, urllib.request, urllib.error
from datetime import datetime, timezone

UA = "invest-multifactor-probe (research; https://github.com/20251014peru-gif/invest)"
SAMPLE = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "BRK-B", "JPM", "XOM", "UNH"]
SCALE_N = int(os.environ.get("US_ALT_N", "30"))
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out_alt")
RESULTS = []
SCALE = {}
CONCEPTS = {
    "revenue": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"],
    "op_income": ["OperatingIncomeLoss"],
    "net_income": ["NetIncomeLoss", "ProfitLoss"],
    "equity": ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
}


def now_iso(): return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get(url, timeout=45):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "identity"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read(), r.status, None
    except urllib.error.HTTPError as ex:
        return None, ex.code, "HTTPError"
    except Exception as ex:
        return None, None, type(ex).__name__


def save():
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "result.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump({"generated_at": now_iso(), "results": RESULTS, "scale": SCALE}, f, ensure_ascii=False, indent=1, default=str)
    nv = sum(1 for r in RESULTS if r.get("valid"))
    L = ["## 멀티팩터 미국 대체 출처 프로브 (SEC EDGAR · Stooq)", "",
         "- 실행: %s · 유효 **%d / %d** 항목 (valid = 필요 항목 충족, 수치 정확성은 **미검증**)" % (now_iso(), nv, len(RESULTS)), "",
         "| 항목 | 수신 | 유효 | HTTP | 소요(초) | 비고 | 오류 |", "|---|---|---|---|---|---|---|"]
    for r in RESULTS:
        L.append("| %s | %s | %s | %s | %s | %s | %s |" % (r["name"], "O" if r.get("received") else "X", "O" if r.get("valid") else "X", r.get("http", ""), r.get("seconds", ""), r.get("note", ""), r.get("error", "")))
    if SCALE:
        L += ["", "### 규모 시험", ""]
        for k, s in SCALE.items():
            L.append("- %s: 성공 %d / %d · 실패 %d · 평균 %.2f초/종목 → 500종목 약 %.1f분(추정, 실측 아님)" % (k, s["ok"], s["n"], s["fail"], s["avg"], s["avg"] * 500 / 60))
    with open(os.path.join(OUT, "result.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L) + "\n")


def rec(name, fn):
    r = {"name": name, "received": False, "valid": False, "at": now_iso()}
    t0 = time.time()
    try:
        out = fn()
        r["seconds"] = round(time.time() - t0, 1)
        r.update(out)
    except BaseException as ex:
        r["seconds"] = round(time.time() - t0, 1); r["error"] = type(ex).__name__
    RESULTS.append(r); save(); return r


def sec_ticker_map():
    body, st, err = get("https://www.sec.gov/files/company_tickers.json")
    if body is None: return {"http": st, "error": err or "no_body"}, None
    d = json.loads(body.decode("utf-8"))
    m = {v["ticker"].upper(): str(v["cik_str"]).zfill(10) for v in d.values()}
    return {"received": True, "http": st, "valid": len(m) > 5000, "note": "티커 %d개" % len(m)}, m


def quarterly_series(facts, tags):
    """companyfacts → 가장 최근 분기(3개월 기간, 10-Q) 값 목록. 어느 태그에서 찾았는지도 돌려준다."""
    g = facts.get("facts", {}).get("us-gaap", {})
    for tag in tags:
        units = g.get(tag, {}).get("units", {}).get("USD")
        if not units: continue
        rows = []
        for u in units:
            if u.get("form") not in ("10-Q", "10-K") or not u.get("start") or not u.get("end"): continue
            try:
                days = (datetime.fromisoformat(u["end"]) - datetime.fromisoformat(u["start"])).days
            except Exception: continue
            if 80 <= days <= 100: rows.append((u["end"], u["val"], u.get("fp"), u.get("form")))
        if rows:
            seen = {}
            for e, v, fp, fm in rows: seen[e] = v
            return sorted(seen.items()), tag
    return [], None


def instant_series(facts, tags):
    g = facts.get("facts", {}).get("us-gaap", {})
    for tag in tags:
        units = g.get(tag, {}).get("units", {}).get("USD")
        if units:
            seen = {u["end"]: u["val"] for u in units if u.get("form") in ("10-Q", "10-K") and not u.get("start")}
            if seen: return sorted(seen.items()), tag
    return [], None


def main():
    r = rec("SEC 티커→CIK 목록", lambda: sec_ticker_map()[0])
    m = None
    try:
        _, m = sec_ticker_map()
    except BaseException:
        m = None
    time.sleep(0.2)
    cik_of = lambda t: (m or {}).get(t.replace("-", "").upper()) or (m or {}).get(t.upper())

    def facts_for(t):
        cik = cik_of(t)
        if not cik: return None, "no_cik"
        body, st, err = get("https://data.sec.gov/api/xbrl/companyfacts/CIK%s.json" % cik)
        if body is None: return None, "http_%s" % st if st else (err or "err")
        return json.loads(body.decode("utf-8")), None

    def sec_one():
        f, err = facts_for("AAPL")
        if f is None: return {"error": err}
        out, notes = {}, []
        for k in ("revenue", "op_income", "net_income"):
            s, tag = quarterly_series(f, CONCEPTS[k]); out[k] = (len(s), tag, s[-1] if s else None)
        eq, tag = instant_series(f, CONCEPTS["equity"])
        ok = all(out[k][0] >= 5 for k in out) and len(eq) >= 2
        return {"received": True, "valid": ok, "note": "분기 3개월 값 개수 매출 %d·영업이익 %d·순이익 %d, 자본 시점 %d · 최근 분기말 %s" % (out["revenue"][0], out["op_income"][0], out["net_income"][0], len(eq), out["revenue"][2][0] if out["revenue"][2] else "-")}
    rec("SEC companyfacts AAPL (분기 매출·영업이익·순이익·자본)", sec_one)

    def stooq_one():
        body, st, err = get("https://stooq.com/q/d/l/?s=aapl.us&i=d")
        if body is None: return {"http": st, "error": err or "no_body"}
        txt = body.decode("utf-8", "replace")
        rows = list(csv.DictReader(io.StringIO(txt)))
        ok = len(rows) >= 250 and {"Date", "Close", "Volume"} <= set(rows[0].keys()) if rows else False
        return {"received": True, "http": st, "valid": ok, "note": "행 %d · 마지막 %s" % (len(rows), rows[-1]["Date"] if rows else "-")}
    rec("Stooq 일별 주가 AAPL.US", stooq_one)

    def fdr_us():
        import FinanceDataReader as fdr
        df = fdr.DataReader("AAPL", "2025-01-01")
        return {"received": True, "valid": len(df) >= 250 and "Close" in df.columns, "note": "행 %d" % len(df)}
    rec("FinanceDataReader 미국 주가 AAPL", fdr_us)

    # 규모 시험
    sp = None
    try:
        import FinanceDataReader as fdr
        sp = [str(s).replace(".", "-") for s in fdr.StockListing("S&P500")["Symbol"].head(SCALE_N)]
    except BaseException:
        pass
    tick = sp or SAMPLE
    for name, fn in (("SEC companyfacts", lambda t: facts_for(t)[0] is not None),
                     ("Stooq 일별 주가", lambda t: (get("https://stooq.com/q/d/l/?s=%s.us&i=d" % t.lower().replace("-", "."))[0] or b"").count(b"\n") >= 250)):
        ok = fail = 0; t0 = time.time()
        for t in tick:
            try:
                if fn(t): ok += 1
                else: fail += 1
            except BaseException:
                fail += 1
            time.sleep(0.15)
        SCALE[name] = {"n": len(tick), "ok": ok, "fail": fail, "avg": (time.time() - t0) / max(1, len(tick))}
        save()
    save(); print("완료")
    return 0


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    os._exit(code)
