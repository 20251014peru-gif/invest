# krx_probe.py v2 — 시험용. KRX 로그인(pykrx)으로 시장 전체 투자자별 순매수가 받아지는지 + 숫자가 서로 맞는지 검사.
# 파일에 쓰지 않고 로그에만 출력. 계정 값은 출력하지 않는다.
import os, sys
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
INST = ["금융투자", "보험", "투신", "사모", "은행", "기타금융", "연기금 등"]  # 합 = 기관합계
TOP = ["기관합계", "기타법인", "개인", "외국인", "기타외국인"]                 # 합 = 전체(=0이어야 함)


def eok(df, col, k):
    return round(float(df.loc[k, col]) / 1e8, 1) if k in df.index else None


def summarize(df):
    """순매수(억원) 행별 값과 합계 검사 결과를 dict로 돌려준다."""
    col = "순매수" if "순매수" in df.columns else df.columns[-1]
    v = {k: eok(df, col, k) for k in df.index}
    out = {"rows": v}
    if all(v.get(k) is not None for k in INST + ["기관합계"]):
        out["기관 세부합-기관합계"] = round(sum(v[k] for k in INST) - v["기관합계"], 1)
    if all(v.get(k) is not None for k in TOP):
        out["5구분 합계(0이어야 함)"] = round(sum(v[k] for k in TOP), 1)
        out["외국인+기타외국인"] = round(v["외국인"] + v["기타외국인"], 1)
    if v.get("전체") is not None:
        out["전체 행"] = v["전체"]
    return out


def main():
    print("KRX_ID 설정:", bool(os.environ.get("KRX_ID")), "| KRX_PW 설정:", bool(os.environ.get("KRX_PW")))
    now = datetime.now(KST)
    print("실행 시각(KST):", now.strftime("%Y-%m-%d %H:%M"), "(15:30 이전이면 오늘 값은 장중 잠정치)")
    try:
        import pykrx
        from pykrx import stock
        print("pykrx 버전:", getattr(pykrx, "__version__", "미확인"))
    except Exception as e:
        print("pykrx 불러오기 실패:", type(e).__name__, e)
        return 1
    ok = 0
    day = now
    for _ in range(10):
        if day.weekday() < 5:
            d = day.strftime("%Y%m%d")
            for mkt in ("KOSPI", "KOSDAQ"):
                try:
                    df = stock.get_market_trading_value_by_investor(d, d, mkt)
                    if df is None or df.empty:
                        print(f"{d} {mkt}: 빈 결과(휴장·미공표·로그인 실패 중 하나)")
                        continue
                    s = summarize(df)
                    print(f"[{d} {mkt}] 순매수(억원)")
                    print("  행별:", s["rows"])
                    for k, val in s.items():
                        if k != "rows":
                            print(f"  {k}: {val}")
                    ok += 1
                except Exception as e:
                    print(f"{d} {mkt}: 실패 {type(e).__name__}: {str(e)[:200]}")
        day -= timedelta(days=1)
        if ok >= 4:
            break
    print("성공 건수:", ok)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
