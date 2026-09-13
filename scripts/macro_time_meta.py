# v 20260913 — 매크로 지표의 '자료 기준일/수집시각/발표주기/다음 갱신/신선도'를 표준화한다.
# 원칙: 수집기가 매시간 돌아가는 것과 원 지표가 새로 발표되는 주기는 서로 다르다.
import json, os, datetime as dt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
KST = dt.timezone(dt.timedelta(hours=9))

FREQ = {
    "D": "일간", "W": "주간", "M": "월간", "Q": "분기", "A": "연간",
    "weekday": "영업일", "daily": "일간", "weekly": "주간", "monthly": "월간", "quarterly": "분기"
}
STALE_DAYS = {"D": 5, "W": 15, "M": 70, "Q": 140, "A": 430,
              "weekday": 5, "daily": 5, "weekly": 15, "monthly": 70, "quarterly": 140}

def load(path, default):
    try:
        with open(path, encoding="utf-8") as f: return json.load(f)
    except Exception: return default

def save(path, obj):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def parse_as_of(s):
    s = str(s or "").strip()
    try:
        if len(s) >= 10: return dt.date.fromisoformat(s[:10])
        if len(s) == 7:  # 월간 자료는 그 달 말일 기준으로 신선도를 계산
            y, m = map(int, s.split("-")); n = dt.date(y + (m == 12), 1 if m == 12 else m + 1, 1)
            return n - dt.timedelta(days=1)
        if len(s) == 4: return dt.date(int(s), 12, 31)
    except Exception: pass
    return None

def next_business_day(d):
    n = d + dt.timedelta(days=1)
    while n.weekday() >= 5: n += dt.timedelta(days=1)
    return n

def estimate_next(cycle, as_of):
    """공식 일정이 없을 때 거짓 정밀도를 피하고 '갱신 가능 시점'을 보수적으로 표현한다."""
    base = parse_as_of(as_of) or dt.datetime.now(KST).date()
    if cycle in ("D", "weekday", "daily"):
        d = next_business_day(base)
        return {"date": d.isoformat(), "label": f"다음 영업일 이후 ({d:%m/%d})", "estimated": True}
    if cycle in ("W", "weekly"):
        d = base + dt.timedelta(days=7)
        return {"date": d.isoformat(), "label": f"다음 주 발표 예상 ({d:%m/%d} 전후)", "estimated": True}
    if cycle in ("M", "monthly"):
        return {"date": "", "label": "다음 공식 월간 발표", "estimated": True}
    if cycle in ("Q", "quarterly"):
        return {"date": "", "label": "다음 공식 분기 발표", "estimated": True}
    if cycle == "A":
        return {"date": "", "label": "다음 공식 연간 발표", "estimated": True}
    return {"date": "", "label": "발표 일정 확인", "estimated": True}

def main():
    path = P("facts", "macro.json")
    doc = load(path, {})
    view = load(P("data", "macro_view.json"), {}).get("items", {})
    cal = load(P("analysis", "calendar.json"), {})
    upcoming = {}
    for e in cal.get("upcoming", []):
        if e.get("id") and e.get("date"):
            upcoming.setdefault(e["id"], e)

    today = dt.datetime.now(KST).date()
    counts = {"fresh": 0, "waiting": 0, "stale": 0, "error": 0, "pending": 0}
    for r in doc.get("items", []):
        m = view.get(r.get("id"), {})
        cycle = r.get("cycle") or m.get("cycle") or ""
        frequency = m.get("frequency") or FREQ.get(cycle, cycle or "미정")
        r["frequency"] = frequency

        exact = upcoming.get(r.get("id"))
        if exact:
            t = (" " + exact.get("time", "")) if exact.get("time") else ""
            r["next_update"] = {"date": exact["date"], "label": f"{exact['date'][5:].replace('-', '/')} {t.strip()} 공식 일정".strip(), "estimated": False, "source": exact.get("url", "")}
        else:
            r["next_update"] = estimate_next(cycle, r.get("as_of"))

        if r.get("error"):
            state = "error"
        elif r.get("pending"):
            state = "pending"
        else:
            d = parse_as_of(r.get("as_of"))
            age = (today - d).days if d else None
            r["age_days"] = age
            limit = STALE_DAYS.get(cycle, 70)
            if age is not None and age > limit:
                state = "stale"
            elif cycle in ("D", "weekday", "daily") and age is not None and age <= 1:
                state = "fresh"
            else:
                state = "waiting"
        r["freshness"] = state
        counts[state] = counts.get(state, 0) + 1

    doc["time_meta"] = {
        "schema": "macro_time/1",
        "computed_at": dt.datetime.now(KST).replace(microsecond=0).isoformat(),
        "collector_schedule": "매시 05분",
        "collector_interval": "1시간",
        "note": "next_update.estimated=true 는 공식 발표일이 아니라 주기 기반 예상. 공식 일정이 연결되면 estimated=false.",
        "freshness_counts": counts
    }
    save(path, doc)
    print("macro time metadata:", counts)

if __name__ == "__main__":
    main()
