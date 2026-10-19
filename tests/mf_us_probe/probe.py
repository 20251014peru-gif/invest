# -*- coding: utf-8 -*-
"""
멀티팩터(미국) 데이터 확보 프로브 (1회성 시험 · 읽기 전용)
목적: GitHub-hosted runner(데이터센터 IP)에서 미국 멀티팩터에 필요한 자료를 실제로 받는지 확인한다.
  - S&P 500 종목 목록(FinanceDataReader → 위키백과)
  - 일별 주가·거래량(yfinance.download) — 모멘텀
  - 종목 요약(yfinance Ticker.info: trailingPE, priceToBook, revenueGrowth, earningsGrowth, returnOnEquity, operatingMargins) — 책 패키지가 쓰는 방식
  - 분기 재무제표(Ticker.quarterly_income_stmt / quarterly_balance_sheet) — 책 방식의 대안(직접 증가율 계산)
  - 규모 시험: 종목 N개를 간격을 두고 연속 호출해 실패율·차단(429 등) 확인

원칙: 키·비밀값·프록시·쿠키 없음 · 저장소에 아무것도 쓰지 않음 · 공개 결과에 응답 본문·예외 원문 없음(error_kind/error_class/http_status 만).
판정: received(수신)와 valid(필요한 항목·행 수 충족)를 나눈다. valid 가 값이 맞다는 뜻은 아니다(정확성은 항상 "미검증").
종료코드: 0 = 시험이 끝까지 실행됨 · 2 = 실행 실패(import 실패 등)
"""
import os, sys, json, time, platform, threading
from datetime import datetime, timezone

CALL_TIMEOUT_SEC = 90
INFO_KEYS = ["trailingPE", "priceToBook", "revenueGrowth", "earningsGrowth", "returnOnEquity", "operatingMargins", "marketCap"]
SAMPLE = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "BRK-B", "JPM", "XOM", "UNH"]
SCALE_N = int(os.environ.get("US_SCALE_N", "60"))
SCALE_SLEEP = 0.3
MAX_CONSEC_FAIL = 10
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
RESULTS = []
LIBS = {}
SCALE = None


def now_iso(): return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def classify(ex):
    name = type(ex).__name__
    status = None
    for attr in ("response",):
        resp = getattr(ex, attr, None)
        if resp is not None: status = getattr(resp, "status_code", None)
    msg = str(ex).lower()
    low = name.lower()
    if "ratelimit" in low or "too many requests" in msg or "429" in msg: return {"error_kind": "rate_limited", "error_class": name, "http_status": status or 429}
    if isinstance(ex, TimeoutError) or "timeout" in low: kind = "timeout"
    elif status is not None: kind = "http_%s" % status
    elif "connection" in low or "ssl" in low or "proxy" in low: kind = "network"
    elif "json" in low or "decode" in low or "parse" in low: kind = "parse"
    elif isinstance(ex, (KeyError, IndexError, ValueError, AttributeError, TypeError)): kind = "data_shape"
    else: kind = "other"
    return {"error_kind": kind, "error_class": name, "http_status": status}


def call_with_timeout(fn, sec):
    box = {}
    def run():
        try: box["v"] = fn()
        except BaseException as ex: box["e"] = ex
    t = threading.Thread(target=run, daemon=True); t.start(); t.join(sec)
    if t.is_alive(): raise TimeoutError("timeout")
    if "e" in box: raise box["e"]
    return box.get("v")


def save():
    os.makedirs(OUT, exist_ok=True)
    meta = {"generated_at": now_iso(), "python": platform.python_version(), "platform": platform.platform(), "libs": LIBS, "overall_value_accuracy": "미검증"}
    with open(os.path.join(OUT, "result.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump({"meta": meta, "results": RESULTS, "scale": SCALE}, f, ensure_ascii=False, indent=1, default=str)
    nv = sum(1 for r in RESULTS if r.get("valid"))
    L = ["## 멀티팩터 미국 데이터 확보 프로브", "",
         "- 실행 환경: Python %s · %s" % (meta["python"], meta["platform"]),
         "- 라이브러리: %s" % ", ".join("%s %s" % (k, v) for k, v in LIBS.items()),
         "- 유효 확보 **%d / %d** 항목 (valid = 필요한 열·행 수 충족. 수치 정확성은 **미검증**)" % (nv, len(RESULTS)),
         "- 워크플로 초록색 = 시험이 끝까지 실행됨일 뿐이다. 확보 여부는 아래 표의 '유효' 열로만 판단한다.", "",
         "| 항목 | 수신 | 유효 | 소요(초) | 비고 | 오류 |", "|---|---|---|---|---|---|"]
    for r in RESULTS:
        err = "" if not r.get("error_kind") else "%s (%s%s)" % (r["error_kind"], r.get("error_class", ""), (", HTTP %s" % r["http_status"]) if r.get("http_status") else "")
        L.append("| %s | %s | %s | %s | %s | %s |" % (r["name"], "O" if r.get("received") else "X", "O" if r.get("valid") else "X", r.get("seconds", ""), r.get("note", ""), err))
    if SCALE:
        s = SCALE
        L += ["", "### 규모 시험 (Ticker.info + 분기 손익계산서, 종목 %d개 연속, 호출 간격 %.1f초)" % (s["n"], SCALE_SLEEP), "",
              "- 결과: info 성공 %d · 분기 손익 성공 %d · 실패 %d · 차단(429) %d · 중단 규칙 발동: %s" % (s["info_ok"], s["stmt_ok"], s["fail"], s["rate_limited"], "예" if s["aborted"] else "아니오"),
              "- 종목당 평균 %.1f초 → 500종목 순차 실행 시 **약 %.0f분으로 추정**(추정치, 실측 아님)" % (s["avg_sec"], s["avg_sec"] * 500 / 60),
              "- info 핵심 항목이 채워진 비율: " + ", ".join("%s %d/%d" % (k, v, s["info_ok"]) for k, v in s["key_filled"].items())]
    with open(os.path.join(OUT, "result.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L) + "\n")


def check(name, fn, validate):
    rec = {"name": name, "received": False, "valid": False, "at": now_iso()}
    t0 = time.time()
    try:
        v = call_with_timeout(fn, CALL_TIMEOUT_SEC)
        rec["seconds"] = round(time.time() - t0, 1)
        rec["received"] = True
        ok, note = validate(v)
        rec["valid"] = bool(ok); rec["note"] = note
    except BaseException as ex:
        rec["seconds"] = round(time.time() - t0, 1)
        rec.update(classify(ex))
    RESULTS.append(rec); save()
    return rec


def main():
    global SCALE
    try:
        import importlib.metadata as md
        import FinanceDataReader as fdr
        import yfinance as yf
        import pandas as pd
        for p in ("finance-datareader", "yfinance", "pandas", "requests"):
            try: LIBS[p] = md.version(p)
            except Exception: LIBS[p] = "?"
    except BaseException as ex:
        print("import 실패:", type(ex).__name__); return 2

    sp = {}
    def get_sp():
        df = fdr.StockListing("S&P500"); sp["df"] = df; return df
    def v_sp(df):
        cols = {"Symbol", "Name"} <= set(df.columns)
        return (cols and len(df) >= 450), "행 %d · 열 %s" % (len(df), ",".join(map(str, df.columns))[:80])
    check("S&P 500 종목 목록 (FDR)", get_sp, v_sp)

    def get_px():
        return yf.download(SAMPLE, period="2y", interval="1d", progress=False, auto_adjust=False, threads=False)
    def v_px(df):
        if df is None or len(df) == 0: return False, "빈 결과"
        close = df["Close"]
        full = int((close.notna().sum() >= 250).sum())
        return full == len(SAMPLE), "행 %d · 250행 이상 %d/%d종목 · 마지막 %s" % (len(df), full, len(SAMPLE), str(df.index[-1].date()))
    check("일별 주가 %d종목 2년 (yf.download)" % len(SAMPLE), get_px, v_px)

    def get_info():
        out = {}
        for t in SAMPLE[:5]:
            out[t] = yf.Ticker(t).info; time.sleep(0.3)
        return out
    def v_info(d):
        filled = {k: sum(1 for t in d if isinstance(d[t], dict) and d[t].get(k) is not None) for k in INFO_KEYS}
        return all(filled[k] >= 4 for k in ("trailingPE", "priceToBook", "revenueGrowth", "earningsGrowth", "returnOnEquity")), "채움 " + ", ".join("%s %d/5" % (k, v) for k, v in filled.items())
    check("Ticker.info 5종목 (책 방식 입력)", get_info, v_info)

    def get_stmt():
        t = yf.Ticker("AAPL")
        return t.quarterly_income_stmt, t.quarterly_balance_sheet
    def v_stmt(x):
        inc, bal = x
        rows = [r for r in ("Total Revenue", "Operating Income", "Net Income") if r in inc.index]
        eq = [r for r in ("Stockholders Equity", "Common Stock Equity") if r in bal.index]
        return (len(rows) == 3 and inc.shape[1] >= 5 and bool(eq)), "손익 열(분기) %d · 필요 행 %d/3 · 자본 행 %s" % (inc.shape[1], len(rows), ",".join(eq) or "없음")
    check("분기 재무제표 AAPL (직접 증가율 계산용)", get_stmt, v_stmt)

    # 규모 시험
    tickers = []
    try:
        df = sp.get("df")
        if df is not None: tickers = [str(s).replace(".", "-").replace("/", "-") for s in df["Symbol"].head(SCALE_N)]
    except BaseException:
        pass
    if not tickers: tickers = SAMPLE
    s = {"n": len(tickers), "info_ok": 0, "stmt_ok": 0, "fail": 0, "rate_limited": 0, "aborted": False, "key_filled": {k: 0 for k in INFO_KEYS}, "avg_sec": 0.0}
    consec, t_all = 0, time.time()
    for t in tickers:
        ok_info = False
        try:
            info = call_with_timeout(lambda: yf.Ticker(t).info, CALL_TIMEOUT_SEC)
            if isinstance(info, dict) and len(info) > 5:
                ok_info = True; s["info_ok"] += 1
                for k in INFO_KEYS:
                    if info.get(k) is not None: s["key_filled"][k] += 1
            else:
                raise ValueError("empty_info")
            inc = call_with_timeout(lambda: yf.Ticker(t).quarterly_income_stmt, CALL_TIMEOUT_SEC)
            if inc is not None and inc.shape[1] >= 5: s["stmt_ok"] += 1
            consec = 0
        except BaseException as ex:
            c = classify(ex); s["fail"] += 1; consec += 1
            if c["error_kind"] == "rate_limited": s["rate_limited"] += 1
            if consec >= MAX_CONSEC_FAIL: s["aborted"] = True; break
        time.sleep(SCALE_SLEEP)
    s["avg_sec"] = (time.time() - t_all) / max(1, len(tickers))
    SCALE = s; save()
    print("완료: 유효 %d/%d, 규모 시험 info %d/%d" % (sum(1 for r in RESULTS if r["valid"]), len(RESULTS), s["info_ok"], s["n"]))
    return 0


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    os._exit(code)
