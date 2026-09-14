# v 20260915-WaveC1 dart.py — DART Collector 유지 + Event Engine/ntfy 연결.
# 기존 facts/dart.json 호환은 유지하고, 신규 판단/알림은 Event Engine만 담당한다.
import json, os, datetime as dt, urllib.request, urllib.parse
import event_runtime as ER
import event_notifier as EN

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
    except (json.JSONDecodeError, ValueError):
        print(f"[경고] {p} JSON 손상 — 기본값으로 진행(자동 복구)"); return d

def save(p, o):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f: json.dump(o, f, ensure_ascii=False, indent=2)

# 구형 화면 호환용 표시값. 알림/중대성 판정에는 사용하지 않는다.
def kind_of(nm):
    if any(k in nm for k in ["공급계약", "수주", "단일판매"]): return "수주"
    if any(k in nm for k in ["잠정", "영업(잠정)", "실적"]): return "실적"
    if any(k in nm for k in ["유상증자", "전환사채", "신주인수권", "교환사채"]): return "증자"
    if "자기주식" in nm: return "자사주"
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
    codes = {}
    for s in sec.get("sectors", []):
        for c in s.get("companies", []):
            code = (c.get("code") or "").strip()
            if code and code.isdigit() and len(code) == 6:
                codes[code] = {"sector": s["name"], "company": c["name"]}

    end = kst_now().date(); bgn = end - dt.timedelta(days=DAYS)
    bgn_s, end_s = bgn.strftime("%Y%m%d"), end.strftime("%Y%m%d")
    items, seen = [], set(); page, pages = 1, 1
    while page <= pages and page <= 20:
        d = fetch_list(bgn_s, end_s, page); st = str(d.get("status"))
        if st == "013": break
        if st != "000": raise RuntimeError(f"DART status {st}: {d.get('message')}")
        pages = int(d.get("total_page", 1))
        for it in d.get("list", []):
            sc = (it.get("stock_code") or "").strip()
            if sc not in codes: continue
            no = it.get("rcept_no", "")
            if no in seen: continue
            seen.add(no); nm = it.get("report_nm", "")
            items.append({"stock_code": sc, "company": codes[sc]["company"], "sector": codes[sc]["sector"],
                          "report_nm": nm, "kind": kind_of(nm), "flr": it.get("flr_nm", ""),
                          "rcept_dt": it.get("rcept_dt", ""), "rcept_no": no,
                          "url": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=" + no})
        page += 1
    items.sort(key=lambda x: (x["rcept_dt"], x["rcept_no"]), reverse=True)

    # legacy snapshot은 유지한다. 이 kind 값은 화면 호환용일 뿐 알림에는 쓰지 않는다.
    save(P("facts", "dart.json"), {"schema": "dart/1", "version": "v 20260915-WaveC1", "updated": kst_iso(),
        "range": f"{bgn_s}~{end_s}", "count": len(items), "items": items})

    # 신규/미해결 Event만 상세조회. 정정 오탐·중대성·Risk Gate는 여기서 처리한다.
    er = ER.process(items, KEY)
    alert_events = er.get("new_events", []) + er.get("material_updates", [])
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    notify = EN.send(topic, alert_events)
    if notify.get("sent"):
        print(f"Event ntfy 전송 OK · {notify.get('count',0)}건")
    elif alert_events:
        print(f"Event ntfy 미전송 · {notify.get('reason')} · 후보 {len(alert_events)}건")

    stj = load(P("data", "status.json"), {"schema": "status/1", "jobs": []})
    job = {"id": "dart", "name": "공시 수집", "status": "ok", "ran": kst_iso(),
           "due": kst_iso(kst_now() + dt.timedelta(hours=30)), "cause": "", "fix": "", "link": "cygnus.html#sectors",
           "note": f"{len(items)}건({DAYS}일) · 신규 Event {len(er.get('new_events',[]))} · 중대성갱신 {len(er.get('material_updates',[]))} · push {notify.get('count',0)}"}
    stj["jobs"] = [j for j in stj.get("jobs", []) if j.get("id") != "dart"] + [job]
    stj["updated"] = kst_iso(); save(P("data", "status.json"), stj)
    print(f"공시 {len(items)}건 · Event index {er.get('index_count')} · 신규 {len(er.get('new_events',[]))} · 중대성갱신 {len(er.get('material_updates',[]))}")
    return len(items)

def fail(msg):
    stj = load(P("data", "status.json"), {"schema": "status/1", "jobs": []})
    stj["jobs"] = [j for j in stj.get("jobs", []) if j.get("id") != "dart"] + [{"id": "dart", "name": "공시 수집",
        "status": "fail", "ran": kst_iso(), "due": "", "cause": msg[:300], "fix": "DART_API_KEY Secret 확인 · Event Engine · Actions 로그", "link": "cygnus.html#sectors"}]
    stj["updated"] = kst_iso(); save(P("data", "status.json"), stj)

if __name__ == "__main__":
    try: run()
    except Exception as e:
        fail(f"{type(e).__name__}: {e}"); raise
