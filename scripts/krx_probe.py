# krx_probe.py — 시험용. KRX 로그인(pykrx)으로 시장 전체 투자자별 순매수가 GitHub Actions에서 받아지는지만 확인한다.
# 파일에 쓰지 않고 로그에만 출력. 계정 값은 출력하지 않는다(있음/없음만).
import os, sys
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
print("KRX_ID 설정:", bool(os.environ.get("KRX_ID")), "| KRX_PW 설정:", bool(os.environ.get("KRX_PW")))
try:
    import pykrx
    from pykrx import stock
    print("pykrx 버전:", getattr(pykrx, "__version__", "미확인"))
except Exception as e:
    print("pykrx 불러오기 실패:", type(e).__name__, e); sys.exit(1)

ok = 0
day = datetime.now(KST)
for _ in range(10):
    if day.weekday() < 5:
        d = day.strftime("%Y%m%d")
        for mkt in ("KOSPI", "KOSDAQ"):
            try:
                df = stock.get_market_trading_value_by_investor(d, d, mkt)
                if df is None or df.empty:
                    print(f"{d} {mkt}: 빈 결과(휴장이거나 미공표 또는 로그인 실패)")
                    continue
                col = "순매수" if "순매수" in df.columns else df.columns[-1]
                row = {k: round(float(df.loc[k, col]) / 1e8, 1) for k in ("외국인", "기관합계", "개인") if k in df.index}
                print(f"{d} {mkt}: 순매수(억원) {row}  | 행: {list(df.index)}")
                ok += 1
            except Exception as e:
                print(f"{d} {mkt}: 실패 {type(e).__name__}: {str(e)[:200]}")
    day -= timedelta(days=1)
    if ok >= 4:
        break
print("성공 건수:", ok)
sys.exit(0 if ok else 1)
