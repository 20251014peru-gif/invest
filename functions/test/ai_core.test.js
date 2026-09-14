import assert from 'node:assert/strict';
import {
  MODEL_POLICY, AI_POLICY_VERSION, analysisFingerprint, estimateCostUsd, costFromUsageUsd,
  kstKeys, buildAnalysisPrompt, pricingIsStale, ANALYSIS_OUTPUT_SCHEMA, cleanThesis, decisionPolicy
} from '../lib/ai_core.js';

let tests=0;
const eq=(a,b,msg)=>{assert.equal(a,b,msg);tests++;};
const neq=(a,b,msg)=>{assert.notEqual(a,b,msg);tests++;};
const match=(a,b,msg)=>{assert.match(a,b,msg);tests++;};
const deep=(a,b,msg)=>{assert.deepEqual(a,b,msg);tests++;};

const pricing={verifiedAt:'2026-09-15',staleWarnAfterDays:90,models:{
  'claude-sonnet-5':{inputPerMillion:2,outputPerMillion:10,cacheReadPerMillion:.2,cache5mWritePerMillion:2.5}
}};
const price=pricing.models['claude-sonnet-5'];
eq(estimateCostUsd(4000,1000,price),0.018);
eq(costFromUsageUsd({input_tokens:4000,output_tokens:1000},price),0.018);
eq(costFromUsageUsd({input_tokens:4000,output_tokens:1000,cache_read_input_tokens:1000},price),0.0182);

const event={schema:'event/waveB2-1',event_id:'EV-X',type:'RIGHTS_OFFERING',family:'DILUTION',claimStatus:'CONFIRMED',materiality:'M2',materialityStatus:'CALCULATED',facts:{b:2,a:1},metrics:[{metric:'ordinary_dilution',computedValue:10,status:'CALCULATED'}],unknowns:[],versions:[{rcept_no:'20260101000001'}]};
const f1=analysisFingerprint({event,thesis:{statement:'A',version:'1'},model:'claude-sonnet-5'});
const f2=analysisFingerprint({event:{...event,facts:{a:1,b:2}},thesis:{version:'1',statement:'A'},model:'claude-sonnet-5'});
eq(f1,f2,'key order must not change fingerprint');
const f3=analysisFingerprint({event:{...event,metrics:[{metric:'ordinary_dilution',computedValue:11,status:'CALCULATED'}]},thesis:{statement:'A',version:'1'},model:'claude-sonnet-5'});
neq(f1,f3,'metric change must invalidate cache');
const f4=analysisFingerprint({event,thesis:{statement:'A',version:'1'},model:'claude-sonnet-5',policyVersion:'different-policy'});
neq(f1,f4,'AI policy change must invalidate cache');

const p=buildAnalysisPrompt(event,{statement:'핵심 가설'});
match(p.system,/must never unlock G6/);
match(p.user,/EVENT_DATA/);
eq(MODEL_POLICY.analysis.model,'claude-sonnet-5');
eq(MODEL_POLICY.analysis.effort,'medium');
eq(MODEL_POLICY.analysis.maxTokens,4000);
eq(MODEL_POLICY.deep.effort,'high');
eq(MODEL_POLICY.deep.maxTokens,6000);
eq(MODEL_POLICY.routine.effort,null,'Haiku 4.5 must not receive effort');
match(AI_POLICY_VERSION,/^ai-policy-/);
eq(ANALYSIS_OUTPUT_SCHEMA.additionalProperties,false);
deep(kstKeys(new Date('2026-09-14T16:00:00Z')),{day:'2026-09-15',month:'2026-09'});
eq(pricingIsStale(pricing,new Date('2026-09-20T00:00:00Z')),false);
eq(pricingIsStale(pricing,new Date('2027-01-01T00:00:00Z')),true);

const legacyStock={
  name:'테스트전자',status:'보유',
  customFields:[
    {label:'매수사유',value:'AI 수요 성장'},
    {label:'핵심가정',value:'마진 개선 지속'},
    {label:'반증조건',value:'마진 2분기 연속 하락'},
    {label:'촉매',value:'신제품 양산'},
    {label:'리스크',value:'고객 집중'},
    {label:'재평가시점',value:'2026-12'}
  ],
  thesisLog:[{date:'2026-09-01',text:'초기 관찰'},{date:'2026-09-15',text:'가정 유지'}]
};
const lt=cleanThesis(legacyStock);
eq(lt.thesisId,'테스트전자');
match(lt.statement,/매수사유: AI 수요 성장/);
match(lt.statement,/핵심가정: 마진 개선 지속/);
match(lt.statement,/2026-09-15 가정 유지/);
deep(lt.confirmationConditions,['핵심가정: 마진 개선 지속','촉매: 신제품 양산']);
deep(lt.invalidationConditions,['반증조건: 마진 2분기 연속 하락','리스크: 고객 집중']);
eq(lt.expectedHorizon,'2026-12');
eq(lt.version,'2026-09-15');

// G6: server policy is authoritative, not the browser UI.
eq(decisionPolicy(event,'BUY',false).reason,'RISK_REVIEW_REQUIRED');
eq(decisionPolicy(event,'BUY',true).ok,true);
eq(decisionPolicy({...event,claimStatus:'UNCONFIRMED'},'BUY',true).reason,'AGGRESSIVE_DECISION_LOCKED');
eq(decisionPolicy({...event,materiality:'UNKNOWN',materialityStatus:'UNKNOWN'},'ADD',true).reason,'AGGRESSIVE_DECISION_LOCKED');
eq(decisionPolicy({...event,metrics:[{metric:'x',status:'CONFLICT'}]},'BUY',true).reason,'AGGRESSIVE_DECISION_LOCKED');
eq(decisionPolicy({...event,claimStatus:'UNCONFIRMED',materiality:'UNKNOWN',materialityStatus:'UNKNOWN'},'SELL',true).ok,true);
eq(decisionPolicy(event,'INVALID',true).reason,'INVALID_DECISION');

console.log(`Wave C AI core: ${tests}/${tests} PASS`);
