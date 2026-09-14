# Wave B 오프라인 단위테스트 — 공식필드 계산·상태·사건별 Materiality threshold 검증. 네트워크 불필요.
import os, sys
from decimal import Decimal
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),"..","scripts"))
import materiality as MAT, risk_gate as RG, opendart_detail as OD, event_normalizer as N
R=[]; ck=lambda n,c,d="":R.append((n,bool(c),d)); FM=MAT.load_field_map(); TH=MAT.load_thresholds()
ck("parser 콤마제거", MAT.num("92,000,000,000")==Decimal("92000000000"))
ck("parser 소수", MAT.num("18.4")==Decimal("18.4"))
ck("parser '-'·''·null → None", MAT.num("-") is None and MAT.num("") is None and MAT.num(None) is None)
ck("endpoint 9종 등록", all(OD.endpoint_for(k) for k in ["RIGHTS_OFFERING","CB_ISSUE","BW_ISSUE","EB_ISSUE","BUYBACK","TREASURY_DISPOSAL","DEFAULT","BUSINESS_SUSPENSION","LITIGATION"]))
verified={k for k,v in FM.items() if v.get("status") in ("VERIFIED_SCHEMA","LIVE_VERIFIED_SCHEMA")}
ck("검증 schema 7종", verified=={"RIGHTS_OFFERING","BUSINESS_SUSPENSION","BW_ISSUE","CB_ISSUE","EB_ISSUE","BUYBACK","TREASURY_DISPOSAL"}, str(sorted(verified)))
ck("PENDING은 소송 1종만", [k for k,v in FM.items() if v.get("status")=="PENDING_GUIDE_READ"]==["LITIGATION"])

# 영업정지 reported/computed 교차검증
mo,_=MAT.compute("BUSINESS_SUSPENSION",{"bsnsp_amt":"92,000,000,000","rsl":"500,000,000,000","sl_vs":"18.4"},{},"R1",FM)
ck("영업정지 computed 18.4", mo[0]["computedValue"]==18.4)
ck("reported≈computed→VERIFIED", mo[0]["status"]=="VERIFIED" and mo[0]["reportedValue"]==18.4 and mo[0]["diff_pp"]==0.0)
mc,sc=MAT.compute("BUSINESS_SUSPENSION",{"bsnsp_amt":"156000000000","rsl":"500000000000","sl_vs":"18.4"},{},"R2",FM)
ck("reported≠computed→CONFLICT", mc[0]["status"]=="CONFLICT" and sc=="CONFLICT")
mz,_=MAT.compute("BUSINESS_SUSPENSION",{"bsnsp_amt":"1","rsl":"0"},{},"R3",FM)
ck("0 분모 → UNKNOWN/ZERO_DENOMINATOR", mz[0]["status"]=="UNKNOWN" and mz[0]["reason"]=="ZERO_DENOMINATOR")

# 유상증자
row={"nstk_ostk_cnt":"1,000,000","nstk_estk_cnt":"-","bfic_tisstk_ostk":"10,000,000","bfic_tisstk_estk":"-","fdpp_op":"5000000000"}
mets,st=MAT.compute("RIGHTS_OFFERING",row,{},"R4",FM); byname={x["metric"]:x for x in mets}
ck("보통주 희석 10%", byname["ordinary_dilution"]["computedValue"]==10.0 and byname["ordinary_dilution"]["status"]=="CALCULATED")
ck("기타주 없음 → other/total UNKNOWN", byname["other_share_dilution"]["status"]=="UNKNOWN" and byname["total_dilution"]["status"]=="UNKNOWN")
ck("조달/시총 외부없음 → PARTIAL", byname["raise_to_mktcap"]["status"]=="UNKNOWN" and st=="PARTIAL")
row0={"nstk_ostk_cnt":"1000000","nstk_estk_cnt":"0","bfic_tisstk_ostk":"10000000","bfic_tisstk_estk":"0"}
m0={x["metric"]:x for x in MAT.compute("RIGHTS_OFFERING",row0,{},"R5",FM)[0]}
ck("기타주식 0 → total==ordinary", m0["total_dilution"]["computedValue"]==10.0)
facts=MAT.extract_facts("RIGHTS_OFFERING",{"fdpp_op":"5000000000","ic_mthn":"제3자배정","fdpp_fclt":None},FM)
ck("fdpp/ic_mthn Fact 보존", facts.get("fdpp_op")=="5000000000" and facts.get("ic_mthn")=="제3자배정")
ck("M과 방향 분리", mo[0]["direction"]=="UNKNOWN")

# 구조 위험
ck("부도 materialityStatus NOT_REQUIRED", MAT.compute("DEFAULT",{}, {},"R6",FM)[1]=="NOT_REQUIRED")
ev=N.normalize_item({"stock_code":"111111","company":"X","sector":"s","report_nm":"부도발생","rcept_no":"29990101000001","rcept_dt":"29990101","url":""}); ev["materialityStatus"]="NOT_REQUIRED"; RG.evaluate(ev)
ck("부도 → 구조 HIGH·M3·잠금", ev["structural_risk"]=="HIGH" and ev["materiality"]=="M3" and ev["new_buy_locked"])

# schema 대조
ck("영업정지 기대필드 없음 → mismatch", OD.check_schema(["rcept_no"],"BUSINESS_SUSPENSION",FM)["schema"]=="SCHEMA_MISMATCH")
ck("유상증자 필드 다 있으면 OK", OD.check_schema(["rcept_no","nstk_ostk_cnt","nstk_estk_cnt","bfic_tisstk_ostk","bfic_tisstk_estk"],"RIGHTS_OFFERING",FM)["schema"]=="OK")
ck("CB required field 누락 감지", "cvisstk_tisstk_vs" in OD.check_schema(["rcept_no","bd_fta","cv_prc","cvisstk_cnt"],"CB_ISSUE",FM).get("missing",[]))

# 일반 감사보고서 / 영업정지 과잉판정 방지
aud=N.normalize_item({"stock_code":"111111","company":"X","sector":"s","report_nm":"감사보고서","rcept_no":"29990101000002","rcept_dt":"29990101","url":""})
ck("일반 감사보고서→PERIODIC/AUDIT_REPORT(U0)", aud["family"]=="PERIODIC" and aud["type"]=="AUDIT_REPORT" and aud["urgency"]=="U0")
bs=N.normalize_item({"stock_code":"111111","company":"X","sector":"s","report_nm":"영업정지","rcept_no":"29990101000003","rcept_dt":"29990101","url":""}); bs["materialityStatus"]="UNKNOWN"; RG.evaluate(bs)
ck("영업정지 규모미확인→자동 M3 금지", bs["materiality"]=="UNKNOWN" and bs["fast_risk_defense_allowed"] and bs["structural_risk"]=="REVIEW")

# 사건별 threshold
ck("유상증자 희석 10% → M2", MAT.band_for("RIGHTS_OFFERING",mets,TH)=="M2")
row25={"nstk_ostk_cnt":"2500000","nstk_estk_cnt":"0","bfic_tisstk_ostk":"10000000","bfic_tisstk_estk":"0"}
m25=MAT.compute("RIGHTS_OFFERING",row25,{},"R7",FM)[0]
ck("유상증자 희석 25% → M3", MAT.band_for("RIGHTS_OFFERING",m25,TH)=="M3")
mb7=MAT.compute("BUSINESS_SUSPENSION",{"bsnsp_amt":"7000000000","rsl":"100000000000","sl_vs":"7.0"},{},"R8",FM)[0]
ck("영업정지 7% → M2", MAT.band_for("BUSINESS_SUSPENSION",mb7,TH)=="M2")
mb3=MAT.compute("BUSINESS_SUSPENSION",{"bsnsp_amt":"3000000000","rsl":"100000000000","sl_vs":"3.0"},{},"R9",FM)[0]
ck("영업정지 3% → M1", MAT.band_for("BUSINESS_SUSPENSION",mb3,TH)=="M1")
bw=[{"metric":"bw_shares_ratio","status":"REPORTED_ONLY","reportedValue":7.0,"computedValue":None}]
ck("BW 7% → M2", MAT.band_for("BW_ISSUE",bw,TH)=="M2")
buy=[{"metric":"buyback_to_mktcap","status":"CALCULATED","reportedValue":None,"computedValue":2.0}]
ck("자사주취득 시총대비 2% → M2", MAT.band_for("BUYBACK",buy,TH)=="M2")
only_raise=[{"metric":"raise_to_mktcap","status":"CALCULATED","reportedValue":None,"computedValue":30.0}]
ck("정책 미정 metric 임의등급 금지", MAT.band_for("RIGHTS_OFFERING",only_raise,TH)=="UNKNOWN")
ck("구형 공통 worst_band 비활성", MAT.worst_band([{"metric":"x","status":"CALCULATED","computedValue":99.0}])=="UNKNOWN")

# 라이브에서 확보된 CB/EB/자사주 필드 의미를 오프라인으로 고정
cbrow={"rcept_no":"C1","bd_fta":"10000000000","cv_prc":"2268","cvisstk_cnt":"4409171","cvisstk_tisstk_vs":"10.82","fdpp_op":"3000000000"}
cbm,cbs=MAT.compute("CB_ISSUE",cbrow,{},"C1",FM)
ck("CB 공식 잠재희석 10.82% → REPORTED_ONLY", cbm[0]["reportedValue"]==10.82 and cbm[0]["status"]=="REPORTED_ONLY" and cbs=="PARTIAL")
ck("CB 10.82% → M2(15/5)", MAT.band_for("CB_ISSUE",cbm,TH)=="M2")
ebrow={"rcept_no":"E1","bd_fta":"2372275000000","ex_prc":"523125","extg":"HD현대중공업 보통주","extg_stkcnt":"4534814","extg_tisstk_vs":"4.32"}
ebm,ebs=MAT.compute("EB_ISSUE",ebrow,{},"E1",FM)
ck("EB 교환대상 비율 4.32% 보존", ebm[0]["reportedValue"]==4.32 and ebm[0]["status"]=="REPORTED_ONLY")
ck("EB 교환비율을 자동 희석 M으로 쓰지 않음", MAT.band_for("EB_ISSUE",ebm,TH)=="UNKNOWN")
bfacts=MAT.extract_facts("BUYBACK",{"aqpln_stk_ostk":"339411","aqpln_prc_ostk":"15680788200","aq_pp":"임직원 주식보상","aq_mth":"장내 매수"},FM)
ck("자사주취득 실응답 Fact 보존", bfacts.get("aqpln_prc_ostk")=="15680788200" and bfacts.get("aq_pp")=="임직원 주식보상")
_,bst=MAT.compute("BUYBACK",{"aqpln_prc_ostk":"15680788200","aq_pp":"임직원 주식보상","aq_mth":"장내 매수"},{},"B1",FM)
ck("시총 없으면 자사주 M 추측 금지", bst=="UNKNOWN")
ck("소송은 표본없어 계속 PENDING", FM["LITIGATION"]["status"]=="PENDING_GUIDE_READ")

p=sum(1 for _,ok,_ in R if ok)
print("Wave B 오프라인 단위테스트 (실응답 schema + 사건별 threshold)\n"+"-"*60)
for n,ok,d in R: print(f"  [{'PASS' if ok else 'FAIL'}] {n}"+(f"  · {d}" if d else ""))
print("-"*60+f"\n  합계 {p}/{len(R)} PASS")
sys.exit(0 if p==len(R) else 1)
