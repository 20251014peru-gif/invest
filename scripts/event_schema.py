# v 20260915-WaveB4  event_schema.py — 3축 모델(출처/사건확정/데이터최종성) + Gate/Lock.
EVENT_SCHEMA_VERSION = "event/waveB4-1"
NEW_BUY_LABELS = ["매수","추가매수","분할매수","매수검토"]

def new_event_id(stock_code, etype, rcept_dt, rcept_no):
    import hashlib
    seed=f"{stock_code}|{etype}|{rcept_dt}|{rcept_no}"
    return f"EV-{stock_code}-{etype}-{rcept_dt}-{hashlib.sha1(seed.encode('utf-8')).hexdigest()[:10]}"

def derive_verification(claim_status, data_status):
    if claim_status=="DENIED": return "V0"
    if claim_status in ("UNCONFIRMED","WITHDRAWN","DISPUTED"): return "V1"
    if claim_status=="PARTIALLY_CONFIRMED": return "V2"
    return "V2" if data_status=="PRELIMINARY" else "V3"

def compute_gate_and_lock(source_level, claim_status, materiality_status, family):
    gate="G0"
    if source_level in ("S2","S3"): gate="G1"
    if family!="OTHER": gate="G2"
    if materiality_status not in ("NOT_RUN","PENDING",None): gate="G3"
    locked, reasons = False, []
    if claim_status in ("UNCONFIRMED","DENIED","DISPUTED","WITHDRAWN"):
        locked=True; reasons.append(f"claim {claim_status}")
    if materiality_status in ("UNKNOWN","NOT_RUN","CONFLICT",None):
        locked=True; reasons.append(f"중대성 {materiality_status or 'NOT_RUN'}")
    if gate!="G6":
        locked=True; reasons.append(f"{gate} < G6")
    return gate, locked, list(dict.fromkeys(reasons))

def build_event(*, stock_code, company, sector, raw_title, norm_title, tokens,
                family, etype, version_type, channel, urgency,
                source_level, claim_status, data_status,
                rcept_no, rcept_dt, url, risk_class=None):
    materiality_status = "NOT_RUN"
    verification = derive_verification(claim_status, data_status)
    gate, locked, reasons = compute_gate_and_lock(source_level, claim_status, materiality_status, family)
    return {
        "schema": EVENT_SCHEMA_VERSION,
        "event_id": new_event_id(stock_code, etype, rcept_dt, rcept_no),
        "stock_code": stock_code, "corp_code": None, "company": company, "sector": sector,
        "family": family, "type": etype, "version_type": version_type, "disclosure_channel": channel,
        "status": "OPEN", "urgency": urgency,
        "sourceLevel": source_level,
        "claimStatus": claim_status,
        "dataStatus": data_status,
        "verification": verification,
        "materiality": "UNKNOWN", "materialityStatus": materiality_status,
        "direction": "UNKNOWN", "thesisImpact": "UNKNOWN", "riskGate": gate,
        "decisionLocked": locked, "lock_reasons": reasons, "new_buy_locked": locked,
        "structural_risk": None, "fast_risk_defense_allowed": False, "risk_class": risk_class,
        "raw_title": raw_title, "norm_title": norm_title, "tokens": tokens,
        "facts": {}, "metrics": [], "unknowns": [],
        "link_status": "NONE", "parent_event_id": None,
        "candidate_parent_event_id": None, "link_confidence": None, "link_note": None,
        "versions": [{"rcept_no": rcept_no, "version_type": version_type, "rcept_dt": rcept_dt, "url": url}],
        "first_seen": rcept_dt, "last_updated": rcept_dt,
    }
