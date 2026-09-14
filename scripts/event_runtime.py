# v 20260915-WaveC2 event_runtime.py — DART list 신규 Event만 상세조회/중대성 계산/장기보존.
# 운영 원칙: 매 실행마다 전체 34종목×9 endpoint를 돌지 않는다. 신규/미해결 Event에 해당 endpoint만 호출한다.
# 첫 운영 실행(index 없음)은 baseline 구축으로 간주해 기존 공시 알림 폭탄을 막는다.
import json, os, datetime as dt
import event_normalizer as N
import correction_resolver as C
import corp_code_cache as CC
import opendart_detail as OD
import materiality as MAT
import risk_gate as RG

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__))); P=lambda *a:os.path.join(ROOT,*a)
KST=dt.timezone(dt.timedelta(hours=9))
MAX_DETAIL_ATTEMPTS=3


def _load(path, default):
    try:
        with open(path,encoding="utf-8") as f: return json.load(f)
    except FileNotFoundError: return default


def _save(path, obj):
    os.makedirs(os.path.dirname(path),exist_ok=True)
    with open(path,"w",encoding="utf-8",newline="\n") as f: json.dump(obj,f,ensure_ascii=False,indent=2)


def _now(): return dt.datetime.now(KST).replace(microsecond=0).isoformat()


def _rcept(ev): return str((ev.get("versions") or [{}])[0].get("rcept_no") or ev.get("rcept_no") or "")
def _date(ev): return str((ev.get("versions") or [{}])[0].get("rcept_dt") or ev.get("date") or "")


def _summary(ev):
    return {
        "event_id":ev.get("event_id"),"date":_date(ev),"stock_code":ev.get("stock_code"),"corp_code":ev.get("corp_code"),
        "rcept_no":_rcept(ev),"company":ev.get("company"),"family":ev.get("family"),"type":ev.get("type"),
        "version_type":ev.get("version_type"),"urgency":ev.get("urgency"),
        "sourceLevel":ev.get("sourceLevel"),"claimStatus":ev.get("claimStatus"),"dataStatus":ev.get("dataStatus"),
        "materiality":ev.get("materiality","UNKNOWN"),"materialityStatus":ev.get("materialityStatus","UNKNOWN"),
        "riskGate":ev.get("riskGate"),"decisionLocked":ev.get("decisionLocked",True),
        "structural_risk":ev.get("structural_risk"),"fast_risk_defense_allowed":ev.get("fast_risk_defense_allowed",False),
        "link_status":ev.get("link_status"),"link_confidence":ev.get("link_confidence"),
        "detailStatus":ev.get("detailStatus","NOT_RUN"),"detailAttempts":int(ev.get("detailAttempts",0)),
        "lastDetailAttemptAt":ev.get("lastDetailAttemptAt"),"url":(ev.get("versions") or [{}])[0].get("url",ev.get("url",""))
    }


def _ensure_corp_map(key, stock_codes):
    cmap=CC.load_map(); missing=[c for c in stock_codes if c not in cmap]
    if not missing: return cmap, None
    try:
        result=CC.build(); cmap=CC.load_map()
        return cmap, result
    except Exception as e:
        return cmap, {"ok":False,"reason":f"{type(e).__name__}:{e}"}


def _mark_unknown(ev, status, reason):
    ev["detailStatus"]=status
    ev["materialityStatus"]="UNKNOWN"
    ev["materiality"]="UNKNOWN"
    if reason and reason not in ev["unknowns"]: ev["unknowns"].append(reason)
    RG.evaluate(ev)
    return ev


def enrich_event(ev, key, corp_map, field_map=None, fetcher=None):
    """신규/미해결 한 Event만 상세조회. 실패는 UNKNOWN으로 남기고 collector 전체를 깨뜨리지 않는다."""
    fm=field_map if field_map is not None else MAT.load_field_map(); fetcher=fetcher or OD.fetch
    sc=ev.get("stock_code",""); corp=(corp_map.get(sc) or {}).get("corp_code")
    ev["corp_code"]=corp or ev.get("corp_code") or None
    ev["detailAttempts"]=int(ev.get("detailAttempts",0))+1; ev["lastDetailAttemptAt"]=_now()

    entry=fm.get(ev.get("type"),{})
    if entry.get("materialityStatus")=="NOT_REQUIRED":
        ev["detailStatus"]="NOT_REQUIRED"; ev["materialityStatus"]="NOT_REQUIRED"; ev["materiality"]="M3"
        RG.evaluate(ev); return ev
    if not OD.endpoint_for(ev.get("type")):
        return _mark_unknown(ev,"NO_ENDPOINT","구조화 상세 API 없음")
    if not corp:
        return _mark_unknown(ev,"NO_CORP_CODE","corp_code 미확인")
    rdt=_date(ev); rno=_rcept(ev)
    try: res=fetcher(ev["type"],corp,rdt,rdt,key)
    except Exception as e: return _mark_unknown(ev,"API_ERROR",f"상세 API 예외:{type(e).__name__}")
    if not res.get("ok"):
        return _mark_unknown(ev,"API_ERROR",f"상세 API 오류:{res.get('status') or res.get('reason')}")
    if res.get("match")=="NO_DETAIL_RECORD":
        return _mark_unknown(ev,"NO_DETAIL_RECORD","상세 API에 동일일자 자료 없음")
    row,state=OD.match_by_rcept(res.get("list",[]),rno)
    if state!="MATCHED" or row is None:
        return _mark_unknown(ev,"NO_RCEPT_MATCH","상세 API rcept_no exact match 없음")
    schema=OD.check_schema(res.get("field_names",[]),ev["type"],fm)
    if schema.get("schema")=="SCHEMA_MISMATCH":
        ev["schemaMismatch"]=schema.get("missing",[])
        return _mark_unknown(ev,"SCHEMA_MISMATCH","상세 API schema mismatch")
    mets,ov=MAT.compute(ev["type"],row,{},rno,field_map=fm)
    ev["facts"]=MAT.extract_facts(ev["type"],row,fm); ev["metrics"]=mets; ev["materialityStatus"]=ov
    ev["materiality"]=MAT.band_for(ev["type"],mets)
    ev["detailStatus"]="MATCHED"
    if ov=="CONFLICT" and "공식값/재계산값 충돌" not in ev["unknowns"]: ev["unknowns"].append("공식값/재계산값 충돌")
    RG.evaluate(ev); return ev


def _upsert_day(ev):
    d=_date(ev)
    if len(d)!=8: return
    path=P("facts","events",f"{d[:4]}-{d[4:6]}-{d[6:8]}.json")
    doc=_load(path,{"schema":"events-day/2","date":f"{d[:4]}-{d[4:6]}-{d[6:8]}","events":[]})
    events=doc.get("events",[]); r=_rcept(ev); replaced=False
    for i,old in enumerate(events):
        if _rcept(old)==r:
            events[i]=ev; replaced=True; break
    if not replaced: events.append(ev)
    events.sort(key=lambda x:(_date(x),_rcept(x)),reverse=True); doc["events"]=events
    _save(path,doc)


def _restore_summary_state(ev, old):
    """normalizer가 새 객체를 만들더라도 이미 검증한 요약 상태는 잃지 않는다."""
    if not old: return ev
    for k,default in (
        ("corp_code",None),("detailAttempts",0),("detailStatus","NOT_RUN"),("lastDetailAttemptAt",None),
        ("materiality","UNKNOWN"),("materialityStatus","UNKNOWN"),("structural_risk",None),
        ("fast_risk_defense_allowed",False),("riskGate","G2"),("decisionLocked",True)):
        if k in old: ev[k]=old.get(k,default)
    return ev


def process(items, key):
    """현재 DART list items를 Event로 처리하고 신규/중대성변경 Event를 반환한다."""
    now=_now(); idx_path=P("facts","events","index.json")
    index_existed=os.path.exists(idx_path)
    idx=_load(idx_path,{"schema":"events-index/2","updated":now,"count":0,"events":[]})
    # index 자체가 없거나 비어 있으면 첫 운영 baseline. 기존 공시는 저장하되 알림하지 않는다.
    baseline_mode=(not index_existed) or not bool(idx.get("events"))
    old_by_rcept={str(x.get("rcept_no") or ""):x for x in idx.get("events",[])}
    current=C.resolve(N.normalize_all(items))
    stock_codes={e.get("stock_code") for e in current if e.get("stock_code")}
    cmap,corp_refresh=_ensure_corp_map(key,stock_codes); fm=MAT.load_field_map()
    new_events=[]; material_updates=[]; processed=[]

    for ev in current:
        r=_rcept(ev); old=old_by_rcept.get(r); is_new=old is None
        _restore_summary_state(ev,old)
        retry=(not is_new and ev.get("detailStatus") not in ("MATCHED","NOT_REQUIRED","NO_ENDPOINT") and int(ev.get("detailAttempts",0))<MAX_DETAIL_ATTEMPTS)
        if is_new or retry:
            before=old.get("materiality","UNKNOWN") if old else "UNKNOWN"
            ev=enrich_event(ev,key,cmap,field_map=fm)
            if not baseline_mode and not is_new and before!=ev.get("materiality") and ev.get("materiality") in ("M2","M3"):
                ev["notification_reason"]="MATERIALITY_UPDATE"; material_updates.append(ev)
            _upsert_day(ev)
        else:
            RG.evaluate(ev)
        if is_new and not baseline_mode:
            ev["notification_reason"]="NEW_EVENT"; new_events.append(ev)
        processed.append(ev)
        old_by_rcept[r]=_summary(ev)

    merged=list(old_by_rcept.values()); merged.sort(key=lambda x:(str(x.get("date") or ""),str(x.get("rcept_no") or "")),reverse=True)
    out={"schema":"events-index/2","updated":now,"count":len(merged),"baselineBuiltAt":idx.get("baselineBuiltAt") or (now if baseline_mode else None),"events":merged}
    _save(idx_path,out)
    return {"processed":processed,"new_events":new_events,"material_updates":material_updates,
            "corp_refresh":corp_refresh,"index_count":len(merged),"baseline_mode":baseline_mode,
            "baseline_count":len(current) if baseline_mode else 0}
