import assert from 'node:assert/strict';
import {
  MODEL_POLICY, analysisFingerprint, estimateCostUsd, costFromUsageUsd,
  kstKeys, buildAnalysisPrompt, pricingIsStale, ANALYSIS_OUTPUT_SCHEMA
} from '../lib/ai_core.js';

const pricing={verifiedAt:'2026-09-15',staleWarnAfterDays:90,models:{
  'claude-sonnet-5':{inputPerMillion:2,outputPerMillion:10,cacheReadPerMillion:.2,cache5mWritePerMillion:2.5}
}};
const price=pricing.models['claude-sonnet-5'];
assert.equal(estimateCostUsd(4000,1000,price),0.018);
assert.equal(costFromUsageUsd({input_tokens:4000,output_tokens:1000},price),0.018);
assert.equal(costFromUsageUsd({input_tokens:4000,output_tokens:1000,cache_read_input_tokens:1000},price),0.0182);

const event={schema:'event/waveB2-1',event_id:'EV-X',type:'RIGHTS_OFFERING',family:'DILUTION',claimStatus:'CONFIRMED',facts:{b:2,a:1},metrics:[{metric:'ordinary_dilution',computedValue:10}],unknowns:[],versions:[{rcept_no:'20260101000001'}]};
const f1=analysisFingerprint({event,thesis:{statement:'A',version:'1'},model:'claude-sonnet-5'});
const f2=analysisFingerprint({event:{...event,facts:{a:1,b:2}},thesis:{version:'1',statement:'A'},model:'claude-sonnet-5'});
assert.equal(f1,f2,'key order must not change fingerprint');
const f3=analysisFingerprint({event:{...event,metrics:[{metric:'ordinary_dilution',computedValue:11}]},thesis:{statement:'A',version:'1'},model:'claude-sonnet-5'});
assert.notEqual(f1,f3,'metric change must invalidate cache');

const p=buildAnalysisPrompt(event,{statement:'핵심 가설'});
assert.match(p.system,/must never unlock G6/);
assert.match(p.user,/EVENT_DATA/);
assert.equal(MODEL_POLICY.analysis.model,'claude-sonnet-5');
assert.equal(ANALYSIS_OUTPUT_SCHEMA.additionalProperties,false);
assert.deepEqual(kstKeys(new Date('2026-09-14T16:00:00Z')),{day:'2026-09-15',month:'2026-09'});
assert.equal(pricingIsStale(pricing,new Date('2026-09-20T00:00:00Z')),false);
assert.equal(pricingIsStale(pricing,new Date('2027-01-01T00:00:00Z')),true);
console.log('Wave C AI core: 10/10 PASS');
