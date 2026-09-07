# v 20260907-2100  regime.py — 레짐 요약 계산. 읽기: data/regime_rules.json(규칙) · facts/macro.json(값) · facts/macro_history.json(추세) · data/axes.json(4분면 자산·메모)
# 쓰기: analysis/regime.json(regime/1). 한 방향(원칙 10): facts → analysis. 근거 없으면 '판단 불가'(원칙 3). 숫자 기준은 규칙 파일에만(원칙 8).
import json, os, sys, datetime as dt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
KST = dt.timezone(dt.timedelta(hours=9))
def kst_iso(): return dt.datetime.now(KST).replace(microsecond=0).isoformat()
def load(p, default):
    try:
        with open(p, encoding="utf-8") as f: return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, ValueError): return default
def save(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f: json.dump(obj, f, ensure_ascii=False, indent=2)

def trend(hist_days, iid, days):
    """N일 전 값 대비 변화율 %. 이력 부족하면 (None, 실제 일수)"""
    ks = sorted(k for k, v in hist_days.items() if isinstance(v, dict) and v.get(iid) is not None)
    if len(ks) < 2: return None, len(ks)
    last, base = hist_days[ks[-1]][iid], None
    for k in reversed(ks):
        d = (dt.date.fromisoformat(ks[-1]) - dt.date.fromisoformat(k)).days
        base = hist_days[k][iid]
        if d >= days: break
    if base in (None, 0): return None, len(ks)
    span = (dt.date.fromisoformat(ks[-1]) - dt.date.fromisoformat(ks[0])).days
    return round((last - base) / base * 100, 2), span

def fmt(v):
    if v is None: return "없음"
    return f"{v:,.0f}" if abs(v) >= 1000 else (f"{v:.2f}".rstrip("0").rstrip("."))

def read_signal(sg, rec, hist):
    """신호 하나 → {score(+1/0/-1/None), text, official, value, as_of}. None = 값 없음"""
    out = {"id": sg["id"], "name": (rec or {}).get("name", sg["id"]), "why": sg.get("why", ""), "weight": sg.get("weight", 1),
           "official": bool((rec or {}).get("official")), "value": None, "as_of": "", "score": None, "read": "값 없음", "unit": (rec or {}).get("unit", ""),
           "cycle": (rec or {}).get("cycle", ""), "collected_at": (rec or {}).get("collected_at", "")}
    if not rec or rec.get("value") is None: return out
    v, out["value"], out["as_of"] = rec["value"], rec["value"], rec.get("as_of", "")
    k, s = sg["kind"], 0
    if k == "level":
        s = 1 if v >= sg["hi"] else (-1 if v <= sg["lo"] else 0)
        out["read"] = f"{fmt(v)}{out['unit']} → " + ("기준 위" if s > 0 else "기준 아래" if s < 0 else "중간")
    elif k == "direction":
        pv = rec.get("prev")
        if pv is None: out["read"] = f"{fmt(v)}{out['unit']} (전기 값 없어 방향 미확인)"; return out
        s = 1 if v > pv else (-1 if v < pv else 0)
        out["read"] = f"{fmt(pv)} → {fmt(v)}{out['unit']} " + ("↑" if s > 0 else "↓" if s < 0 else "동결")
    elif k == "trend":
        pct, span = trend(hist, sg["id"], sg["days"])
        if pct is None: out["read"] = f"{fmt(v)}{out['unit']} (이력 {span}일 — {sg['days']}일 추세는 이력 쌓인 뒤)"; return out
        s = 1 if pct >= sg["pct"] else (-1 if pct <= -sg["pct"] else 0)
        out["read"] = f"{span}일 {pct:+.1f}% → " + ("↑" if s > 0 else "↓" if s < 0 else "횡보")
        if span < sg["days"]: out["read"] += f" (이력 {span}일뿐, {sg['days']}일 되면 정확)"
    out["score"] = s * sg.get("sign", 1)
    return out

def judge_block(rule, recs, hist):
    sigs = [read_signal(sg, recs.get(sg["id"]), hist) for sg in rule["signals"]]
    have = [s for s in sigs if s["score"] is not None]
    score = sum(s["score"] * s["weight"] for s in have)
    n_off = sum(1 for s in have if s["official"])
    lab = rule["labels"]
    if not have: verdict, conf = "판단 불가", "판단 불가"
    else:
        verdict = lab["up"] if score >= rule["cut"]["up"] else (lab["down"] if score <= rule["cut"]["down"] else lab["flat"])
        conf = "확인" if n_off >= rule.get("need_official", 1) else "추정"
    direction = ""
    if rule.get("direction_from"):
        ups = downs = 0
        for iid in rule["direction_from"]:
            r = recs.get(iid) or {}
            if r.get("value") is not None and r.get("prev") is not None:
                ups += r["value"] > r["prev"]; downs += r["value"] < r["prev"]
        direction = "올라오는 중" if ups > downs else ("내려오는 중" if downs > ups else ("보합" if ups or downs else ""))
    return {"name": rule["name"], "verdict": verdict, "confidence": conf, "score": score, "direction": direction,
            "signals": sigs, "used": len(have), "official_used": n_off, "flip": rule.get("flip", ""),
            "reason": " · ".join(f"{s['name']} {s['read']}" for s in have) if have else "쓸 수 있는 값이 없음"}

def pct_changes(hist_days, iid, days):
    """이력에서 N일 간격 변화율 표본(%). 재검토용"""
    ks = sorted(k for k, v in hist_days.items() if isinstance(v, dict) and v.get(iid) is not None)
    out = []
    for i, k in enumerate(ks):
        d0 = dt.date.fromisoformat(k)
        for j in range(i - 1, -1, -1):
            if (d0 - dt.date.fromisoformat(ks[j])).days >= days:
                b = hist_days[ks[j]][iid]
                if b: out.append((hist_days[k][iid] - b) / b * 100)
                break
    return out, ((dt.date.fromisoformat(ks[-1]) - dt.date.fromisoformat(ks[0])).days + 1 if ks else 0)

def review(rules, hist):
    """추정 기준값 자동 재검토: 제안만 하고 규칙은 안 바꾼다(달님 판별)."""
    cfg = rules.get("review") or {}
    if not cfg: return []
    min_days = int(cfg.get("min_days", 20)); out = []
    for k in ("growth", "inflation", "liquidity"):
        for sg in rules[k]["signals"]:
            if sg.get("basis_kind") != "추정": continue
            row = {"block": rules[k]["name"], "id": sg["id"], "kind": sg["kind"], "current": "", "suggest": "", "sample": 0, "days": 0, "status": ""}
            if sg["kind"] == "trend":
                row["current"] = f"±{sg['pct']}% / {sg['days']}일"
                xs, span = pct_changes(hist, sg["id"], sg["days"]); row["sample"], row["days"] = len(xs), span
                if len(xs) < 5 or span < sg["days"] + min_days:
                    row["status"] = f"이력 부족 {span}/{sg['days'] + min_days}일"; out.append(row); continue
                m = sum(xs) / len(xs); sd = (sum((x - m) ** 2 for x in xs) / len(xs)) ** 0.5
                row["suggest"] = f"±{round(sd, 1)}% (1σ, 표본 {len(xs)})"
                row["status"] = "제안 있음" if abs(sd - sg["pct"]) >= 0.5 else "현행 유지(차이 0.5 미만)"
            elif sg["kind"] == "level":
                row["current"] = f"hi {sg['hi']} / lo {sg['lo']}"
                ks = sorted(k2 for k2, v in hist.items() if isinstance(v, dict) and v.get(sg["id"]) is not None)
                vals = sorted(hist[k2][sg["id"]] for k2 in ks); row["sample"] = len(vals)
                row["days"] = (dt.date.fromisoformat(ks[-1]) - dt.date.fromisoformat(ks[0])).days + 1 if ks else 0
                if len(vals) < min_days:
                    row["status"] = f"이력 부족 {len(vals)}/{min_days}일"; out.append(row); continue
                q = lambda p: vals[min(len(vals) - 1, int(p * len(vals)))]
                row["suggest"] = f"hi {round(q(0.75), 2)} / lo {round(q(0.25), 2)} (25·75 백분위)"
                row["status"] = "제안 있음"
            else:
                row["current"] = "방향"; row["status"] = "재검토 대상 아님"
            out.append(row)
    return out

def run():
    rules = load(P("data", "regime_rules.json"), None)
    if not rules or rules.get("schema") != "regime_rules/1": raise SystemExit("data/regime_rules.json 규격 아님")
    macro = load(P("facts", "macro.json"), {"items": []})
    hist = load(P("facts", "macro_history.json"), {"days": {}}).get("days", {})
    axes = load(P("data", "axes.json"), {})
    recs = {r["id"]: r for r in macro.get("items", []) if r.get("id")}
    g, i, l = (judge_block(rules[k], recs, hist) for k in ("growth", "inflation", "liquidity"))
    # 4분면: 성장 ↑/↓ × 물가 ↑/↓. 혼조·중립·판단불가는 '보류'
    gl, il = rules["growth"]["labels"], rules["inflation"]["labels"]
    gk = "성장↑" if g["verdict"] == gl["up"] else ("성장↓" if g["verdict"] == gl["down"] else "")
    ik = "물가↑" if i["verdict"] == il["up"] else ("물가↓" if i["verdict"] == il["down"] else "")
    qmap = (axes.get("regime") or {}).get("quadrants", {})
    if gk and ik:
        qname = gk + ik; quad = {"name": qname, "assets": qmap.get(qname, ""), "confidence": "확인" if g["confidence"] == i["confidence"] == "확인" else "추정",
                                 "note": "성장·물가 둘 다 판정이 나와 4분면 확정"}
    else:
        miss = [b["name"] for b, k in ((g, gk), (i, ik)) if not k]
        near = []
        if not gk and g["verdict"] != "판단 불가": near.append(f"성장 점수 {g['score']:+.1f}(±{rules['growth']['cut']['up']} 넘어야 확정)")
        if not ik and i["verdict"] != "판단 불가": near.append(f"물가 점수 {i['score']:+.1f}")
        quad = {"name": "보류", "assets": "", "confidence": "판단 불가", "note": " · ".join(miss) + " 이 혼조/중립이라 4분면을 정하지 않음. " + " · ".join(near)}
    ok_n = sum(1 for b in (g, i, l) if b["verdict"] != "판단 불가")
    out = {"schema": "regime/1", "version": "v 20260907-2100", "computed_at": kst_iso(), "macro_collected_at": macro.get("collected_at", ""),
           "growth": g, "inflation": i, "liquidity": l, "quadrant": quad, "review": review(rules, hist),
           "one_line": f"성장 {g['verdict']}({g['confidence']}) · 물가 {i['verdict']}{('·' + i['direction']) if i['direction'] else ''}({i['confidence']}) · 유동성 {l['verdict']}({l['confidence']}) → 4분면 {quad['name']}" + (f" → {quad['assets']} 우위" if quad["assets"] else ""),
           "memo": {"text": (axes.get("regime") or {}).get("quadrant", ""), "basis": (axes.get("regime") or {}).get("basis", ""), "as_of": (axes.get("regime") or {}).get("as_of", ""), "_tag": "축 문장(수동, Claude 초안) — 위 자동 판정과 다르면 달님이 판별"},
           "_정직": "숫자 기준값은 data/regime_rules.json 의 Claude 초안(추정). 신호 값이 없으면 그 신호는 빼고 계산하며, 공식 신호가 하나도 없으면 '추정', 아무 값도 없으면 '판단 불가'"}
    save(P("analysis", "regime.json"), out)
    # status: 세 칸 다 판단 불가면 fail(조용한 실패 금지), 아니면 ok
    st = load(P("data", "status.json"), {"schema": "status/1", "jobs": []})
    job = {"id": "regime", "name": "레짐 판정", "status": "ok" if ok_n else "fail", "ran": kst_iso(), "due": (dt.datetime.now(KST) + dt.timedelta(hours=30)).replace(microsecond=0).isoformat(),
           "cause": "" if ok_n else "성장·물가·유동성 셋 다 판단 불가 — facts/macro.json 에 값이 없음", "fix": "" if ok_n else "매크로 수집(macro.yml) 먼저 확인", "link": "axes.html", "note": out["one_line"][:120]}
    st["jobs"] = [j for j in st.get("jobs", []) if j.get("id") != "regime"] + [job]; st["updated"] = kst_iso()
    save(P("data", "status.json"), st)
    print(out["one_line"]); return out

if __name__ == "__main__":
    r = run()
    if all(r[k]["verdict"] == "판단 불가" for k in ("growth", "inflation", "liquidity")): sys.exit(1)
