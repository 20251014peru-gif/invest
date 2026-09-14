# Wave B 오프라인 단위테스트 — 공식필드 기반 계산·상태·parser 검증. 네트워크 불필요.
import os, sys
from decimal import Decimal
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),"..","scripts"))
import materiality as MAT, risk_gate as RG, opendart_detail as OD, event_normalizer as N
R=[]; ck=lambda n,c,d="":R.append((n,bool(c),d)); FM=MAT.load_field_map()
ck("parser 콤마제거", MAT.num("92,000,000,000")==Decimal("92000000000"))
ck("parser 소수", MAT.num("18.4")==Decimal("18.4"))
ck("parser '-'·''·null → None", MAT.num("-") is None and MAT.num("") is None and MAT.num(None) is None)
ck("endpoint 9종 등록", all(OD.endpoint_for(k) for k in ["RIGHTS_OFFERING","CB_ISSUE","BW_ISSUE","EB_ISSUE","BUYBACK","TREASURY_DISPOSAL","DEFAULT","BUSINESS_SUSPENSION","LITIGATION"]))
ck("VERIFIED_SCHEMA 3종", sorted(k for k,v in FM.items() if v.get("status")=="VERIFIED_SCHEMA")==["BUSINESS_SUSPENSION","BW_ISSUE","RIGHTS_OFFERING"])
ck("PENDING 5종 자동계산 비활성", MAT.compute("CB_ISSUE",{"x":1},{},"r",FM)[1]=="UNKNOWN")
mo,_=MAT.compute("BUSINESS_SUSPENSION",{"bsnsp_amt":"92,000,000,000","rsl":"500,000,000,000","sl_vs":"18.4"},{},"R1",FM)
ck("영업정지 computed 18.4", mo[0]["computedValue"]==18.4)
ck("reported≈computed→VERIFIED, 둘 다 보존", mo[0]["status"]=="VERIFIED" and mo[0]["reportedValue"]==18.4 and mo[0]["diff_pp"]==0.0)
mc,sc=MAT.compute("BUSINESS_SUSPENSION",{"bsnsp_amt":"156000000000","rsl":"500000000000","sl_vs":"18.4"},{},"R2",FM)
ck("reported≠computed→CONFLICT(+overall)", mc[0]["status"]=="CONFLICT" and sc=="CONFLICT" and mc[0]["reason"]=="OVER_TOLERANCE")
mz,_=MAT.compute("BUSINESS_SUSPENSION",{"bsnsp_amt":"1","rsl":"0"},{},"R3",FM)
ck("0 분모 → UNKNOWN/ZERO_DENOMINATOR", mz[0]["status"]=="UNKNOWN" and mz[0]["reason"]=="ZERO_DENOMINATOR")
row={"nstk_ostk_cnt":"1,000,000","nstk_estk_cnt":"-","bfic_tisstk_ostk":"10,000,000","bfic_tisstk_estk":"-","fdpp_op":"5000000000"}
mets,st=MAT.compute("RIGHTS_OFFERING",row,{},"R4",FM); byname={x["metric"]:x for x in mets}
ck("보통주 희석 10%", byname["ordinary_dilution"]["computedValue"]==10.0 and byname["ordinary_dilution"]["status"]=="CALCULATED")
ck("기타주 없음 → other/total UNKNOWN", byname["other_share_dilution"]["status"]=="UNKNOWN" and byname["total_dilution"]["status"]=="UNKNOWN")
ck("조달/시총 외부없음 → UNKNOWN, overall PARTIAL", byname["raise_to_mktcap"]["status"]=="UNKNOWN" and st=="PARTIAL")
row0={"nstk_ostk_cnt":"1000000","nstk_estk_cnt":"0","bfic_tisstk_ostk":"10000000","bfic_tisstk_estk":"0"}
m0={x["metric"]:x for x in MAT.compute("RIGHTS_OFFERING",row0,{},"R5",FM)[0]}
ck("기타주식 0 → total_dilution==ordinary(10%)", m0["total_dilution"]["computedValue"]==10.0)
facts=MAT.extract_facts("RIGHTS_OFFERING",{"fdpp_op":"5000000000","ic_mthn":"제3자배정","fdpp_fclt":None},FM)
ck("fdpp/ic_mthn Fact 보존", facts.get("fdpp_op")=="5000000000" and facts.get("ic_mthn")=="제3자배정" and "fdpp_fclt" not in facts)
ck("M과 방향 분리(direction=UNKNOWN)", mo[0]["direction"]=="UNKNOWN")
ck("부도 materialityStatus NOT_REQUIRED", MAT.compute("DEFAULT",{}, {},"R6",FM)[1]=="NOT_REQUIRED")
ev=N.normalize_item({"stock_code":"111111","company":"X","sector":"s","report_nm":"부도발생","rcept_no":"29990101000001","rcept_dt":"29990101","url":""}); ev["materialityStatus"]="NOT_REQUIRED"; RG.evaluate(ev)
ck("부도 → 구조 HIGH·방어허용·M3·잠금", ev["structural_risk"]=="HIGH" and ev["fast_risk_defense_allowed"] and ev["materiality"]=="M3" and ev["new_buy_locked"])
ck("영업정지 기대필드 없음 → SCHEMA_MISMATCH", OD.check_schema(["rcept_no"],"BUSINESS_SUSPENSION",FM)["schema"]=="SCHEMA_MISMATCH")
ck("유상증자 total 필드 다 있으면 OK", OD.check_schema(["nstk_ostk_cnt","nstk_estk_cnt","bfic_tisstk_ostk","bfic_tisstk_estk"],"RIGHTS_OFFERING",FM)["schema"]=="OK")
aud=N.normalize_item({"stock_code":"111111","company":"X","sector":"s","report_nm":"감사보고서","rcept_no":"29990101000002","rcept_dt":"29990101","url":""})
ck("일반 감사보고서→PERIODIC/AUDIT_REPORT(U0)", aud["family"]=="PERIODIC" and aud["type"]=="AUDIT_REPORT" and aud["urgency"]=="U0")
bs=N.normalize_item({"stock_code":"111111","company":"X","sector":"s","report_nm":"영업정지","rcept_no":"29990101000003","rcept_dt":"29990101","url":""}); bs["materialityStatus"]="UNKNOWN"; RG.evaluate(bs)
ck("영업정지 규모미확인→자동 M3 금지·방어검토는 허용", bs["materiality"]=="UNKNOWN" and bs["fast_risk_defense_allowed"] and bs["structural_risk"]=="REVIEW")
p=sum(1 for _,ok,_ in R if ok)
print("Wave B 오프라인 단위테스트 (공식필드 기반)\n"+"-"*60)
for n,ok,d in R: print(f"  [{'PASS' if ok else 'FAIL'}] {n}"+(f"  · {d}" if d else ""))
print("-"*60+f"\n  합계 {p}/{len(R)} PASS")
sys.exit(0 if p==len(R) else 1)
