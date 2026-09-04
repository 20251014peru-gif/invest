# v 20260904-1530  score.py — 오픈북 전방 채점 엔진(원칙 15). 검증엔진 v4.3 의 judge_prediction 을 옮겨온 것.
# 읽기: raw/predictions.json  → 쓰기: analysis/scores.json, facts/source_trust.json, data/status.json(job score)
# 출처를 가리지 않는다: 유튜브 채널 예측·달님 본인 예측·전략 카드 신호 전부 같은 규격(predictions/1)으로 채점.
# 규칙: 기한(due)이 지난 pending 만 채점. ±2% 이내는 판정불가. 근거 없으면 판정불가 — 절대 추측으로 채우지 않는다.
import json, os, sys, datetime as dt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
KST = dt.timezone(dt.timedelta(hours=9))
def kst_now(): return dt.datetime.now(KST)
def kst_iso(d=None): return (d or kst_now()).replace(microsecond=0).isoformat()
THRESH = 2.0   # % — 검증엔진 v4.3 과 같은 값(추정치, 오픈북 결과 보고 조정)

def load(p, default):
    try:
        with open(p, encoding="utf-8") as f: return json.load(f)
    except FileNotFoundError: return default

def save(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f: json.dump(obj, f, ensure_ascii=False, indent=2)

def price_change(ticker, made_at, due, fetch=None):
    """기준가 = 발표일 이후 첫 종가, 판정가 = 기한일 이전 마지막 종가. 실패 → None (판정불가)."""
    fetch = fetch or _yf_history
    try:
        base = dt.date.fromisoformat(made_at[:10]); end = dt.date.fromisoformat(due[:10])
        closes = fetch(ticker, base - dt.timedelta(days=7), end + dt.timedelta(days=1))  # [(date, close)] 오름차순
        after = [c for d, c in closes if d >= base]
        upto = [c for d, c in closes if d <= end]
        if not after or not upto: return None
        b, e = float(after[0]), float(upto[-1])
        return {"base": round(b, 2), "final": round(e, 2), "change_pct": round((e - b) / b * 100, 2)}
    except Exception as ex:
        return None

def _yf_history(ticker, start, end):
    import yfinance as yf
    h = yf.Ticker(ticker).history(start=start.isoformat(), end=end.isoformat(), auto_adjust=False)
    if h is None or len(h) == 0: return []
    return [(idx.to_pydatetime().date(), float(v)) for idx, v in h["Close"].dropna().items()]

def judge(pred, fetch=None):
    """예측 1건 → (status, basis). 검증엔진 judge_prediction 과 같은 규칙."""
    t = (pred.get("ticker") or "").strip(); d = (pred.get("direction") or "").strip()
    if not t: return "판정불가", "티커 없음 — 수동 판정 필요"
    up, down = d in ("상승", "돌파"), d in ("하락", "하회")
    if not (up or down): return "판정불가", "방향 모호(상승·하락·돌파·하회만 채점)"
    px = price_change(t, pred.get("made_at", ""), pred.get("due", ""), fetch)
    if not px: return "판정불가", f"{t} 주가 조회 실패(티커 확인 또는 수동 판정)"
    c = px["change_pct"]; basis = f"{t} 기준 {px['base']} → 기한 {px['final']} ({c:+.1f}%)"
    if abs(c) < THRESH: return "판정불가", basis + f" · 변화 미미(±{THRESH:g}% 이내)"
    return ("적중" if (up and c >= THRESH) or (down and c <= -THRESH) else "빗나감"), basis

def run(fetch=None, today=None):
    today = today or kst_now().date()
    src = load(P("raw", "predictions.json"), {"schema": "predictions/1", "items": []})
    if src.get("schema") != "predictions/1": raise SystemExit("raw/predictions.json 규격이 predictions/1 이 아닙니다")
    scores = load(P("analysis", "scores.json"), {"schema": "scores/1", "items": []})
    done = {s["id"]: s for s in scores["items"]}
    new = 0
    for p in src["items"]:
        if p.get("status", "pending") != "pending" or p["id"] in done: continue
        if not p.get("due") or dt.date.fromisoformat(p["due"][:10]) > today: continue
        status, basis = judge(p, fetch)
        done[p["id"]] = {"id": p["id"], "source": p.get("source", {}), "ticker": p.get("ticker"), "direction": p.get("direction"),
                         "made_at": p.get("made_at"), "due": p.get("due"), "status": status, "basis": basis,
                         "scored_at": kst_iso(), "rules_version": "score/1 ±%g%%" % THRESH}
        new += 1
    scores["items"] = sorted(done.values(), key=lambda s: s.get("due", ""), reverse=True)
    scores["updated"] = kst_iso(); scores["version"] = "v 20260904-1530"
    save(P("analysis", "scores.json"), scores)

    # 출처별 신뢰도(적중률) — 검증엔진 대시보드에서 '종합점수'는 버리고(원칙 14) 적중률·건수만 남긴다
    trust = {}
    for s in scores["items"]:
        key = (s.get("source") or {}).get("name") or "미상"
        t = trust.setdefault(key, {"name": key, "type": (s.get("source") or {}).get("type", ""), "hit": 0, "miss": 0, "na": 0})
        t["hit" if s["status"] == "적중" else "miss" if s["status"] == "빗나감" else "na"] += 1
    rows = []
    for t in trust.values():
        n = t["hit"] + t["miss"]; t["decided"] = n; t["hit_rate"] = round(t["hit"] / n * 100) if n else None
        t["comment"] = "데이터 부족(판정 2건 미만)" if n < 2 else ("적중률 높음" if t["hit_rate"] >= 60 else "보통" if t["hit_rate"] >= 45 else "적중률 낮음")
        rows.append(t)
    rows.sort(key=lambda r: (-(r["hit_rate"] or -1), -r["decided"]))
    pending = sum(1 for p in src["items"] if p.get("status", "pending") == "pending" and p["id"] not in done)
    save(P("facts", "source_trust.json"), {"schema": "source_trust/1", "version": "v 20260904-1530", "updated": kst_iso(),
                                          "rule": "적중률 = 적중/(적중+빗나감). 판정불가는 분모에서 제외. 2건 미만은 판단 보류", "sources": rows})
    # status.json 갱신(철칙 4)
    st = load(P("data", "status.json"), {"schema": "status/1", "jobs": []})
    jobs = [j for j in st.get("jobs", []) if j.get("id") != "score"]
    jobs.append({"id": "score", "name": "오픈북 채점", "status": "ok", "ran": kst_iso(),
                 "due": kst_iso(kst_now() + dt.timedelta(hours=36)), "cause": "", "fix": "",
                 "link": "predict.html", "note": f"새로 채점 {new}건 · 대기 {pending}건"})
    st["jobs"] = jobs; st["updated"] = kst_iso(); save(P("data", "status.json"), st)
    print(f"채점 {new}건, 대기 {pending}건, 출처 {len(rows)}곳")
    return new

def fail(msg):
    st = load(P("data", "status.json"), {"schema": "status/1", "jobs": []})
    st["jobs"] = [j for j in st.get("jobs", []) if j.get("id") != "score"] + [{"id": "score", "name": "오픈북 채점", "status": "fail",
        "ran": kst_iso(), "due": "", "cause": msg[:300], "fix": "Actions 로그 확인 → 🐞 [복사] 로 Claude 에게", "link": "predict.html"}]
    st["updated"] = kst_iso(); save(P("data", "status.json"), st)

if __name__ == "__main__":
    try: run()
    except Exception as e:
        fail(f"{type(e).__name__}: {e}"); raise
