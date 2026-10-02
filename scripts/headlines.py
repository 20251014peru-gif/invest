# headlines.py — 경제 헤드라인(연합·한경·매경) RSS 를 받아 facts/headlines.json 에 저장. 예약 세션·작업 환경은 외부 사이트가 막혀 있어 이 파일을 대신 읽는다.
# 직접 RSS 가 실패하면 같은 매체의 Google News RSS 로 대체(issue_board.py 와 같은 방식). 실패한 매체는 이전 값을 지우지 않고 status 만 남긴다.
import datetime as dt, json, os, sys, urllib.request
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "facts", "headlines.json")
G = "https://news.google.com/rss/search?q=site:{}+when:1d&hl=ko&gl=KR&ceid=KR:ko"
FEEDS = [("연합뉴스", "https://www.yna.co.kr/rss/economy.xml", G.format("yna.co.kr")),
         ("한국경제", "https://www.hankyung.com/feed/economy", G.format("hankyung.com")),
         ("매일경제", "https://www.mk.co.kr/rss/30100041/", G.format("mk.co.kr"))]
KEEP = 60


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    root = ET.fromstring(urllib.request.urlopen(req, timeout=25).read())
    out = []
    for it in root.iter("item"):
        t = (it.findtext("title") or "").strip()
        if t:
            out.append({"title": t, "link": (it.findtext("link") or "").strip(), "pub": (it.findtext("pubDate") or "").strip()})
    return out


def main():
    try:
        prev = json.load(open(OUT, encoding="utf-8"))
    except Exception:
        prev = {}
    res = {}
    for name, direct, fallback in FEEDS:
        items, via, err = [], "", ""
        for label, url in (("직접", direct), ("구글뉴스", fallback)):
            try:
                items = fetch(url)
            except Exception as e:
                err = f"{label}: {type(e).__name__}"[:80]
                continue
            if items:
                via = label
                break
        if items:
            res[name] = {"status": "ok", "via": via, "items": items[:KEEP]}
        else:
            old = (prev.get("sources") or {}).get(name, {})
            res[name] = {"status": "fail", "error": err or "빈 응답", "items": old.get("items", []), "stale": True}
    obj = {"schema": "headlines/1", "collected_at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).replace(microsecond=0).isoformat(),
           "note": "제목·링크·게시시각만 저장(본문 없음). 구글뉴스 대체분은 원 매체 기사의 제목이 '제목 - 매체' 꼴일 수 있음.", "sources": res}
    json.dump(obj, open(OUT, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=1)
    print({k: (v["status"], v.get("via"), len(v["items"])) for k, v in res.items()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
