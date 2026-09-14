# v 20260915-WaveB4 risk_gate.py — Gate(G0~G3) · claimStatus 반영 · 구조위험. Python only, AI 0.
import event_schema as S
STRUCTURAL_M3={"DEFAULT","REHABILITATION","AUDIT_OPINION","DELISTING"}
FAST_REVIEW={"TRADING_HALT","BUSINESS_SUSPENSION"}

def evaluate(ev):
    gate,locked,reasons=S.compute_gate_and_lock(ev["sourceLevel"],ev["claimStatus"],ev["materialityStatus"],ev["family"])
    ev["riskGate"]=gate
    confirmed = ev["claimStatus"]=="CONFIRMED"
    structural = ev["type"] in STRUCTURAL_M3 and confirmed
    fast_review = ev["type"] in FAST_REVIEW and confirmed
    if structural:
        ev["structural_risk"]="HIGH"; ev["fast_risk_defense_allowed"]=True
        if ev["materialityStatus"] in ("NOT_REQUIRED","UNKNOWN","NOT_RUN"):
            ev["materiality"]="M3"
        reasons=list(dict.fromkeys(reasons+["구조적 위험(FAST_RISK)"]))
    elif fast_review:
        ev["structural_risk"]="REVIEW"; ev["fast_risk_defense_allowed"]=True
        reasons=list(dict.fromkeys(reasons+["신속 방어검토 필요(원인/규모 확인)"]))
    else:
        ev["structural_risk"]="UNKNOWN" if ev["materialityStatus"] in ("UNKNOWN","NOT_RUN",None) else "NORMAL"
        ev["fast_risk_defense_allowed"]=False
    ev["decisionLocked"]=locked or gate!="G6"
    ev["new_buy_locked"]=ev["decisionLocked"]
    ev["lock_reasons"]=reasons
    return ev
