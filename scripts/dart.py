# v 20260904-2330  dart.py — sectors.json 의 종목코드로 DART 최근 공시를 긁어 facts/dart.json + 알림.
# 읽기: data/sectors.json(회사 code)  쓰기: facts/dart.json, data/status.json(job dart)
# 방식: DART list.json 을 날짜범위로 페이지 순회 → 내 종목만 필터 → 키워드로 종류 분류(수주/실적/증자/자사주). 수주·공급계약은 알림.
# 규칙: DART_API_KEY 는 GitHub Secret. 공식 자료(원칙 7). 실패는 소리를 낸다(철칙 4).
import json, os, sys, datetime as dt, urllib.request, urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
KST = dt.timezone(dt.timedelta(hours=9))
def kst_now(): return dt.datetime.now(KST)
def kst_iso(d=None): return (d or kst_now()).replace(microsecond=0).isoformat()
KEY = os.environ.get("DART_API_KEY", "").strip()
DAYS = int(os.environ.get("DART_DAYS", "7"))

def load(p, d):
    try:
        with open(p, encoding="utf-8") as f: return json.load(f)
    except FileNotFoundError: return d
def save(p, o):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f: json.dump(o, f, ensure_ascii=False, indent=2)

# 공시 제목 → 종류
def kind_of(nm):
    if any(k in nm for k in ["공급계약", "수주", "단일판매"]): return "수주"
    if any(k in nm for k in ["잠정", "영업(잠정)", "실적"]): return "실적"
    if any(k in nm for k in ["유상증자", "전환사채", "신주인수권", "교환사채"]): return "증자"
    if "자기주식" in nm: return "자사주"
    if any(k in nm for k in ["단일판매·공급계약"]): return "수주"
    return "기타"

def fetch_list(bgn, end, page):
    url = "https://opendart.fss.or.kr/api/list.json?" + urllib.parse.urlencode({
        "crtfc_key": KEY, "bgn_de": bgn, "end_de": end, "page_no": page, "page_count": 100})
    with urllib.request.urlopen(url, timeout=25) as r:
        return json.loads(r.read().decode("utf-8"))

def run():
    if not KEY:
        stj = load(P("data", "status.json"), {"schema": "status/1", "jobs": []})
        stj["jobs"] = [j for j in stj.get("jobs", []) if j.get("id") != "dart"] + [{"id": "dart", "name": "공시 수집",
            "status": "stopped", "ran": kst_iso(), "due": "", "cause": "DART_API_KEY 미설정", "fix": "GitHub Secret 에 DART_API_KEY 등록하면 자동 수집", "link": "cygnus.html#sectors"}]
        stj["updated"] = kst_iso(); save(P("data", "status.json"), stj)
        print("DART_API_KEY 없음 — 공시 수집 건너뜀(정상 종료, 알림 없음)")
        return 0
    sec = load(P("data", "sectors.json"), {"sectors": []})
    codes = {}   # stock_code -> {sector, company}
    for s in sec.get("sectors", []):
        for c in s.get("companies", []):
            code = (c.get("code") or "").strip()
            if code and code.isdigit() and len(code) == 6:
                codes[code] = {"sector": s["name"], "company": c["name"]}
    end = kst_now().date(); bgn = end - dt.timedelta(days=DAYS)
    bgn_s, end_s = bgn.strftime("%Y%m%d"), end.strftime("%Y%m%d")
    items, seen = [], set()
    page, pages = 1, 1
    while page <= pages and page <= 20:
        d = fetch_list(bgn_s, end_s, page)
        st = str(d.get("status"))
        if st == "013":   # 조회된 데이터 없음
            break
        if st != "000":
            raise RuntimeError(f"DART status {st}: {d.get('message')}")
        pages = int(d.get("total_page", 1))
        for it in d.get("list", []):
            sc = (it.get("stock_code") or "").strip()
            if sc not in codes: continue
            no = it.get("rcept_no", "")
            if no in seen: continue
            seen.add(no)
            nm = it.get("report_nm", "")
            items.append({"stock_code": sc, "company": codes[sc]["company"], "sector": codes[sc]["sector"],
                          "report_nm": nm, "kind": kind_of(nm), "flr": it.get("flr_nm", ""),
                          "rcept_dt": it.get("rcept_dt", ""), "rcept_no": no,
                          "url": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=" + no})
        page += 1
    items.sort(key=lambda x: (x["rcept_dt"], x["rcept_no"]), reverse=True)
    # 새 수주 공시(직전 저장분에 없던 것) → 알림 대상
    prev = {i["rcept_no"] for i in load(P("facts", "dart.json"), {"items": []}).get("items", [])}
    new_orders = [i for i in items if i["kind"] == "수주" and i["rcept_no"] not in prev]
    save(P("facts", "dart.json"), {"schema": "dart/1", "version": "v 20260904-2330", "updated": kst_iso(),
        "range": f"{bgn_s}~{end_s}", "count": len(items), "items": items})
    # status
    stj = load(P("data", "status.json"), {"schema": "status/1", "jobs": []})
    job = {"id": "dart", "name": "공시 수집", "status": "ok", "ran": kst_iso(),
           "due": kst_iso(kst_now() + dt.timedelta(hours=30)), "cause": "", "fix": "", "link": "cygnus.html#sectors",
           "note": f"{len(items)}건({DAYS}일) · 새 수주 {len(new_orders)}건"}
    stj["jobs"] = [j for j in stj.get("jobs", []) if j.get("id") != "dart"] + [job]
    stj["updated"] = kst_iso(); save(P("data", "status.json"), stj)
    print(f"공시 {len(items)}건, 새 수주 {len(new_orders)}건")
    # 새 수주는 ntfy(있으면)
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if new_orders and topic:
        body = "\n".join(f"[{o['sector']}] {o['company']} · {o['report_nm']}" for o in new_orders[:10])
        try:
            r = urllib.request.urlopen(urllib.request.Request("https://ntfy.sh/" + topic, data=body.encode("utf-8"),
                headers={"Title": "[수주공시] 관심 종목", "Priority": "4"}), timeout=10)
            print(f"ntfy 전송 OK (HTTP {r.status}) · 토픽 끝4자리=…{topic[-4:]} · 수주 {len(new_orders)}건")
        except Exception as e:
            print(f"ntfy 전송 실패: {type(e).__name__}: {e} · 토픽 끝4자리=…{topic[-4:]}")
    elif new_orders and not topic:
        print("새 수주 있으나 NTFY_TOPIC 미설정 — 알림 생략")
    return len(items)

def fail(msg):
    stj = load(P("data", "status.json"), {"schema": "status/1", "jobs": []})
    stj["jobs"] = [j for j in stj.get("jobs", []) if j.get("id") != "dart"] + [{"id": "dart", "name": "공시 수집",
        "status": "fail", "ran": kst_iso(), "due": "", "cause": msg[:300], "fix": "DART_API_KEY Secret 확인 · Actions 로그 · 🐞[복사]", "link": "cygnus.html#sectors"}]
    stj["updated"] = kst_iso(); save(P("data", "status.json"), stj)

if __name__ == "__main__":
    try: run()
    except Exception as e:
        fail(f"{type(e).__name__}: {e}"); raise
