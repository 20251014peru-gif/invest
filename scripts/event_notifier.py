# v 20260915-WaveC1 event_notifier.py — Event 기반 ntfy 분류/전송. 투자판단과 알림긴급도를 분리한다.
import urllib.request

PRIORITY={"FAST_RISK":"5","BREAKING":"4","RISK_REVIEW":"4","MATERIAL_EVENT":"4","WATCH_EVENT":"3","CORRECTION_REVIEW":"3","RECORD":"2"}
LABEL={
    "FAST_RISK":"🚨 FAST RISK",
    "BREAKING":"⚠ BREAKING",
    "RISK_REVIEW":"⚠ RISK REVIEW",
    "MATERIAL_EVENT":"🔴 MATERIAL EVENT",
    "WATCH_EVENT":"🟡 WATCH EVENT",
    "CORRECTION_REVIEW":"🟠 CORRECTION REVIEW",
    "RECORD":"🟢 RECORD",
}


def classify(ev):
    """알림 등급. FAST_RISK는 보유 여부가 명시된 경우에만 허용한다."""
    held = ev.get("is_held") is True or ev.get("holding_status") == "HOLD"
    if held and ev.get("structural_risk") == "HIGH" and ev.get("claimStatus") == "CONFIRMED":
        return "FAST_RISK"
    if ev.get("urgency") == "U3" and ev.get("claimStatus") != "CONFIRMED":
        return "BREAKING"
    if ev.get("structural_risk") == "HIGH":
        return "RISK_REVIEW"
    if ev.get("materiality") == "M3":
        return "MATERIAL_EVENT"
    if ev.get("materiality") == "M2":
        return "WATCH_EVENT"
    if ev.get("version_type") != "ORIGINAL" and ev.get("family") not in ("PERIODIC","OTHER"):
        return "CORRECTION_REVIEW"
    if ev.get("type") == "SUPPLY_CONTRACT" and ev.get("version_type") == "ORIGINAL":
        return "WATCH_EVENT"
    return "RECORD"


def should_push(ev):
    return classify(ev) != "RECORD"


def _line(ev):
    cls=classify(ev)
    lock="🔒 투자판단 잠김" if ev.get("decisionLocked",True) else "투자판단 검토 가능"
    m=ev.get("materiality","UNKNOWN"); g=ev.get("riskGate","G0")
    version=ev.get("version_type","ORIGINAL")
    return f"{LABEL[cls]}\n{ev.get('company','')} · {ev.get('raw_title','')}\nM={m} · G={g} · {version}\n{lock}\n{ev.get('versions',[{}])[0].get('url','')}"


def build_message(events):
    push=[e for e in events if should_push(e)]
    if not push: return None
    # 가장 높은 우선순위를 제목에 사용한다.
    rank={"5":5,"4":4,"3":3,"2":2}
    top=max(push,key=lambda e:rank[PRIORITY[classify(e)]])
    top_cls=classify(top)
    body="\n\n".join(_line(e) for e in push[:10])
    return {"title":f"[공시 Event] {LABEL[top_cls]}","priority":PRIORITY[top_cls],"body":body,"count":len(push)}


def send(topic, events, click_url="https://20251014peru-gif.github.io/invest/records.html"):
    msg=build_message(events)
    if not topic or not msg: return {"sent":False,"reason":"NO_TOPIC_OR_PUSH_EVENT","count":0 if not msg else msg["count"]}
    h=lambda v:v.encode("utf-8").decode("latin-1")
    req=urllib.request.Request(
        "https://ntfy.sh/"+topic,
        data=msg["body"].encode("utf-8"),
        headers={"Title":h(msg["title"]),"Priority":msg["priority"],"Click":click_url})
    try:
        with urllib.request.urlopen(req,timeout=10) as r:
            return {"sent":True,"status":r.status,"count":msg["count"]}
    except Exception as e:
        return {"sent":False,"reason":f"{type(e).__name__}:{e}","count":msg["count"]}
