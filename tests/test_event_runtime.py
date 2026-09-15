import os, sys, tempfile, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),"..","scripts"))
import event_normalizer as N
import event_runtime as ER
import event_notifier as EN
import materiality as MAT

R=[]
def ck(name,cond,detail=""): R.append((name,bool(cond),detail))

def raw(title,no="29990101000001",code="005930"):
    return {"stock_code":code,"company":"테스트전자","sector":"반도체","report_nm":title,
            "rcept_no":no,"rcept_dt":"29990101","url":"https://dart.test/"+no}

# 알림 분류: 정정을 신규수주로 다루지 않고, 보유 여부 없이는 FAST_RISK 금지
corr=N.normalize_item(raw("[기재정정]단일판매ㆍ공급계약체결")); corr["materialityStatus"]="UNKNOWN"; corr["materiality"]="UNKNOWN"
ck("정정수주 → CORRECTION_REVIEW", EN.classify(corr)=="CORRECTION_REVIEW")
orig=N.normalize_item(raw("단일판매ㆍ공급계약체결","29990101000002")); orig["materialityStatus"]="UNKNOWN"; orig["materiality"]="UNKNOWN"
ck("신규수주 규모미확인 → WATCH_EVENT", EN.classify(orig)=="WATCH_EVENT")
risk=N.normalize_item(raw("부도발생","29990101000003")); risk["claimStatus"]="CONFIRMED"; risk["structural_risk"]="HIGH"; risk["materiality"]="M3"; risk["decisionLocked"]=True
ck("보유여부 미확인 구조위험 → FAST_RISK 금지", EN.classify(risk)=="RISK_REVIEW")
risk["is_held"]=True
ck("보유종목 확정 구조위험 → FAST_RISK", EN.classify(risk)=="FAST_RISK")

# 상세 API exact rcept match + 사건별 threshold
fm=MAT.load_field_map(); ev=N.normalize_item(raw("유상증자결정","29990101000004"))
def fake_fetch(event_type,corp,bgn,end,key):
    row={"rcept_no":"29990101000004","nstk_ostk_cnt":"1000000","nstk_estk_cnt":"0",
         "bfic_tisstk_ostk":"10000000","bfic_tisstk_estk":"0","fdpp_op":"5000000000","ic_mthn":"제3자배정"}
    return {"ok":True,"status":"000","list":[row],"field_names":sorted(row.keys())}
en=ER.enrich_event(ev,"KEY",{"005930":{"corp_code":"00126380"}},field_map=fm,fetcher=fake_fetch)
ck("상세 rcept exact match", en["detailStatus"]=="MATCHED")
ck("유상증자 10% → M2", en["materiality"]=="M2",str(en.get("materiality")))
ck("G3 도달", en["riskGate"]=="G3")
ck("G3여도 신규매수 잠금 유지", en["new_buy_locked"] is True)

# process: 첫 실행은 baseline(알림 0), 이후 동일 rcept 중복금지, 진짜 신규만 알림
with tempfile.TemporaryDirectory() as td:
    oldroot=ER.ROOT; ER.ROOT=td
    os.makedirs(os.path.join(td,"facts","events"),exist_ok=True)
    original_source=ER.DS.fetch; ER.DS.fetch=lambda r,key: {"status":"UNAVAILABLE","rceptNo":r}; original_ensure=ER._ensure_corp_map; original_enrich=ER.enrich_event
    ER._ensure_corp_map=lambda key,codes: ({"005930":{"corp_code":"00126380"}},None)
    def simple_enrich(e,key,cmap,field_map=None,fetcher=None):
        e["corp_code"]="00126380"; e["detailAttempts"]=1; e["detailStatus"]="NO_ENDPOINT"
        e["lastDetailAttemptAt"]="2999-01-01T10:00:00+09:00"
        e["materialityStatus"]="UNKNOWN"; e["materiality"]="UNKNOWN"; return e
    ER.enrich_event=simple_enrich
    item=raw("단일판매ㆍ공급계약체결","29990101000009")
    a=ER.process([item],"KEY")
    ck("첫 실행 baseline_mode", a["baseline_mode"] is True)
    ck("첫 실행 기존공시 알림 0건", len(a["new_events"])==0)
    b=ER.process([item],"KEY")
    ck("두번째 동일 rcept 신규 0건", len(b["new_events"])==0)
    idx=json.load(open(os.path.join(td,"facts","events","index.json"),encoding="utf-8"))
    ck("Event index 중복 없음", idx["count"]==1)
    saved=idx["events"][0]
    ck("기존 detailAttempts 보존", saved["detailAttempts"]==1)
    ck("기존 lastDetailAttemptAt 보존", saved["lastDetailAttemptAt"]=="2999-01-01T10:00:00+09:00")
    ck("기존 corp_code 보존", saved["corp_code"]=="00126380")
    new_item=raw("단일판매ㆍ공급계약체결","29990101000010")
    c=ER.process([item,new_item],"KEY")
    ck("baseline 이후 진짜 신규 1건만 알림", len(c["new_events"])==1 and ER._rcept(c["new_events"][0])=="29990101000010")
    ER.DS.fetch=original_source; ER._ensure_corp_map=original_ensure; ER.enrich_event=original_enrich; ER.ROOT=oldroot

p=sum(1 for _,ok,_ in R if ok)
print("Event Runtime/Notifier tests\n"+"-"*60)
for n,ok,d in R: print(f"  [{'PASS' if ok else 'FAIL'}] {n}"+(f" · {d}" if d else ""))
print("-"*60+f"\n  합계 {p}/{len(R)} PASS")
sys.exit(0 if p==len(R) else 1)
