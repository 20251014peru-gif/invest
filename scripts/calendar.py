# v 20260907-2300  calendar.py — 발표 달력. 읽기: data/reports.json(발표 규칙) · raw/report_log.json(기록) · raw/manual_macro.json(수동 지표) · facts/macro.json
# 쓰기: analysis/calendar.json(calendar/1: 앞으로 14일 발표·오늘·미입력) · facts/calendar_sent.json(알림 중복 방지) · data/status.json(job calendar)
# 알림: 오늘 발표가 있으면 ntfy 1회(NTFY_TOPIC 환경변수, 없으면 생략). 미입력이 3일 넘으면 status 경고. 날짜 규칙은 '대개 그때'(추정) — 정확한 일정은 기관 일정표.
import json, os, sys, datetime as dt, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
KST = dt.timezone(dt.timedelta(hours=9))
def now(): return dt.datetime.now(KST)
def kst_iso(): return now().replace(microsecond=0).isoformat()
def load(p, d):
    try:
        with open(p, encoding="utf-8") as f: return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, ValueError): return d
def save(p, o):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f: json.dump(o, f, ensure_ascii=False, indent=2)

def bizday(d):
    while d.weekday() >= 5: d += dt.timedelta(days=1)
    return d
def month_end(y, m):
    return (dt.date(y + (m == 12), (m % 12) + 1, 1) - dt.timedelta(days=1))
def nth_weekday(y, m, n, wd):
    d = dt.date(y, m, 1); d += dt.timedelta(days=(wd - d.weekday()) % 7); return d + dt.timedelta(days=7 * (n - 1))

def occurrences(sch, start, end):
    """규칙 → [date] (start~end 사이)"""
    out, k = [], sch.get("kind")
    if k == "manual": return out
    y, m = start.year, start.month
    for _ in range(0, 15):                                              # 최대 15개월 훑기
        if k == "month_day":
            d = dt.date(y, m, min(sch["day"], month_end(y, m).day)); d = bizday(d) if sch.get("bizday") else d; out.append(d)
        elif k == "month_end":
            out.append(month_end(y, m))
        elif k == "months":
            if m in sch["months"]: out.append(dt.date(y, m, min(sch.get("day", 15), month_end(y, m).day)))
        elif k == "nth_weekday":
            if sch.get("every"):
                d = dt.date(y, m, 1)
                while d.month == m:
                    if d.weekday() == sch["weekday"]: out.append(d)
                    d += dt.timedelta(days=1)
            else: out.append(nth_weekday(y, m, sch.get("n", 1), sch["weekday"]))
        m += 1
        if m > 12: m, y = 1, y + 1
    return sorted(set(d for d in out if start <= d <= end))

def period_for(rep, d):
    """발표일 d 가 가리키는 기준기간 라벨 — 기록(report_log.period)과 맞추는 열쇠"""
    k = rep["schedule"].get("kind")
    if k == "nth_weekday" and rep["schedule"].get("every"): return f"{d.isocalendar()[0]}-W{d.isocalendar()[1]:02d}"
    if k == "months":
        if len(rep["schedule"]["months"]) == 2: return f"{d.year}-H{1 if d.month <= 6 else 2}"
        return f"{d.year}Q{(d.month - 1) // 3 + 1}"
    if k == "month_end": return d.strftime("%Y-%m")                      # 말일 발표 = 그 달
    if k == "month_day" and rep["schedule"].get("day", 1) > 15: return d.strftime("%Y-%m")   # 21일 발표(1~20일 수출) = 그 달
    prev = (d.replace(day=1) - dt.timedelta(days=1))                      # 월초 발표 = 전달
    return prev.strftime("%Y-%m")

def run():
    cfg = load(P("data", "reports.json"), {}); reps = cfg.get("items", [])
    since = dt.date.fromisoformat(cfg.get("log_since", "2026-09-01"))   # 이 날짜 전 발표는 '미입력'으로 안 침(시스템 시작 전)
    log = load(P("raw", "report_log.json"), {"items": []}).get("items", [])
    have = {}
    for e in log: have[(e.get("id"), e.get("period"))] = e
    today = now().date(); horizon = today + dt.timedelta(days=14); back = today - dt.timedelta(days=45)
    upcoming, due_today, missing = [], [], []
    for r in reps:
        for d in occurrences(r["schedule"], back, horizon):
            per = period_for(r, d)
            row = {"id": r["id"], "name": r["name"], "tier": r.get("tier", ""), "date": d.isoformat(), "time": r["schedule"].get("time", ""), "period": per, "url": r.get("url", ""), "auto": bool(r.get("auto")), "note": r["schedule"].get("note", "")}
            if d == today: due_today.append(row)
            if today <= d <= horizon: upcoming.append(row)
            if d < today and d >= since and not r.get("auto") and not r.get("optional") and (r["id"], per) not in have:
                row2 = dict(row); row2["days_late"] = (today - d).days; missing.append(row2)
    upcoming.sort(key=lambda x: (x["date"], x["time"])); missing.sort(key=lambda x: -x["days_late"])
    # 최근 기록(보고서별 최신 1건)
    latest = {}
    for e in sorted(log, key=lambda e: (e.get("date", ""), e.get("period", ""))): latest[e.get("id")] = e
    out = {"schema": "calendar/1", "version": "v 20260907-2300", "computed_at": kst_iso(), "today": today.isoformat(),
           "due_today": due_today, "upcoming": upcoming, "missing": missing, "latest": latest,
           "_정직": "발표일은 규칙(대개 그때) 기준 추정. 기관 일정표와 다르면 data/reports.json 의 schedule 을 고친다"}
    save(P("analysis", "calendar.json"), out)
    # ntfy: 오늘 발표 있으면 하루 1회
    sent = load(P("facts", "calendar_sent.json"), {"days": {}})
    topic = os.environ.get("NTFY_TOPIC", "").strip(); note = ""
    if due_today and topic and sent["days"].get(today.isoformat()) != "sent":
        body = " · ".join(f"{x['name']} {x['time']}".strip() for x in due_today)
        try:
            req = urllib.request.Request(f"https://ntfy.sh/{topic}", data=body.encode("utf-8"), headers={"Title": "오늘 발표 " + str(len(due_today)) + "건", "Priority": "3", "Tags": "calendar"})
            urllib.request.urlopen(req, timeout=15).read(); sent["days"][today.isoformat()] = "sent"; note = "ntfy 보냄"
        except Exception as e: note = f"ntfy 실패 {type(e).__name__}"
    sent["days"] = {k: v for k, v in sent["days"].items() if k >= (today - dt.timedelta(days=30)).isoformat()}
    save(P("facts", "calendar_sent.json"), sent)
    late = [x for x in missing if x["days_late"] >= 3]
    st = load(P("data", "status.json"), {"schema": "status/1", "jobs": []})
    job = {"id": "calendar", "name": "발표 달력", "status": "stale" if late else "ok", "ran": kst_iso(), "due": (now() + dt.timedelta(hours=30)).replace(microsecond=0).isoformat(),
           "cause": ("미입력 " + ", ".join(f"{x['name']} {x['period']}" for x in late[:3])) if late else "", "fix": "manual.html 보고서 탭에서 입력" if late else "", "link": "manual.html#reports",
           "note": f"오늘 {len(due_today)}건 · 14일 내 {len(upcoming)}건 · 미입력 {len(missing)}건 {note}".strip()}
    st["jobs"] = [j for j in st.get("jobs", []) if j.get("id") != "calendar"] + [job]; st["updated"] = kst_iso()
    save(P("data", "status.json"), st)
    print(job["note"]); return out

if __name__ == "__main__":
    run()
