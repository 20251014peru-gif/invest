# v 20260906-0100  board.py — sectors.json 종목의 네이버 종목토론실을 긁어 '근거 있는 주장'만 골라 facts/board.json + (선택)알림.
# 읽기: data/sectors.json(회사 code)   쓰기: facts/board.json, data/status.json(job board)
# 방식: 토론실 목록 HTML 파싱 → 새 글만 골라 → LLM(haiku) 한 번에 배치로 노이즈 제거 → 근거글만 저장.
# 규칙: ANTHROPIC_API_KEY·NTFY_TOPIC·RELAY_URL 은 GitHub Secret. 실패는 소리를 낸다(철칙 4). load() 하드닝.
# 정직: 토론실 글은 검증 안 된 '주장 후보'다. LLM 은 '근거 있어 보이는지'만 거른다 — 사실 여부는 판단 못 한다(판단은 달님).
import json, os, re, sys, html, datetime as dt, urllib.request, urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
KST = dt.timezone(dt.timedelta(hours=9))
def kst_now(): return dt.datetime.now(KST)
def kst_iso(d=None): return (d or kst_now()).replace(microsecond=0).isoformat()

KEY     = os.environ.get("ANTHROPIC_API_KEY", "").strip()
RELAY   = os.environ.get("RELAY_URL", "").strip()          # 있으면 CORS/IP차단 우회용 프록시로 경유
MODEL   = os.environ.get("BOARD_MODEL", "claude-haiku-4-5-20251001").strip()
TOPIC   = os.environ.get("NTFY_TOPIC", "").strip()
MAX_CO      = int(os.environ.get("BOARD_MAX_CO", "40"))     # 이번 실행에서 훑을 회사 수 상한(비용/시간)
POSTS_PER   = int(os.environ.get("BOARD_POSTS_PER", "20"))  # 회사당 최근 글 상한
NEW_LIMIT   = int(os.environ.get("BOARD_NEW_LIMIT", "120")) # 한 번에 LLM 에 보낼 새 글 총 상한
KEEP_DAYS   = int(os.environ.get("BOARD_KEEP_DAYS", "90"))  # 근거글 보관 일수(분기 주장까지 검증 가능하게 길게)
SEEN_DAYS   = int(os.environ.get("BOARD_SEEN_DAYS", "21"))  # 이미 본 글 nid 기억 일수(노이즈 재분석 방지=비용)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"


def load(p, d):
    try:
        with open(p, encoding="utf-8") as f: return json.load(f)
    except FileNotFoundError: return d
    except (json.JSONDecodeError, ValueError):
        print(f"[경고] {p} JSON 손상 — 기본값으로 진행(자동 복구)"); return d

def save(p, o):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f: json.dump(o, f, ensure_ascii=False, indent=2)


def _fetch_raw(url, timeout=20):
    """네이버 금융은 EUC-KR + 봇 IP 차단 잦음. RELAY 있으면 경유. 바이트 그대로 받아 cp949 우선 디코드."""
    target = (RELAY + urllib.parse.quote(url, safe="")) if RELAY else url
    req = urllib.request.Request(target, headers={"User-Agent": UA, "Referer": "https://finance.naver.com/"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        ct = (r.headers.get("Content-Type") or "").lower()
    if "utf-8" in ct or "utf8" in ct:
        return raw.decode("utf-8", errors="replace")
    try:
        return raw.decode("euc-kr")
    except UnicodeDecodeError:
        return raw.decode("utf-8", errors="replace")


# 토론실 목록 행: board_read.naver?...&nid=NNNN... 링크의 제목 + 조회/공감/비공감 숫자
_ROW = re.compile(
    r'board_read\.naver\?[^"\']*?nid=(\d+)[^"\']*?["\'][^>]*>(.*?)</a>', re.S)
_TAGS = re.compile(r"<[^>]+>")

def _clean(t):
    t = _TAGS.sub("", t)
    t = html.unescape(t)
    return re.sub(r"\s+", " ", t).strip()

def fetch_board(code):
    """한 종목 토론실 1페이지 → [{nid, title}] (최근 글 위주). 실패하면 빈 리스트(수집은 계속)."""
    url = f"https://finance.naver.com/item/board.naver?code={code}"
    try:
        htmltext = _fetch_raw(url)
    except Exception as e:
        print(f"  · {code} 목록 실패: {type(e).__name__}"); return []
    seen, out = set(), []
    for m in _ROW.finditer(htmltext):
        nid = m.group(1)
        if nid in seen: continue
        seen.add(nid)
        title = _clean(m.group(2))
        if not title or len(title) < 4: continue
        out.append({"nid": nid, "title": title})
        if len(out) >= POSTS_PER: break
    return out


PROMPT = (
    "너는 한국 주식 종목토론실 글 제목을 거르는 필터다. 대부분은 감정·욕설·근거 없는 뇌피셜·도배·홍보 노이즈다.\n"
    "아래 글 목록에서 '구체적 근거(수치·계약·공시·실적·기관 수급·일정 등)를 대는 주장'만 골라라.\n"
    "확인된 사실인지 여부는 판단하지 말고, '근거를 제시하려는 진지한 글인지'만 본다. 단순 응원·비난·질문·예측 감정글은 버린다.\n"
    "각 글에 topic(핵심 한 줄 요약, 한국어), why(왜 근거글로 골랐는지 15자 내), strength(상/중/하),\n"
    "when(주장이 가리키는 시점·기한. 예: '3분기','연내','다음 실적','2027'. 시점 없으면 빈 문자열)을 붙인다.\n"
    '반드시 JSON 만: {"keep":[{"i":정수인덱스,"topic":"...","why":"...","strength":"상|중|하","when":"..."}]}. 고를 게 없으면 keep:[].\n'
    "글 목록(인덱스: [종목] 제목):\n")

def call_claude(posts):
    """posts: [{i, code, company, title, nid}] → LLM 이 고른 인덱스 집합 dict{i: {topic,why,strength}}."""
    if not posts: return {}
    lines = "\n".join(f'{p["i"]}: [{p["company"]}] {p["title"]}' for p in posts)
    body = json.dumps({
        "model": MODEL, "max_tokens": 2000, "temperature": 0,
        "messages": [{"role": "user", "content": PROMPT + lines}]}).encode("utf-8")
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, headers={
        "content-type": "application/json", "x-api-key": KEY, "anthropic-version": "2023-06-01"})
    with urllib.request.urlopen(req, timeout=90) as r:
        resp = json.loads(r.read().decode("utf-8"))
    txt = "".join(b.get("text", "") for b in resp.get("content", []) if b.get("type") == "text")
    mo = re.search(r"\{.*\}", txt, re.S)
    if not mo: return {}
    try:
        keep = json.loads(mo.group(0)).get("keep", [])
    except (json.JSONDecodeError, ValueError):
        return {}
    out = {}
    for k in keep:
        try: out[int(k["i"])] = {"topic": str(k.get("topic", ""))[:120],
                                 "why": str(k.get("why", ""))[:40],
                                 "strength": k.get("strength", "중"),
                                 "when": str(k.get("when", ""))[:30]}
        except (ValueError, TypeError, KeyError): pass
    return out


def set_status(status, note="", cause="", fix=""):
    stj = load(P("data", "status.json"), {"schema": "status/1", "jobs": []})
    job = {"id": "board", "name": "토론실 근거", "status": status, "ran": kst_iso(),
           "due": kst_iso(kst_now() + dt.timedelta(hours=14)) if status == "ok" else "",
           "cause": cause, "fix": fix, "link": "cygnus.html#board", "note": note}
    stj["jobs"] = [j for j in stj.get("jobs", []) if j.get("id") != "board"] + [job]
    stj["updated"] = kst_iso(); save(P("data", "status.json"), stj)


def run():
    if not KEY:
        set_status("stopped", note="ANTHROPIC_API_KEY 미설정",
                   cause="ANTHROPIC_API_KEY 없음", fix="GitHub Secret 에 ANTHROPIC_API_KEY 등록하면 자동 분석")
        print("ANTHROPIC_API_KEY 없음 — 토론실 분석 건너뜀(정상 종료, 알림 없음)"); return 0

    sec = load(P("data", "sectors.json"), {"sectors": []})
    cos = []
    for s in sec.get("sectors", []):
        for c in s.get("companies", []):
            code = (c.get("code") or "").strip()
            if code.isdigit() and len(code) == 6:
                cos.append({"code": code, "company": c["name"], "sector": s["name"]})
    cos = cos[:MAX_CO]

    prevj = load(P("facts", "board.json"), {"items": [], "seen": {}})
    now_iso = kst_iso()
    # 이미 본 글(채택 여부 무관)은 다시 LLM 에 안 보낸다 → 노이즈 재분석 비용 0
    seen = dict(prevj.get("seen", {}))
    seen_nid = set(seen) | {i["nid"] for i in prevj.get("items", [])}

    # 1) 목록 수집 → 새 글만
    fresh, idx = [], 0
    for co in cos:
        for post in fetch_board(co["code"]):
            if post["nid"] in seen_nid: continue
            seen_nid.add(post["nid"]); seen[post["nid"]] = now_iso
            fresh.append({"i": idx, "code": co["code"], "company": co["company"],
                          "sector": co["sector"], "nid": post["nid"], "title": post["title"]})
            idx += 1
            if len(fresh) >= NEW_LIMIT: break
        if len(fresh) >= NEW_LIMIT: break

    # 2) LLM 필터 (새 글 있을 때만 = 비용 절감)
    kept_new = []
    if fresh:
        try:
            picks = call_claude(fresh)
        except Exception as e:
            set_status("fail", cause=f"LLM 호출 실패: {type(e).__name__}: {e}"[:300],
                       fix="ANTHROPIC_API_KEY·모델명 확인 · Actions 로그")
            print(f"LLM 호출 실패: {type(e).__name__}: {e}"); raise
        for p in fresh:
            info = picks.get(p["i"])
            if not info: continue
            kept_new.append({"nid": p["nid"], "code": p["code"], "company": p["company"], "sector": p["sector"],
                             "title": p["title"], "topic": info["topic"], "why": info["why"],
                             "strength": info["strength"], "when": info.get("when", ""),
                             "url": f"https://finance.naver.com/item/board_read.naver?code={p['code']}&nid={p['nid']}",
                             "found": kst_iso(),
                             # 검증 루프용(지금은 비워둠. 나중에 dart.json·실적과 대조해 채운다): 미검증→적중/빗나감/무관
                             "verify": {"status": "미검증", "note": "", "date": ""}})

    # 3) 병합 + 오래된 근거글 정리(보관일 초과) + 중복 nid 제거
    cutoff = (kst_now() - dt.timedelta(days=KEEP_DAYS)).isoformat()
    merged, keep_nid = [], set()
    for it in kept_new + prevj.get("items", []):
        if it["nid"] in keep_nid: continue
        if it.get("found", "") and it["found"] < cutoff: continue
        it.setdefault("when", ""); it.setdefault("verify", {"status": "미검증", "note": "", "date": ""})  # 옛 글 소급 필드
        keep_nid.add(it["nid"]); merged.append(it)
    merged.sort(key=lambda x: x.get("found", ""), reverse=True)

    # seen 정리(오래된 nid 는 잊어 파일 비대화 방지)
    seen_cut = (kst_now() - dt.timedelta(days=SEEN_DAYS)).isoformat()
    seen = {n: t for n, t in seen.items() if t >= seen_cut}

    save(P("facts", "board.json"), {
        "schema": "board/1", "version": "v 20260906-0100", "updated": now_iso,
        "_정직": "검증 안 된 '주장 후보'. LLM 은 근거를 대려는 글인지만 걸렀을 뿐, 사실 여부는 판단 못 함. 판단은 달님.",
        "scanned_companies": len(cos), "new_posts": len(fresh), "new_kept": len(kept_new),
        "count": len(merged), "items": merged, "seen": seen})
    set_status("ok", note=f"훑음 {len(cos)}종목 · 새 글 {len(fresh)} · 근거글 +{len(kept_new)}(누적 {len(merged)})")
    print(f"토론실: {len(cos)}종목 훑음, 새 글 {len(fresh)}건, 근거글 +{len(kept_new)}(누적 {len(merged)})")

    # 4) 하루 한 통 — 그날 새로 걸러진 근거글을 강도순(상>중>하)으로 묶어 한 번만 알림.
    rank = {"상": 0, "중": 1, "하": 2}
    digest = sorted(kept_new, key=lambda k: rank.get(k["strength"], 3))
    if digest and TOPIC:
        emo = {"상": "🔴", "중": "🟡", "하": "⚪"}
        body = "\n\n".join(f"{emo.get(k['strength'],'')} [{k['sector']}] {k['company']} · {k['topic']}\n{k['url']}" for k in digest[:12])
        n_strong = sum(1 for k in digest if k["strength"] == "상")
        h = lambda v: v.encode("utf-8").decode("latin-1")
        try:
            r = urllib.request.urlopen(urllib.request.Request("https://ntfy.sh/" + TOPIC, data=body.encode("utf-8"),
                headers={"Title": h(f"[토론실] 오늘 근거글 {len(digest)}건(미검증·상 {n_strong})"), "Priority": "3",
                         "Click": "https://20251014peru-gif.github.io/invest/cygnus.html#board"}), timeout=10)
            print(f"ntfy OK (HTTP {r.status}) · 다이제스트 {len(digest)}건(상 {n_strong}) · 토픽 끝4자리=…{TOPIC[-4:]}")
        except Exception as e:
            print(f"ntfy 실패: {type(e).__name__}: {e}")
    elif not digest:
        print("오늘 새 근거글 없음 — 알림 생략")
    return len(merged)


if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        set_status("fail", cause=f"{type(e).__name__}: {e}"[:300], fix="Actions 로그 · Secret 확인")
        raise
