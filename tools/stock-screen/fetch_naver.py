"""네이버 증권 주봉 시세 → CSV (2026-10-28 클라우드 환경에서 응답 확인).
사용: python3 fetch_naver.py [상위N=100] > 시세.csv     (코스피 시가총액 상위 N개, 종목당 1초 간격)
출처는 네이버의 비공식 내부 주소다. 주소·키가 바뀔 수 있고 자동 수집 약관 허용 여부는 미확인이다.
받은 CSV·엑셀은 저장소에 올리지 말 것(HOME_HANDOFF: 데이터 출처 약관 근거 없음)."""
import sys, csv, json, time, urllib.request
LIST = "https://m.stock.naver.com/api/stocks/marketValue/KOSPI?page=1&pageSize=%d"
CHART = "https://api.stock.naver.com/chart/domestic/item/%s?periodType=weekCandle&range=3"
def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return json.load(urllib.request.urlopen(req, timeout=20))
def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    w = csv.writer(sys.stdout); w.writerow(["종목명", "일자", "종가", "거래량"])
    stocks = get(LIST % n)["stocks"]
    for s in stocks:
        try: items = get(CHART % s["itemCode"])["priceInfos"]
        except Exception as e:
            print(f"건너뜀 {s['stockName']}: {e}", file=sys.stderr); continue
        for it in items:
            d = it["localDate"]
            w.writerow([f'{s["stockName"]}({s["itemCode"]})', f"{d[:4]}-{d[4:6]}-{d[6:]}", it["closePrice"], it["accumulatedTradingVolume"]])
        time.sleep(1)
main()
