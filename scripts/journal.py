# v 20260907-2000  journal.py — 투자일지 자동 초안. 읽기: facts/macro.json · facts/macro_history.json · analysis/regime.json · analysis/calendar.json · raw/report_log.json · facts/dart.json · facts/board.json · data/indicators.json
# 쓰기: log/YYYY-MM-DD.json(journal_day/1, 자동 부분만 — 달님 기록은 Firestore) · log/index.json(journal_index/1, 날짜 목록)
# 원칙: 하루 한 파일, 덮어쓰되 자동 칸만. 값 없는 칸은 '없음'으로 남긴다(조용히 숨기지 않음).
import json, os, datetime as dt

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
def fmt(v, unit=""):
    if v is None: return "없음"
    s = f"{v:,.0f}" if abs(v) >= 1000 else (f"{v:.2f}".rstrip("0").rstrip("."))
    return s + (unit if unit in ("%", "%p") else (" " + unit if unit else ""))

def changed_indicators(macro, hist, ind_cfg, limit=8):
    """어제(이력 직전일) 대비 바뀐 지표. 월간은 as_of 가 바뀐 것. 변화 큰 순."""
    days = sorted(hist.get("days", {}).keys())
    prev_day = days[-2] if len(days) >= 2 else (days[-1] if days else None)
    prev = hist.get("days", {}).get(prev_day, {}) if prev_day else {}
    out = []
    for r in macro.get("items", []):
        if r.get("value") is None: continue
        pv = prev.get(r["id"]) if r.get("cycle") == "D" else r.get("prev")
        if pv in (None, 0) or pv == r["value"]: continue
        d = r["value"] - pv
        pct = d / abs(pv) * 100
        is_rate = r.get("unit") in ("%", "%p")
        out.append({"id": r["id"], "name": r["name"], "value": r["value"], "unit": r.get("unit", ""), "prev": pv,
                    "delta": round(d, 3), "delta_text": (f"{d:+.2f}%p" if is_rate else f"{pct:+.1f}%"), "judge": r.get("judge", ""),
                    "as_of": r.get("as_of", ""), "cycle": r.get("cycle", ""), "score": abs(d) if is_rate else abs(pct), "group": next((i.get("group", "") for i in ind_cfg if i["id"] == r["id"]), "")})
    out.sort(key=lambda x: -x["score"])
    return out[:limit]

def run():
    today = now().date().isoformat()
    macro = load(P("facts", "macro.json"), {"items": []}); hist = load(P("facts", "macro_history.json"), {"days": {}})
    reg = load(P("analysis", "regime.json"), {}); cal = load(P("analysis", "calendar.json"), {})
    rlog = load(P("raw", "report_log.json"), {"items": []}).get("items", []); reps = load(P("data", "reports.json"), {"items": []}).get("items", [])
    dart = load(P("facts", "dart.json"), {}); board = load(P("facts", "board.json"), {}); ind_cfg = load(P("data", "indicators.json"), {"items": []}).get("items", [])
    v = {r["id"]: r for r in macro.get("items", [])}
    g = lambda i, k="value": v.get(i, {}).get(k)
    changed = changed_indicators(macro, hist, ind_cfg)
    # 시장 상태 4칸
    cards = [
        {"key": "regime", "label": "레짐", "value": (f"{reg['growth']['verdict']}·{reg['inflation']['verdict']}" if reg.get("growth") else "없음"),
         "sub": (reg.get("quadrant", {}).get("assets") or reg.get("quadrant", {}).get("name") or "") + (f" · {reg['growth']['confidence']}" if reg.get("growth") else ""), "tone": "blue"},
        {"key": "credit_spread", "label": "신용 스프레드", "value": fmt(g("credit_spread"), "%p"), "sub": f"{g('credit_spread','judge') or '—'} · {g('credit_spread','as_of') or ''}", "tone": "yellow" if g("credit_spread", "judge") in ("주의", "위험") else "green"},
        {"key": "kospi", "label": "코스피", "value": fmt(g("kospi")), "sub": f"{fmt(g('kospi','change_pct'),'%') if g('kospi','change_pct') is not None else ''} · {g('kospi','as_of') or ''}", "tone": "red" if (g("kospi", "change_pct") or 0) < 0 else "green"},
        {"key": "us10y", "label": "미 10년물", "value": fmt(g("us10y"), "%"), "sub": f"{g('us10y','judge') or '—'} · {g('us10y','as_of') or ''}", "tone": "green"},
    ]
    # 발표
    due = cal.get("due_today", []); up = cal.get("upcoming", [])[:3]; missing = cal.get("missing", [])
    latest_reps = sorted(rlog, key=lambda e: e.get("date", ""))[-3:]
    name_of = {r["id"]: r["name"] for r in reps}
    # 공시·토론실 요약(파일 구조가 다를 수 있어 안전하게)
    dart_n = len(dart.get("items", [])) if isinstance(dart.get("items"), list) else dart.get("count", 0)
    dart_new = sum(1 for x in (dart.get("items") or []) if isinstance(x, dict) and x.get("kind") in ("수주", "공급계약"))
    board_kept = board.get("new_kept", 0); board_hit = board.get("hit", 0)
    top_board = [x for x in (board.get("items") or []) if isinstance(x, dict)][:3]
    # 오늘 5줄
    brief = [
        {"k": "레짐", "t": reg.get("one_line", "레짐 판정 없음")},
        {"k": "바뀐 것", "t": " · ".join(f"{c['name']} {fmt(c['value'], c['unit'])}({c['delta_text']})" for c in changed[:4]) or "바뀐 지표 없음"},
        {"k": "오늘 발표", "t": (" · ".join(f"{x['name']} {x.get('time','')}".strip() for x in due) or "없음") + (" · 다음 " + " · ".join(f"{x['date'][5:]} {x['name']}" for x in up) if up else "")},
        {"k": "산업·종목", "t": f"DART {dart_n}건(수주·공급계약 {dart_new}) · 토론실 근거글 +{board_kept}(적중 {board_hit})" + (" · " + " / ".join(f"{x.get('company', x.get('name',''))} {str(x.get('topic',''))[:18]}" for x in top_board) if top_board else "")},
        {"k": "미입력", "t": (" · ".join(f"{x['name']} {x['period']}" for x in missing) if missing else "없음")},
    ]
    auto_entries = [
        {"id": f"{today}/auto/brief", "time": "08:00", "who": "auto", "kind": "brief", "title": f"아침 초안 — 바뀐 지표 {len(changed)}개", "items": changed},
        {"id": f"{today}/auto/flow", "time": ((board.get("updated", "") or "")[11:16] if str(board.get("updated", "")).startswith(today) else "08:40"), "who": "auto", "kind": "flow", "title": f"공시·토론실 — 근거글 +{board_kept}, 수주·공급계약 {dart_new}", "text": " · ".join(f"{x.get('company', x.get('name',''))} \"{str(x.get('topic',''))[:30]}\"({x.get('strength','')})" for x in top_board) or "새 근거글 없음"},
        {"id": f"{today}/auto/macro", "time": (macro.get("collected_at", "") or "")[11:16] or "", "who": "auto", "kind": "macro", "title": f"지표 갱신 — {macro.get('ok', 0)}/{macro.get('total', 0)} 수집", "text": "실패: " + ", ".join(r["name"] for r in macro.get("items", []) if r.get("error")) if any(r.get("error") for r in macro.get("items", [])) else "전부 정상"},
    ]
    day = {"schema": "journal_day/1", "version": "v 20260907-2000", "date": today, "generated_at": kst_iso(),
           "brief": brief, "cards": cards, "changed": changed, "releases": {"today": due, "upcoming": up, "missing": missing,
           "latest": [{"id": e.get("id"), "name": name_of.get(e.get("id"), e.get("id")), "period": e.get("period"), "verdict": e.get("verdict"), "memo": e.get("memo", ""), "date": e.get("date")} for e in latest_reps]},
           "auto_entries": auto_entries, "_정직": "자동 초안. 달님 기록(결론·헤드라인·시나리오·보고서 판정·종목 판단)은 Firestore invest_journal/<date>, invest_records 에 있음"}
    save(P("log", f"{today}.json"), day)
    idx = load(P("log", "index.json"), {"schema": "journal_index/1", "days": []})
    days = {d["date"]: d for d in idx.get("days", []) if isinstance(d, dict)}
    days[today] = {"date": today, "generated_at": day["generated_at"], "regime": reg.get("one_line", "")[:60], "changed": len(changed)}
    idx["days"] = sorted(days.values(), key=lambda d: d["date"])[-400:]; idx["updated"] = kst_iso()
    save(P("log", "index.json"), idx)
    print(f"일지 초안 {today}: 바뀐 지표 {len(changed)} · 발표 오늘 {len(due)} · 미입력 {len(missing)}")

if __name__ == "__main__":
    run()
