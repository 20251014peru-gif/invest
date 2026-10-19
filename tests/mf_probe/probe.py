# -*- coding: utf-8 -*-
"""
멀티팩터(국내) 데이터 확보 프로브 (1회성 시험 · 클라우드 실행 전)
목적: GitHub-hosted runner(데이터센터 IP) 에서 FinanceDataReader 가 국내 종목 목록·주가·재무를
      실제로 받아오는지 확인한다. (책 2장 멀티팩터 구현의 데이터 전제 조건)

원칙: 키·Firestore·AI·프록시·쿠키 없음 · 저장소에 아무것도 쓰지 않음 · 공개 결과에 응답 본문·예외 원문 없음.
      공개 결과에 남기는 오류 정보는 error_kind / error_class / http_status 뿐이다.

판정은 두 겹으로 나눈다:
  received = 라이브러리가 데이터프레임을 돌려줬다         (수신 여부)
  valid    = 필요한 열이 있고 행 수·최신성 기준을 만족한다  (구조 유효성)
'valid' 는 값이 정확하다는 뜻이 아니다. 수치의 정확성은 이 시험에서 검증하지 않는다 (항상 "미검증").

사용: python tests/mf_probe/probe.py  → tests/mf_probe/out/result.json + result.md (항목마다 즉시 저장)
종료코드: 0 = 시험이 끝까지 실행됨(데이터 확보 여부와 무관) · 2 = 실행 실패(라이브러리 import 실패 등)
"""
import os, sys, json, time, platform, threading
from datetime import datetime, timezone, timedelta

CALL_TIMEOUT_SEC = 90        # 호출 1건의 상한. 넘으면 '시간 초과'로 기록하고 다음 항목으로 넘어간다
SAMPLE_N = 5                 # 종목 반복 시험 개수 (시가총액 상위)
SLEEP_BETWEEN_SEC = 1.0      # 종목 사이 대기 (요청 제한 예방)
FALLBACK_CODES = ["005930", "000660", "373220", "207940", "005380"]   # 목록 조회 실패 시 대체
MIN_LISTING_ROWS = 1000      # KRX 전체 종목 수는 수천 개 — 이보다 적으면 '유효' 아님
MIN_PRICE_ROWS = 200         # 1년 거래일 약 240 — 이보다 적으면 '유효' 아님
MAX_STALE_DAYS = 10          # 마지막 주가 날짜가 이보다 오래되면 '유효' 아님
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
RESULTS = []

def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def classify(ex):
    """예외 → 공개 가능한 최소 정보(원문 메시지는 버린다)."""
    name = type(ex).__name__
    status = None
    resp = getattr(ex, "response", None)
    if resp is not None:
        status = getattr(resp, "status_code", None)
    low = name.lower()
    if isinstance(ex, TimeoutError) or "timeout" in low: kind = "timeout"
    elif status is not None: kind = "http_%s" % status
    elif "connection" in low or "ssl" in low or "proxy" in low: kind = "network"
    elif "json" in low or "decode" in low or "parse" in low: kind = "parse"
    elif isinstance(ex, (KeyError, IndexError, ValueError)): kind = "data_shape"
    else: kind = "other"
    return {"error_kind": kind, "error_class": name, "http_status": status}

def call_with_timeout(fn, sec):
    """fn() 실행. sec 초 안에 끝나지 않으면 TimeoutError (스레드는 남지만 데몬이라 종료를 막지 않는다)."""
    box = {}
    def run():
        try: box["v"] = fn()
        except BaseException as ex: box["e"] = ex
    t = threading.Thread(target=run, daemon=True)
    t.start(); t.join(sec)
    if t.is_alive(): raise TimeoutError("호출 시간 초과(%ss)" % sec)
    if "e" in box: raise box["e"]
    return box.get("v")

def save():
    os.makedirs(OUT, exist_ok=True)
    meta = {
        "generated_at": now_iso(), "python": platform.python_version(), "platform": platform.platform(),
        "libs": LIBS, "overall_value_accuracy": "미검증",
    }
    with open(os.path.join(OUT, "result.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump({"meta": meta, "results": RESULTS}, f, ensure_ascii=False, indent=2)
    n_valid = sum(1 for r in RESULTS if r.get("valid"))
    lines = ["## 멀티팩터 국내 데이터 확보 프로브", "",
             "- 실행 환경: Python %s · %s" % (meta["python"], meta["platform"]),
             "- 라이브러리: %s" % ", ".join("%s %s" % (k, v) for k, v in LIBS.items()),
             "- 유효 확보 **%d / %d** 항목 (valid = 필요한 열·행 수·최신성 기준 충족. 수치 정확성은 **미검증**)" % (n_valid, len(RESULTS)),
             "- 워크플로 초록색 = 시험이 끝까지 실행됨일 뿐이다. 확보 여부는 아래 표의 '유효' 열로만 판단한다.", "",
             "| 항목 | 수신 | 유효 | 소요(초) | 행 수 | 비고 | 오류 |", "|---|---|---|---|---|---|---|"]
    for r in RESULTS:
        err = "" if not r.get("error_kind") else "%s (%s%s)" % (r["error_kind"], r.get("error_class", ""),
                                                              (", HTTP %s" % r["http_status"]) if r.get("http_status") else "")
        lines.append("| %s | %s | %s | %s | %s | %s | %s |" % (
            r["name"], "O" if r.get("received") else "X", "O" if r.get("valid") else "X",
            r.get("seconds", ""), r.get("rows", ""), r.get("note", ""), err))
    s = SAMPLE_SUMMARY
    if s:
        lines += ["", "### 종목 반복 시험 (시가총액 상위 %d개, 종목당 주가 1회 + 분기 재무 1회)" % s["n"], "",
                  "- 종목 코드 출처: %s" % s["code_source"],
                  "- 주가 유효 %d/%d · 분기 재무 유효 %d/%d" % (s["price_ok"], s["n"], s["fin_ok"], s["n"]),
                  "- 종목당 평균 %.1f초 → 100종목 순차 실행 시 **약 %.0f분으로 추정** (추정치일 뿐 실측 아님)" % (s["avg_sec"], s["avg_sec"] * 100 / 60)]
    with open(os.path.join(OUT, "result.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")

def check(name, fn, validate):
    """fn() → DataFrame. validate(df) → (valid:bool, note:str). 결과를 즉시 저장한다."""
    rec = {"name": name, "received": False, "valid": False, "at": now_iso()}
    t0 = time.time()
    try:
        df = call_with_timeout(fn, CALL_TIMEOUT_SEC)
        rec["seconds"] = round(time.time() - t0, 1)
        if df is None or not hasattr(df, "shape"):
            rec.update(error_kind="data_shape", error_class="NoneOrNotDataFrame")
        else:
            rec["received"] = True
            rec["rows"] = int(df.shape[0])
            valid, note = validate(df)
            rec["valid"] = bool(valid); rec["note"] = note
    except BaseException as ex:
        rec["seconds"] = round(time.time() - t0, 1)
        rec.update(classify(ex))
    RESULTS.append(rec); save()
    return rec

def has_cols(df, cols):
    missing = [c for c in cols if c not in df.columns]
    return (not missing), ("필요 열 모두 있음" if not missing else "없는 열: " + ", ".join(missing))

def v_listing(df):
    ok, note = has_cols(df, ["Code", "Name", "Marcap"])
    if ok and df.shape[0] < MIN_LISTING_ROWS: return False, "행 수 부족(<%d)" % MIN_LISTING_ROWS
    return ok, note

def v_price(df):
    ok, note = has_cols(df, ["Close", "Volume"])
    if not ok: return False, note
    if df.shape[0] < MIN_PRICE_ROWS: return False, "행 수 부족(<%d)" % MIN_PRICE_ROWS
    last = df.index[-1]
    try: days = (datetime.now() - last.to_pydatetime().replace(tzinfo=None)).days
    except Exception: return False, "날짜 인덱스 해석 실패"
    if days > MAX_STALE_DAYS: return False, "최신성 부족(마지막 주가 %d일 전)" % days
    return True, "마지막 주가 %d일 전" % days

def v_fin_annual(df):
    ok, note = has_cols(df, ["PER(배)", "PBR(배)", "영업이익"])
    if not ok: return False, note
    if df["PER(배)"].dropna().empty or df["PBR(배)"].dropna().empty: return False, "PER/PBR 값이 모두 비어 있음"
    return True, "PER/PBR 값 있음(추정치 행 포함 여부는 별도 처리 필요)"

def v_fin_quarter(df):
    ok, note = has_cols(df, ["매출액", "영업이익", "당기순이익", "ROE(%)"])
    if not ok: return False, note
    if df.dropna(subset=["영업이익"]).shape[0] < 2: return False, "확정(영업이익 있는) 분기 2개 미만"
    return True, "확정 분기 %d개" % df.dropna(subset=["영업이익"]).shape[0]

LIBS = {}
SAMPLE_SUMMARY = None

def main():
    global SAMPLE_SUMMARY
    try:
        import importlib.metadata as md
        import FinanceDataReader as fdr
        import pandas as pd
        for pkg in ("finance-datareader", "pandas", "requests"):
            try: LIBS[pkg] = md.version(pkg)
            except Exception: LIBS[pkg] = "?"
    except BaseException as ex:
        print("import 실패:", type(ex).__name__); return 2

    today = datetime.now()
    start = (today - timedelta(days=370)).strftime("%Y%m%d")
    end = today.strftime("%Y%m%d")

    listing = {}
    def get_listing():
        df = fdr.StockListing("KRX"); listing["df"] = df; return df
    check("종목 목록 KRX (StockListing)", get_listing, v_listing)
    check("주가 1년 삼성전자 (DataReader)", lambda: fdr.DataReader("005930", start, end), v_price)
    check("연간 재무 삼성전자 (SnapDataReader 2Y)", lambda: fdr.SnapDataReader("NAVER/FINSTATE-2Y/005930"), v_fin_annual)
    check("분기 재무 삼성전자 (SnapDataReader 2Q)", lambda: fdr.SnapDataReader("NAVER/FINSTATE-2Q/005930"), v_fin_quarter)

    codes, src = FALLBACK_CODES[:SAMPLE_N], "고정 목록(종목 목록 조회 실패 또는 열 없음)"
    try:
        df = listing.get("df")
        if df is not None and {"Code", "Marcap"} <= set(df.columns):
            codes = [str(c) for c in df.sort_values("Marcap", ascending=False)["Code"].head(SAMPLE_N)]
            src = "KRX 목록의 시가총액 상위"
    except BaseException:
        pass

    price_ok = fin_ok = 0; total_sec = 0.0
    for code in codes:
        t0 = time.time()
        r1 = check("반복 주가 %s" % code, lambda c=code: fdr.DataReader(c, start, end), v_price)
        r2 = check("반복 분기재무 %s" % code, lambda c=code: fdr.SnapDataReader("NAVER/FINSTATE-2Q/%s" % c), v_fin_quarter)
        price_ok += 1 if r1["valid"] else 0; fin_ok += 1 if r2["valid"] else 0
        total_sec += time.time() - t0
        time.sleep(SLEEP_BETWEEN_SEC)
    SAMPLE_SUMMARY = {"n": len(codes), "code_source": src, "price_ok": price_ok, "fin_ok": fin_ok,
                      "avg_sec": total_sec / max(1, len(codes))}
    save()
    n_valid = sum(1 for r in RESULTS if r["valid"])
    print("완료: 유효 %d/%d (시험이 끝까지 실행됨. 데이터 정확성은 미검증)" % (n_valid, len(RESULTS)))
    return 0

if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    os._exit(code)   # 시간 초과로 남은 데몬 스레드가 있어도 종료를 막지 않는다
