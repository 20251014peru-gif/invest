# v 20260915-WaveB4 replay_test.py — facts/dart.json 실제 28건 리플레이 + 안전성 회귀시험.
import json, os, sys, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import event_normalizer as N
import correction_resolver as C
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__))); P=lambda *a:os.path.join(ROOT,*a)

def load_items():
    with open(P("facts","dart.json"),encoding="utf-8") as f: return json.load(f).get("items",[])
def build_events(extra=None): return C.resolve(N.normalize_all(load_items()+(extra or [])))
def find(events,contains,version=None): return [e for e in events if contains in e["raw_title"] and (version is None or e["version_type"]==version)]

def run_tests(events):
    r=[]
    def ck(name,cond,detail=""): r.append((name,bool(cond),detail))
    base="단일판매{d}공급계약체결"; norms={N.normalize_title(base.format(d=d)) for d in ["\u318D","\u00B7","\u2219","\uFF65"]}
    ck("T12 유니코드 ㆍ·∙･ 동일 정규화",len(norms)==1,str(norms))
    ck("T11 version_type", N.detect_version("[첨부정정]단일판매ㆍ공급계약체결")=="ATTACHMENT_CORRECTION" and N.detect_version("[발행조건확정]전환사채발행결정")=="TERMS_FINAL" and N.detect_version("단일판매ㆍ공급계약체결철회")=="WITHDRAWAL" and N.detect_version("단일판매ㆍ공급계약체결")=="ORIGINAL")
    corr=[e for e in events if "정정" in e["raw_title"] and "공급계약" in e["raw_title"]]
    ck("T01 정정수주→CONTRACT+CORRECTION",corr and all(e["family"]=="CONTRACT" and e["version_type"]=="CORRECTION" for e in corr),f"{len(corr)}건")
    ck("T01 정정수주 신규알림 금지",all(not N.is_new_order_alert(e) for e in corr))
    orig=find(events,"단일판매",version="ORIGINAL"); ck("T02 신규수주",orig and all(e["type"]=="SUPPLY_CONTRACT" and N.is_new_order_alert(e) for e in orig),f"{len(orig)}건")
    ern=find(events,"잠정"); ck("T03 잠정실적→EARNINGS",ern and all(e["family"]=="EARNINGS" for e in ern),f"{len(ern)}건")
    ins=[e for e in events if "임원" in e["raw_title"] and "주요주주" in e["raw_title"]]; ck("T04 임원·주요주주→OWNERSHIP",ins and all(e["family"]=="OWNERSHIP" for e in ins),f"{len(ins)}건")
    maj=find(events,"최대주주"); ck("T05 최대주주→OWNERSHIP/CONTROL",maj and all(e["family"] in ("OWNERSHIP","CONTROL") for e in maj),f"{len(maj)}건")
    fac=find(events,"신규시설투자"); ck("T06 신규시설투자→ASSET",fac and all(e["family"]=="ASSET" for e in fac),f"{len(fac)}건")
    rum=find(events,"풍문"); ck("T07 풍문해명→RUMOR_CHECK",rum and all(e["family"]=="RUMOR_CHECK" for e in rum)); ck("T10 풍문 S3/UNCONFIRMED/NA/잠김",rum and all(e["sourceLevel"]=="S3" and e["claimStatus"]=="UNCONFIRMED" and e["dataStatus"]=="NA" and e["decisionLocked"] for e in rum))
    ck("T13 잠정실적 S3/CONFIRMED/PRELIMINARY",ern and all(e["sourceLevel"]=="S3" and e["claimStatus"]=="CONFIRMED" and e["dataStatus"]=="PRELIMINARY" for e in ern))
    ck("T08 숫자부족→UNKNOWN",all(e["materiality"]=="UNKNOWN" and e["metrics"]==[] for e in events))
    unk=[e for e in events if e["raw_title"]=="완전히새로운형식의공시XYZ"]; ck("T09 unknown→OTHER/UNMAPPED/잠김",unk and unk[0]["family"]=="OTHER" and unk[0]["type"]=="UNMAPPED" and unk[0]["decisionLocked"])
    ck("정정 자동병합 0건",len([e for e in events if e["link_status"]=="CONFIRMED"])==0)
    cand=[e for e in events if e["link_status"]=="CANDIDATE"]; ck("CANDIDATE HIGH 금지",all(e["link_confidence"]!="HIGH" for e in cand),f"{len(cand)}건")
    a=N.normalize_item({"stock_code":"111111","company":"X","sector":"s","report_nm":"단일판매ㆍ공급계약체결","rcept_no":"29990101001234","rcept_dt":"29990101","url":""}); b=N.normalize_item({"stock_code":"111111","company":"X","sector":"s","report_nm":"단일판매ㆍ공급계약체결","rcept_no":"29990101991234","rcept_dt":"29990101","url":""})
    ck("Event ID suffix 충돌 방지",a["event_id"]!=b["event_id"])
    return r

def write_events(events):
    by_date={}
    for e in events: by_date.setdefault(e["versions"][0]["rcept_dt"],[]).append(e)
    os.makedirs(P("facts","events"),exist_ok=True); now=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).replace(microsecond=0).isoformat()
    idx={"schema":"events-index/1","updated":now,"count":len(events),"events":[{"event_id":e["event_id"],"date":e["versions"][0]["rcept_dt"],"stock_code":e["stock_code"],"rcept_no":e["versions"][0]["rcept_no"],"company":e["company"],"type":e["type"],"version_type":e["version_type"],"link_status":e["link_status"],"link_confidence":e["link_confidence"],"decisionLocked":e["decisionLocked"]} for e in events]}
    with open(P("facts","events","index.json"),"w",encoding="utf-8",newline="\n") as f: json.dump(idx,f,ensure_ascii=False,indent=2)
    for d,evs in by_date.items():
        with open(P("facts","events",f"{d[:4]}-{d[4:6]}-{d[6:8]}.json"),"w",encoding="utf-8",newline="\n") as f: json.dump({"schema":"events-day/1","date":f"{d[:4]}-{d[4:6]}-{d[6:8]}","events":evs},f,ensure_ascii=False,indent=2)

if __name__=="__main__":
    synthetic=[{"stock_code":"000000","company":"테스트","sector":"테스트","report_nm":"완전히새로운형식의공시XYZ","rcept_no":"29990101999999","rcept_dt":"29990101","url":""}]
    events=build_events(extra=synthetic); real=[e for e in events if e["stock_code"]!="000000"]; results=run_tests(events)
    passed=sum(1 for _,ok,_ in results if ok)
    for name,ok,detail in results: print(f"[{'PASS' if ok else 'FAIL'}] {name}"+(f" · {detail}" if detail else ""))
    print(f"합계 {passed}/{len(results)} PASS"); write_events(real); sys.exit(0 if passed==len(results) else 1)
