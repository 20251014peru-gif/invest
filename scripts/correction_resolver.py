# v 20260915-WaveA  correction_resolver.py — 정정/철회/조건확정 → 원 Event 연결.
# 휴리스틱만으로 자동 병합하지 않는다. 명시적 연결키 있으면 CONFIRMED, 없으면 CANDIDATE(병합 X).
NON_ORIGINAL = {"CORRECTION", "ATTACHMENT_CORRECTION", "TERMS_FINAL", "WITHDRAWAL"}

def _key(dt, no):
    return (str(dt), str(no))

def resolve(events):
    originals = [e for e in events if e["version_type"] == "ORIGINAL"]
    for ev in events:
        if ev["version_type"] not in NON_ORIGINAL:
            continue
        me_no = ev["versions"][0]["rcept_no"]; me_dt = ev["versions"][0]["rcept_dt"]
        explicit = ev.get("explicit_parent_rcept")
        if explicit:
            parent = next((o for o in originals if o["versions"][0]["rcept_no"] == explicit), None)
            if parent:
                parent["versions"].append({"rcept_no": me_no, "version_type": ev["version_type"],
                                           "rcept_dt": me_dt, "url": ev["versions"][0]["url"]})
                parent["last_updated"] = me_dt
                ev["link_status"] = "CONFIRMED"; ev["parent_event_id"] = parent["event_id"]
                ev["link_note"] = "명시적 연결키(원문 rcept)로 병합"
                continue
        prior = [o for o in originals
                 if o["stock_code"] == ev["stock_code"] and o["type"] == ev["type"]
                 and _key(o["versions"][0]["rcept_dt"], o["versions"][0]["rcept_no"]) < _key(me_dt, me_no)]
        if not prior:
            ev["link_status"] = "CANDIDATE"; ev["candidate_parent_event_id"] = None
            ev["link_confidence"] = "LOW"
            ev["link_note"] = "원공시 미발견(수집 윈도우 밖일 수 있음) — 별도 Event 로 보존"
            ev["unknowns"].append("원공시 rcept")
            continue
        prior.sort(key=lambda o: _key(o["versions"][0]["rcept_dt"], o["versions"][0]["rcept_no"]))
        parent = prior[-1]
        same_day = parent["versions"][0]["rcept_dt"] == me_dt
        ev["link_status"] = "CANDIDATE"
        ev["candidate_parent_event_id"] = parent["event_id"]
        ev["link_confidence"] = "MEDIUM"
        ev["link_note"] = f"직전 원공시 후보(같은날={same_day}, 후보수={len(prior)}) — 자동 병합 안 함, 검토 필요"
    return events
