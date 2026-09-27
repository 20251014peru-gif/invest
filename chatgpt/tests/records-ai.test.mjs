import test from 'node:test';import assert from 'node:assert/strict';
import {handleRecordsAI,costNano,parseResult,makeRequest,normalizeSelection,MODEL} from '../backend/records-ai.js';
const sources=[{id:'a',title:'A',text:'수요가 증가했다.'},{id:'b',title:'B',text:'공급은 그대로다.'}];
const output={facts:[{text:'자료의 수요 증가 주장',sourceId:'a',quote:'수요가 증가했다.'}],interpretations:[{text:'공급 압박 가능성',reasoning:'수요와 공급을 함께 비교',sourceIds:['a','b'],counterargument:'자료의 시점이 다를 수 있음'}],conflicts:[],unknowns:['원출처 독립 검증 전'],nextChecks:['발표 시점 확인']};
const reply={id:'resp_test',stop_reason:'end_turn',usage:{input_tokens:1000,cache_read_input_tokens:200,cache_creation_input_tokens:0,output_tokens:100},content:[{type:'text',text:JSON.stringify(output)}]};
function harness(){
 const docs=new Map(sources.map(s=>['records/'+s.id,{title:s.title,body:s.text}]));
 let chain=Promise.resolve();
 const snap=k=>({exists:docs.has(k),data:()=>docs.get(k)});
 const ref=k=>({key:k,get:async()=>snap(k),collection:n=>col(k+'/'+n)});
 const col=k=>({doc:id=>ref(k+'/'+id),where:()=>({get:async()=>({docs:[...docs].filter(([key,v])=>key.startsWith(k+'/')&&v.schema).map(([key,v])=>({id:key.split('/').pop(),data:()=>v}))})})});
 return {docs,db:{collection:col,runTransaction(fn){const p=chain.then(async()=>{const writes=[];await fn({get:async r=>snap(r.key),set:(r,v)=>writes.push([r.key,v])});writes.forEach(([k,v])=>docs.set(k,v));});chain=p.catch(()=>{});return p;}}};
}
test('cost uses exact cache categories, missing usage remains unknown',()=>{assert.equal(costNano(reply.usage),3040000);assert.equal(costNano(null),null);assert.equal(costNano({input_tokens:3,output_tokens:1,cache_creation_input_tokens:4}),null);});
test('facts must quote stored source; interpretation needs multiple sources',()=>{assert.deepEqual(parseResult(reply,sources),output);const bad=structuredClone(reply);bad.content[0].text=JSON.stringify({...output,facts:[{text:'추측',sourceId:'a',quote:'없던 문장'}]});assert.throws(()=>parseResult(bad,sources));assert.throws(()=>normalizeSelection({recordIds:['a','a']}));assert.equal(makeRequest(sources,'질문').model,MODEL);});
test('concurrent identical calls charge once; cost survives a different client',async()=>{const h=harness();let calls=0;const args={db:h.db,uid:'owner',input:{action:'records-analyze-anthropic',recordIds:['a','b']},key:'test',fetchImpl:async()=>{calls++;return {ok:true,json:async()=>reply};}};const result=await Promise.all([handleRecordsAI(args),handleRecordsAI(args)]);assert.equal(calls,1);assert(result.some(x=>x.status==='completed'));const reused=await handleRecordsAI(args);assert.equal(calls,1);assert.equal(reused.cached,true);const cost=await handleRecordsAI({...args,input:{action:'records-costs'}});assert.equal(cost.totals.spentNano,3040000);assert.equal(cost.totals.reservedNano,0);assert.equal(cost.billed,null);assert.equal(h.docs.get('records/a').body,sources[0].text);});
test('provider timeout retains reserve and unknown count, never reports free',async()=>{const h=harness();let calls=0;const args={db:h.db,uid:'owner',input:{action:'records-analyze-anthropic',recordIds:['a','b']},key:'test',fetchImpl:async()=>{calls++;throw Error('timeout');}};await handleRecordsAI(args);await handleRecordsAI(args);assert.equal(calls,1);const cost=await handleRecordsAI({...args,input:{action:'records-costs'}});assert.equal(cost.totals.unknown,1);assert(cost.totals.reservedNano>0);});
test('invalid model output is still charged from response usage',async()=>{const h=harness(),args={db:h.db,uid:'owner',input:{action:'records-analyze-anthropic',recordIds:['a','b']},key:'test',fetchImpl:async()=>({ok:true,json:async()=>({...reply,stop_reason:'max_tokens'})})};assert.equal((await handleRecordsAI(args)).status,'failed');assert.equal((await handleRecordsAI({...args,input:{action:'records-costs'}})).totals.spentNano,3040000);});

test('Anthropic cache writes count separately and legacy OpenAI stays separate',async()=>{
 assert.equal(costNano({input_tokens:100,output_tokens:10,cache_read_input_tokens:20,cache_creation_input_tokens:50,cache_creation:{ephemeral_5m_input_tokens:30,ephemeral_1h_input_tokens:20}}),459000);
 const h=harness(),path='chatgpt_macro_private/owner/aiUsage/records_totals';h.docs.set(path,{spentNano:123456,pending:1});
 const out=await handleRecordsAI({db:h.db,uid:'owner',input:{action:'records-costs'}});assert.equal(out.totals,null);assert.equal(out.legacyOpenAI.spentNano,123456);assert.equal(out.provider,'anthropic');assert.equal(h.docs.get(path).pending,1);
});
test('request targets Anthropic Messages with correct auth and format',async()=>{
 const h=harness();await handleRecordsAI({db:h.db,uid:'owner',key:'test-key',input:{action:'records-analyze-anthropic',recordIds:['a','b']},fetchImpl:async(url,opts)=>{assert.equal(url,'https://api.anthropic.com/v1/messages');assert.equal(opts.headers['x-api-key'],'test-key');const r=JSON.parse(opts.body);assert.equal(r.model,'claude-sonnet-5');assert.equal(r.output_config.format.type,'json_schema');assert.equal(r.max_tokens,5000);assert(!('store' in r));return {ok:true,json:async()=>reply};}});
});
