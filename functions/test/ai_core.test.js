import assert from 'node:assert/strict';
import {
  MODEL_POLICY, AI_POLICY_VERSION, analysisFingerprint, estimateCostUsd, costFromUsageUsd,
  kstKeys, buildAnalysisPrompt, pricingIsStale, ANALYSIS_OUTPUT_SCHEMA
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

const event={schema:'event/waveB2-1',event_id:'EV-X',type:'RIGHTS_OFFERING',family:'DILUTION',claimStatus:'CONFIRMED',facts:{b:2,a:1},metrics:[{metric:'ordinary_dilution',computedValue:10}],unknowns:[],versions:[{rcept_no:'20260101000001'}]};
const f1=analysisFingerprint({event,thesis:{statement:'A',version:'1'},model:'claude-sonnet-5'});
const f2=analysisFingerprint({event:{...event,facts:{a:1,b:2}},thesis:{version:'1',statement:'A'},model:'claude-sonnet-5'});
eq(f1,f2,'key order must not change fingerprint');
const f3=analysisFingerprint({event:{...event,metrics:[{metric:'ordinary_dilution',computedValue:11}]},thesis:{statement:'A',version:'1'},model:'claude-sonnet-5'});
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
console.log(`Wave C AI core: ${tests}/${tests} PASS`);
