# v 20260913-objective — 매크로 시간정보를 '확인된 사실'만으로 표준화한다.
# 원칙:
# 1) 수집 주기와 원자료 발표 주기를 분리한다.
# 2) 다음 발표일은 공식 일정이 출처 URL과 함께 검증된 경우에만 표시한다.
# 3) 임의 stale 기준, 주기 기반 추정일, 보간 날짜를 만들지 않는다.
# 4) 판단 대신 객관값(as_of, collected_at, age_days, source)을 제공한다.
import json, os, datetime as dt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
KST = dt.timezone(dt.timedelta(hours=9))

FREQ = {
    "D": "일간", "W": "주간", "M": "월간", "Q": "분기", "A": "연간",
    "weekday": "영업일", "daily": "일간", "weekly": "주간", "monthly": "월간", "quarterly": "분기"
}

def load(path, default):
    try:
        with open(path, encoding="utf-8") as f: return json.load(f)
    except Exception: return default

def save(path, obj):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def parse_exact_date(s):
    """정확한 YYYY-MM-DD만 날짜 나이 계산에 사용한다. 월/연 자료에 임의 말일을 붙이지 않는다."""
    s = str(s or "").strip()
    try:
        if len(s) >= 10 and s[4] == "-" and s[7] == "-":
            return dt.date.fromisoformat(s[:10])
    except Exception:
        pass
    return None

def official_event_map(cal):
    """공식 검증 플래그 + 출처 URL + 날짜가 모두 있는 일정만 채택한다."""
    out = {}
    for e in cal.get("upcoming", []):
        verified = e.get("verified_official") is True or e.get("evidence") == "official"
        if not verified or not e.get("id") or not e.get("date") or not e.get("url"):
            continue
        out.setdefault(e["id"], e)
    return out

def main():
    path = P("facts", "macro.json")
    doc = load(path, {})
    view = load(P("data", "macro_view.json"), {}).get("items", {})
    cal = load(P("analysis", "calendar.json"), {})
    official = official_event_map(cal)

    today = dt.datetime.now(KST).date()
    counts = {"today": 0, "available": 0, "scheduled": 0, "error": 0, "pending": 0, "unknown": 0}

    for r in doc.get("items", []):
        m = view.get(r.get("id"), {})
        cycle = r.get("cycle") or m.get("cycle") or ""
        r["frequency"] = m.get("frequency") or FREQ.get(cycle, cycle or "미확인")

        ev = official.get(r.get("id"))
        if ev:
            time_part = (" " + ev.get("time", "").strip()) if ev.get("time") else ""
            r["next_update"] = {
                "date": ev["date"],
                "time": ev.get("time", ""),
                "label": f"{ev['date']}{time_part}",
                "verified": True,
                "source": ev["url"]
            }
        else:
            r["next_update"] = {
                "date": "", "time": "", "label": "공식 일정 미확인",
                "verified": False, "source": ""
            }

        exact_date = parse_exact_date(r.get("as_of"))
        r["age_days"] = (today - exact_date).days if exact_date else None

        if r.get("error"):
            state = "error"
        elif r.get("pending"):
            state = "pending"
        elif ev and ev.get("date") > today.isoformat():
            state = "scheduled"
        elif exact_date == today:
            state = "today"
        elif r.get("value") is not None and r.get("as_of"):
            state = "available"
        else:
            state = "unknown"
        r["freshness"] = state
        counts[state] = counts.get(state, 0) + 1

    doc["time_meta"] = {
        "schema": "macro_time/2",
        "policy": "objective_only",
        "computed_at": dt.datetime.now(KST).replace(microsecond=0).isoformat(),
        "collector_schedule": "매시 05분",
        "collector_interval": "1시간",
        "note": "다음 발표일은 verified_official/evidence=official + 출처 URL이 있는 일정만 표시. 그 외는 '공식 일정 미확인'. 임의 추정·보간·stale 임계값 없음.",
        "status_counts": counts
    }
    save(path, doc)
    print("macro objective time metadata:", counts)

if __name__ == "__main__":
    main()
