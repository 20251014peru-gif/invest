# v 20260915-WaveB5  event_engine_validate.py — GitHub Actions에서 실제 OpenDART 검증.
# 현재 7일 index에 샘플이 없어도 watchlist corp_code 기준으로 180/365일 상세 API를 직접 탐색한다.
import os, json, sys, datetime as dt, urllib.request, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import corp_code_cache as CC, opendart_detail as OD, materiality as MAT, risk_gate as RG, event_normalizer as N
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__))); P=lambda *a:os.path.join(ROOT,*a)
KST=dt.timezone(dt.timedelta(hours=9)); SENSITIVE=("crtfc_key",)
MAX_SUCCESS_CORPS_PER_ENDPOINT=3

def _san(row): return {k:v for k,v in (row or {}).items() if k not in SENSITIVE}

def _watch_meta():
    try: sec=json.load(open(P("data","sectors.json"),encoding="utf-8"))
    except FileNotFoundError: return {}
    out={}
    for s in sec.get("sectors",[]):
        for c in s.get("companies",[]):
            code=(c.get("code") or "").strip()
            if len(code)==6 and code.isdigit(): out[code]={"company":c.get("name") or "","sector":s.get("name") or ""}
    return out

def _fetch_list_rows(corp_code,bgn_de,end_de,key):
    rows=[]; page=1; pages=1
    while page<=pages and page<=20:
        q={"crtfc_key":key,"corp_code":corp_code,"bgn_de":bgn_de,"end_de":end_de,"page_no":page,"page_count":100}
        url="https://opendart.fss.or.kr/api/list.json?"+urllib.parse.urlencode(q)
        try:
            with urllib.request.urlopen(url,timeout=25) as r: d=json.loads(r.read().decode("utf-8"))
        except Exception as e: return {"ok":False,"reason":f"{type(e).__name__}:{e}","rows":[]}
        st=str(d.get("status"))
        if st=="013": return {"ok":True,"rows":[]}
        if st!="000": return {"ok":False,"status":st,"reason":d.get("message"),"rows":[]}
        rows.extend(d.get("list",[])); pages=int(d.get("total_page",1)); page+=1
    return {"ok":True,"rows":rows}

def _raw_item(list_row, stock_code, meta):
    no=str(list_row.get("rcept_no") or "")
    return {"stock_code":stock_code,"company":meta.get("company") or list_row.get("corp_name") or "",
            "sector":meta.get("sector") or "","report_nm":list_row.get("report_nm") or "",
            "rcept_dt":list_row.get("rcept_dt") or "","rcept_no":no,
            "url":"https://dart.fss.or.kr/dsaf001/main.do?rcpNo="+no}

def run(days=None):
    key=os.environ.get("DART_API_KEY","").strip(); days=int(days or os.environ.get("DART_DAYS","180"))
    if not key:
        print(json.dumps({"error":"DART_API_KEY 미설정"},ensure_ascii=False)); return 2
    FM=MAT.load_field_map(); corp_result=CC.build(); cmap=CC.load_map(); meta=_watch_meta()
    end=dt.datetime.now(KST).date(); bgn=end-dt.timedelta(days=days); bgn_s,end_s=bgn.strftime("%Y%m%d"),end.strftime("%Y%m%d")
    rep={"at":dt.datetime.now(KST).replace(microsecond=0).isoformat(),"days":days,"corpCode":corp_result,"endpoints":[],"errors":[]}
    fixdir=P("tests","fixtures","opendart"); os.makedirs(fixdir,exist_ok=True); list_cache={}
    corp_items=[(sc,v.get("corp_code"),meta.get(sc,{"company":v.get("corp_name","") or "","sector":""})) for sc,v in cmap.items() if v.get("corp_code")]
    for et in OD.ENDPOINTS:
        a={"type":et,"endpoint":OD.endpoint_for(et),"corp_queries":0,"status_ok":0,"schema":"-","field_names":set(),
           "MATCHED":0,"NO_DETAIL_RECORD":0,"NO_MATCH":0,"TYPE_MISMATCH":0,"reported":0,"computed":0,
           "VERIFIED":0,"CALCULATED":0,"REPORTED_ONLY":0,"CONFLICT":0,"UNKNOWN":0,"NOT_REQUIRED":0,"G3":0,
           "M0":0,"M1":0,"M2":0,"M3":0,"BAND_UNKNOWN":0,"samples":0}
        success_corps=0
        for sc,corp,m in corp_items:
            res=OD.fetch(et,corp,bgn_s,end_s,key); a["corp_queries"]+=1
            if res.get("match")=="API_ERROR":
                rep["errors"].append({"type":et,"stock_code":sc,"reason":res.get("reason") or res.get("message"),"status":res.get("status")}); continue
            if res.get("match")=="NO_DETAIL_RECORD": a["NO_DETAIL_RECORD"]+=1; continue
            a["status_ok"]+=1; success_corps+=1; a["field_names"]|=set(res.get("field_names",[]))
            scv=OD.check_schema(res.get("field_names",[]),et,FM)
            if scv["schema"]=="SCHEMA_MISMATCH":
                a["schema"]="SCHEMA_MISMATCH"; rep["errors"].append({"type":et,"stock_code":sc,"SCHEMA_MISMATCH":scv["missing"]})
            elif a["schema"]!="SCHEMA_MISMATCH": a["schema"]=scv["schema"]
            if corp not in list_cache: list_cache[corp]=_fetch_list_rows(corp,bgn_s,end_s,key)
            lr=list_cache[corp]
            if not lr.get("ok"):
                rep["errors"].append({"type":et,"stock_code":sc,"LIST_API_ERROR":lr.get("reason"),"status":lr.get("status")}); list_rows=[]
            else: list_rows=lr.get("rows",[])
            by_rcept={str(r.get("rcept_no") or ""):r for r in list_rows}
            for row in res.get("list",[])[:5]:
                a["samples"]+=1; rcept=str(row.get("rcept_no") or ""); list_row=by_rcept.get(rcept); ev=None; match_state="NO_MATCH"
                if list_row:
                    ev=N.normalize_item(_raw_item(list_row,sc,m))
                    if ev["versions"][0]["rcept_no"]==rcept and ev["type"]==et:
                        match_state="MATCHED"; a["MATCHED"]+=1
                    else:
                        match_state="TYPE_MISMATCH"; a["TYPE_MISMATCH"]+=1; rep["errors"].append({"type":et,"stock_code":sc,"rcept_no":rcept,"TYPE_MISMATCH":ev.get("type")})
                else: a["NO_MATCH"]+=1
                mets,ov=MAT.compute(et,row,{},rcept,field_map=FM)
                band="M3" if ov=="NOT_REQUIRED" and et=="DEFAULT" else MAT.band_for(et,mets)
                if band in ("M0","M1","M2","M3"): a[band]+=1
                else: a["BAND_UNKNOWN"]+=1
                for metric in mets:
                    if metric.get("reportedValue") is not None: a["reported"]+=1
                    if metric.get("computedValue") is not None: a["computed"]+=1
                    st=metric.get("status")
                    if st in ("VERIFIED","CALCULATED","REPORTED_ONLY","CONFLICT"): a[st]+=1
                if ov=="UNKNOWN": a["UNKNOWN"]+=1
                if ov=="NOT_REQUIRED": a["NOT_REQUIRED"]+=1
                if ev is not None:
                    ev["corp_code"]=corp; ev["facts"]=MAT.extract_facts(et,row,FM); ev["metrics"]=mets; ev["materialityStatus"]=ov
                    ev["materiality"]=band; RG.evaluate(ev)
                    if ev.get("riskGate")=="G3": a["G3"]+=1
                with open(os.path.join(fixdir,f"{et}_{rcept or sc}.json"),"w",encoding="utf-8") as f:
                    json.dump({"type":et,"stock_code":sc,"rcept_no":rcept,"match":match_state,"field_names":res.get("field_names",[]),
                               "materialityStatus":ov,"materiality":band,"facts":MAT.extract_facts(et,row,FM),"metrics":mets,"row":_san(row)},f,ensure_ascii=False,indent=2)
            if success_corps>=MAX_SUCCESS_CORPS_PER_ENDPOINT: break
        a["no_sample"]=a["status_ok"]==0; a["field_names"]=sorted(a["field_names"]); rep["endpoints"].append(a)
    endpoint_ok=sum(1 for a in rep["endpoints"] if a["status_ok"]>0); matched=sum(a["MATCHED"] for a in rep["endpoints"])
    materiality_real=sum(a["VERIFIED"]+a["CALCULATED"]+a["REPORTED_ONLY"] for a in rep["endpoints"])
    banded=sum(a["M0"]+a["M1"]+a["M2"]+a["M3"] for a in rep["endpoints"])
    schema_mismatch=sum(1 for e in rep["errors"] if "SCHEMA_MISMATCH" in e)
    validation_pass=bool(corp_result.get("ok") and corp_result.get("count",0)>0 and endpoint_ok>=3 and matched>=1 and materiality_real>=1 and banded>=1 and schema_mismatch==0)
    rep["validation"]={"pass":validation_pass,"endpoint_success":endpoint_ok,"matched":matched,"materiality_real":materiality_real,"materiality_banded":banded,"schema_mismatch":schema_mismatch}
    print(json.dumps(rep,ensure_ascii=False,indent=2))
    print(f"\n요약: 응답성공 endpoint {endpoint_ok}종 · MATCHED {matched} · Materiality실계산 {materiality_real} · 사건별M등급 {banded} · SCHEMA_MISMATCH {schema_mismatch} · 오류 {len(rep['errors'])} · LIVE_VALIDATION={'PASS' if validation_pass else 'FAIL'}")
    return 0 if validation_pass else 1

if __name__=="__main__": sys.exit(run())
