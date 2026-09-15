import assert from 'node:assert/strict';
import fs from 'node:fs';
import * as core from '../lib/ai_core.js';
import * as result from '../lib/ai_result.js';

const answer = Object.fromEntries(Object.entries(core.ANALYSIS_OUTPUT_SCHEMA.properties).map(([k,r]) =>
  [k, r.type==='array'?['UNKNOWN']:r.enum?r.enum[0]:'UNKNOWN']));
const response = {stop_reason:'end_turn', content:[{type:'thinking',thinking:'ignored'}, {type:'text',text:JSON.stringify(answer)}],usage:{input_tokens:1426,output_tokens:300}};
assert.deepEqual(result.parseAnalysisOutput(response),answer);
assert.deepEqual(result.parseAnalysisOutput({...response,content:[{type:'text',text:'```json\n'+JSON.stringify(answer)+'\n```'}]}),answer);
const json=JSON.stringify(answer);
assert.deepEqual(result.parseAnalysisOutput({...response,content:[{type:'text',text:json.slice(0,45)},{type:'text',text:json.slice(45)}]}),answer);
for (const stop_reason of ['max_tokens','refusal','pause_turn',null]) assert.throws(()=>result.parseAnalysisOutput({...response,stop_reason}),result.AnalysisParseError);
for (const text of ['', '{}', 'null', '[]', json+' trailing', JSON.stringify({...answer,thesisImpact:3}),JSON.stringify({...answer,keyRisks:[3]}),JSON.stringify({...answer,extra:true})]) {
  assert.throws(()=>result.parseAnalysisOutput({...response,content:[{type:'text',text}]}),result.AnalysisParseError);
}
assert.deepEqual(result.firestoreSafe({missing:undefined,nested:{a:undefined,b:NaN},list:[undefined,Infinity,[1]],__proto__:null}),{nested:{b:null},list:[null,null,{items:[1]}]});
const circular={}; circular.self=circular;
assert.throws(()=>result.firestoreSafe(circular));
const sdkUsage={...response.usage,cache_creation:{ephemeral_5m_input_tokens:undefined}};

// Execute the real callable handler with in-memory Firestore and a fake Anthropic
// constructor. No real SDK is imported and network access always throws.
const source=fs.readFileSync(new URL('../index.js',import.meta.url),'utf8')
  .replace(/^import[\s\S]*?;\r?\n/gm,'').replace(/export const /g,'const ');
class HttpsError extends Error { constructor(code,message,details){super(message);this.code=code;this.details=details;} }
const sentinel={serverTimestamp:true};
function safe(v) {
  assert.notEqual(v,undefined,'Firestore rejects undefined');
  if(v && typeof v==='object') for(const x of Object.values(v)) safe(x);
}
function harness({reply={...response,usage:sdkUsage},failAnalysis=false,lostSettlement=false,failSettlement=false,providerFail=false,lostAnalysis=false,noEvidence=false}={}) {
  const docs=new Map([['ai_users/u',{enabled:true}]]); let calls=0, counts=0, next=0, lost=false, chain=Promise.resolve();
  const db={collection(name){return {doc(id=String(++next)){const key=name+'/'+id;return {id,key,
    async get(){return snap(key);},async set(v,opt){safe(v);if(name==='event_ai_analysis' && v.status==='success' && failAnalysis) throw Error('storage unavailable');write(key,v,opt);if(name==='event_ai_analysis' && v.status==='success' && lostAnalysis)throw Error('lost acknowledgement');}};}};},
    runTransaction(fn){const run=chain.then(async()=>{const writes=[];const tx={get:async ref=>snap(ref.key),set(ref,v,opt){safe(v);writes.push([ref.key,v,opt]);}};const value=await fn(tx);const settles=writes.some(([k,v])=>k.startsWith('ai_usage/') && v.costStatus);if(settles&&failSettlement)throw Error('storage unavailable');for(const w of writes)write(...w);if(settles&&lostSettlement&&!lost){lost=true;throw Error('lost acknowledgement');}return value;});chain=run.catch(()=>{});return run;}};
  function snap(key){return {exists:docs.has(key),data:()=>docs.get(key)};}
  function write(key,v,opt){docs.set(key,opt?.merge?{...docs.get(key),...v}:v);}
  class Anthropic {constructor(options){assert.equal(options.maxRetries,0);this.messages={countTokens:async()=>{counts++;return {input_tokens:1426};},create:async()=>{calls++;if(providerFail)throw Error('provider unavailable');return reply;}};}}
  const event={schema:'event/waveB2-1',event_id:'EV-1',company:'Test',facts:noEvidence?{}:{revenue:100},date:'20260915',materiality:'UNKNOWN'};
  const pricing={verifiedAt:'2026-09-15',models:{'claude-sonnet-5':{inputPerMillion:2,outputPerMillion:10}}};
  const bindings={...core,...result,fs:{existsSync:()=>true,readFileSync:()=>JSON.stringify(pricing)},path:{dirname:()=>'',join:()=>''},fileURLToPath:()=>'',Anthropic,initializeApp:()=>{},getFirestore:()=>db,FieldValue:{serverTimestamp:()=>sentinel},onCall:(_,fn)=>fn,HttpsError,defineSecret:()=>({value:()=> 'FAKE_TEST_KEY'}),logger:{error:()=>{}},fetch:()=>{throw Error('network forbidden');}};
  const text=source.replace('import.meta.url',"'file:///test/index.js'")+
    '\nrawCache.set("facts/events/index.json",{at:Date.now(),value:{events:[testEvent]}});'+
    '\nrawCache.set("facts/events/2026-09-15.json",{at:Date.now(),value:{events:[testEvent]}});return {analyzeEvent,estimateEventAnalysis};';
  const handler=new Function(...Object.keys(bindings),'testEvent',text)(...Object.values(bindings),event);
  return {estimate:()=>handler.estimateEventAnalysis({auth:{uid:'u'},data:{eventId:'EV-1'}}),run:()=>handler.analyzeEvent({auth:{uid:'u'},data:{eventId:'EV-1'}}),docs,calls:()=>calls,counts:()=>counts};
}
const total=(h,field)=>[...h.docs].filter(([k])=>k.startsWith('ai_cost_')).map(([,v])=>v[field]||0);
const expected=core.costFromUsageUsd(response.usage,{inputPerMillion:2,outputPerMillion:10});
const good=harness();
assert.equal((await good.run()).analysis.status,'success');
assert.deepEqual(total(good,'spentUsd'),[expected,expected]);
assert.deepEqual(total(good,'reservedUsd'),[0,0]);
assert.equal((await good.run()).cacheHit,true);assert.equal(good.calls(),1);
assert.equal([...good.docs].find(([k])=>k.startsWith('ai_usage/'))[1].reservedMaxCostUsd,0.042852);
const concurrent=harness();await Promise.allSettled([concurrent.run(),concurrent.run()]);assert.equal(concurrent.calls(),1);
for (const options of [{lostSettlement:true},{lostAnalysis:true},{failAnalysis:true},{failSettlement:true},{providerFail:true},{reply:{...response,content:[{type:'text',text:'not JSON'}]}},{reply:{...response,stop_reason:'max_tokens'}}]) {
  const h=harness(options);let error;
  try {await h.run();} catch(e){error=e;}
  if(options.lostSettlement) {assert.equal(error,undefined);}
  else {
    assert.equal(error.details.failureStage,options.providerFail?'provider':options.reply?'parse':'persistence');
    if(options.failSettlement)assert.equal(error.details.costStatus,'RESERVED');
  }
  if(options.providerFail) {assert.deepEqual(total(h,'spentUsd'),[0,0]);assert.ok(total(h,'unreconciledUsd').every(x=>x>0));}
  else if(!options.failSettlement) assert.deepEqual(total(h,'spentUsd'),[expected,expected]);
  await h.run().catch(()=>{});assert.equal(h.calls(),1,'failure/retry must not trigger another paid call');
}
console.log('Wave C result/gateway regression: PASS (mock provider only)');

const noEvidence=harness({noEvidence:true});const free=await noEvidence.run();assert.equal(free.apiCalled,false);assert.equal(free.analysis.status,'insufficient_data');assert.equal(noEvidence.calls(),0);assert.equal(noEvidence.counts(),0);assert.equal(noEvidence.docs.size,1);

const prepared=harness();const estimate=await prepared.estimate();assert.equal(estimate.canAnalyze,true);assert.equal(estimate.readiness.hasThesis,false);assert.equal(prepared.calls(),0);const emptyEstimate=await noEvidence.estimate();assert.equal(emptyEstimate.canAnalyze,false);assert.equal(noEvidence.counts(),0);
