# v 20260915-WaveB2  opendart_detail.py — 고위험 Event 공식 상세 API adapter (DS005). endpoint 는 공식명만(추측 금지).
# 반환 field 는 실호출로 확인. field_map 의 기대 키와 대조해 SCHEMA_MISMATCH 판정.
import json, urllib.request, urllib.parse
BASE="https://opendart.fss.or.kr/api/"
ENDPOINTS={
 "RIGHTS_OFFERING":"piicDecsn.json","CB_ISSUE":"cvbdIsDecsn.json","BW_ISSUE":"bdwtIsDecsn.json",
 "EB_ISSUE":"exbdIsDecsn.json","BUYBACK":"tsstkAqDecsn.json","TREASURY_DISPOSAL":"tsstkDpDecsn.json",
 "DEFAULT":"dfOcr.json","BUSINESS_SUSPENSION":"bsnSp.json","LITIGATION":"lwstLg.json"}
def endpoint_for(t): return ENDPOINTS.get(t)

def fetch(event_type, corp_code, bgn_de, end_de, key):
    ep=endpoint_for(event_type)
    if not ep: return {"ok":False,"match":"API_ERROR","reason":f"endpoint 미정의:{event_type}"}
    url=BASE+ep+"?"+urllib.parse.urlencode({"crtfc_key":key,"corp_code":corp_code,"bgn_de":bgn_de,"end_de":end_de})
    try:
        with urllib.request.urlopen(url,timeout=25) as r: d=json.loads(r.read().decode("utf-8"))
    except Exception as e:
        return {"ok":False,"match":"API_ERROR","reason":f"{type(e).__name__}:{e}","endpoint":ep}
    st=str(d.get("status"))
    if st=="013": return {"ok":True,"match":"NO_DETAIL_RECORD","status":st,"endpoint":ep,"count":0,"list":[],"field_names":[]}
    if st!="000": return {"ok":False,"match":"API_ERROR","status":st,"message":d.get("message"),"endpoint":ep}
    rows=d.get("list",[])
    return {"ok":True,"status":st,"endpoint":ep,"count":len(rows),"list":rows,
            "field_names":sorted({k for row in rows for k in row.keys()})}

def match_by_rcept(rows, rcept_no):
    hit=[r for r in rows if str(r.get("rcept_no"))==str(rcept_no)]
    return (hit[0],"MATCHED") if hit else (None,"NO_MATCH_IN_ROWS")

def check_schema(field_names, event_type, field_map):
    entry=field_map.get(event_type,{})
    if entry.get("status")=="PENDING_GUIDE_READ" or entry.get("materialityStatus")=="NOT_REQUIRED":
        return {"schema":"SKIP"}
    need=set()
    for m in entry.get("metrics",[]):
        if m.get("reported_field"): need.add(m["reported_field"])
        for spec in (m.get("numerator",{}), m.get("denominator",{})):
            if "field" in spec: need.add(spec["field"])
            if "fields" in spec: need.update(spec["fields"])
    missing=sorted(need - set(field_names))
    return {"schema":"OK"} if not missing else {"schema":"SCHEMA_MISMATCH","missing":missing}
