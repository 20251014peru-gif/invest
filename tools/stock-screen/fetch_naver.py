"""네이버 증권 시세 → CSV (미검증 초안: 이 개발 환경은 네이버 접속이 막혀 실행해 보지 못했다).
사용: python3 fetch_naver.py 종목목록.csv "<F12에서 복사한 주소의 종목코드 부분을 {code}로 바꾼 URL>" > 시세.csv
종목목록.csv 열: 종목명,종목코드.  응답 JSON 에서 priceInfos 목록을 찾고 키 이름은 아래 후보 중 먼저 맞는 것을 쓴다.
키 이름이 다르면 실행 시 오류로 알려주니 DATE/CLOSE/VOL 후보만 고치면 된다."""
import sys, csv, json, time, urllib.request
DATE, CLOSE, VOL = ("localDate", "localTradedAt", "date"), ("closePrice", "close"), ("accumulatedTradingVolume", "volume")
def pick(d, keys):
    for k in keys:
        if k in d: return d[k]
    raise KeyError(f"키 없음 {keys} / 실제 키: {list(d)}")
def find_list(x):
    if isinstance(x, dict):
        if "priceInfos" in x: return x["priceInfos"]
        for v in x.values():
            r = find_list(v)
            if r is not None: return r
    return None
def main():
    stocks, url = sys.argv[1], sys.argv[2]
    w = csv.writer(sys.stdout); w.writerow(["종목명", "일자", "종가", "거래량"])
    for r in csv.DictReader(open(stocks, encoding="utf-8-sig")):
        req = urllib.request.Request(url.format(code=r["종목코드"]), headers={"User-Agent": "Mozilla/5.0"})
        data = json.load(urllib.request.urlopen(req, timeout=20))
        items = find_list(data)
        if items is None: raise SystemExit(f"{r['종목명']}: priceInfos 없음. 응답 구조를 확인하세요.")
        for it in items:
            d = str(pick(it, DATE)); d = f"{d[:4]}-{d[4:6]}-{d[6:8]}" if d.isdigit() else d[:10]
            w.writerow([r["종목명"], d, str(pick(it, CLOSE)).replace(",", ""), str(pick(it, VOL)).replace(",", "")])
        time.sleep(1)   # 차단 방지: 종목당 1초 간격
main()
