import {REV,hash,validate,chunks,marks,stage,reservation,actualCost,provider,read,write} from './engine.mjs';
const json=(data,status=200)=>Response.json(data,{status,headers:{'cache-control':'no-store','x-content-type-options':'nosniff'}});
const month=()=>new Date().toISOString().slice(0,7);
function checkLedger(l){if(!l||!Number.isSafeInteger(l.spent)||!Number.isSafeInteger(l.held)||l.spent<0||l.held<0)throw Error('비용 장부 손상');return l;}
const view=j=>({id:j.id,title:j.input.title,channel:j.input.channel,status:j.status,step:j.step,costs:j.costs,error:j.error,created:j.created,synthetic:j.synthetic,updateNote:j.input.updateNote});
export default {
  async fetch(req,env){
    const url=new URL(req.url);
    if(url.pathname.startsWith('/api/')){
      if(!env.APP_TOKEN||env.APP_TOKEN.length<32)return json({error:'접근 코드 설정 필요'},503);
      const supplied=req.headers.get('authorization')||'';
      if(await hash(supplied)!==await hash('Bearer '+env.APP_TOKEN))return json({error:'접근 코드를 확인하세요.'},401);
      if(req.headers.get('origin')&&req.headers.get('origin')!==url.origin)return json({error:'다른 사이트의 요청은 허용하지 않습니다.'},403);
      return env.JOBS.get(env.JOBS.idFromName('personal-account-v1')).fetch(req);
    }
    const response=await env.ASSETS.fetch(req);const h=new Headers(response.headers);
    h.set('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-src 'self'; object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'");
    h.set('X-Content-Type-Options','nosniff');h.set('Referrer-Policy','no-referrer');
    return new Response(response.body,{status:response.status,headers:h});
  }
};
export class SummaryJobs {
  constructor(ctx,env){this.ctx=ctx;this.db=ctx.storage;this.env=env;}
  async fetch(req){
    const path=new URL(req.url).pathname;
    try{
      if(req.method==='POST'&&/^\/api\/jobs\/[a-f0-9]{64}\/resume$/.test(path))return this.ctx.blockConcurrencyWhile(()=>this.db.transaction(async tx=>{
        const id=path.split('/')[3],job=await read(tx,'job:'+id);
        if(!job||!['blocked','failed'].includes(job.status)||await tx.get('halt'))return json({error:'재개할 수 없는 작업입니다. 확인 필요 상태는 재호출하지 않습니다.'},409);
        job.status='queued';job.error=null;await write(tx,'job:'+id,job);await tx.setAlarm(Date.now()+1000);return json(view(job));
      }));
      if(req.method==='GET'&&path==='/api/jobs'){
        const ids=await this.db.get('index')||[];
        const jobs=await Promise.all(ids.slice(-100).reverse().map(id=>read(this.db,'job:'+id)));
        return json({jobs:jobs.map(view),ledger:await this.db.get('ledger:'+month())||{spent:0,held:0},limit:Number(this.env.MONTHLY_LIMIT_USD)||0,live:this.env.LIVE_AI==='1',halted:!!await this.db.get('halt')});
      }
      if(req.method==='GET'&&/^\/api\/jobs\/[a-f0-9]{64}$/.test(path)){
        const job=await read(this.db,'job:'+path.split('/').pop());if(!job)return json({error:'작업 없음'},404);
        return json({...view(job),input:job.input,marks:job.marks,summary:job.summaryKey?await read(this.db,job.summaryKey):null,note:job.noteKey?await read(this.db,job.noteKey):null,completeness:'전체 내용 완전성 미검증'});
      }
      if(req.method==='POST'&&path==='/api/jobs'){
        if(!req.headers.get('content-type')?.startsWith('application/json'))return json({error:'JSON 필요'},415);
        // Stream limit also covers clients that omit Content-Length.
        const reader=req.body?.getReader();if(!reader)return json({error:'빈 요청'},400);let size=0,parts=[];
        while(true){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>500000){await reader.cancel();return json({error:'입력 크기 초과'},413);}parts.push(value);}
        const bytes=new Uint8Array(size);let offset=0;for(const p of parts){bytes.set(p,offset);offset+=p.length;}
        const p=validate(JSON.parse(new TextDecoder().decode(bytes)));
        const id=await hash([REV,this.env.LIVE_AI==='1',p]);
        return this.ctx.blockConcurrencyWhile(()=>this.db.transaction(async tx=>{
          const existing=await read(tx,'job:'+id);if(existing)return json({...view(existing),reused:true});
          const ids=await tx.get('index')||[];
          if(ids.length>=100)return json({error:'보관 한도 100개입니다. 내보내기 후 저장 정책을 점검하세요.'},429);
          if(await tx.get('halt'))return json({error:'사용량 확인이 필요한 작업이 있습니다. 추가 호출을 중단했습니다.'},409);
          const all=await Promise.all(ids.map(i=>read(tx,'job:'+i)));if(all.filter(j=>['queued','running'].includes(j.status)).length>=10)return json({error:'대기 한도 10개'},429);
          const raw=p.transcript,rawParts=chunks(raw);delete p.transcript;
          const job={id,input:p,created:Date.now(),date:new Date().toISOString().slice(0,10),status:'queued',costs:[],profile:null,chunkIndex:0,chunkKeys:[],rawKeys:[],digestKeys:[],smallModel:p.economy?'claude-haiku-4-5-20251001':'claude-sonnet-4-6',marks:marks(p.timeline),preview:raw.slice(0,8000),synthetic:this.env.LIVE_AI!=='1'};
          for(let i=0;i<rawParts.length;i++){const key='raw:'+id+':'+i;await write(tx,key,rawParts[i]);job.rawKeys.push(key);}
          if(raw.length>18000)job.chunkKeys=job.rawKeys;
          const previous=all.filter(x=>x.summaryKey&&x.input.channel===p.channel&&p.publishDate&&x.input.publishDate<p.publishDate).sort((a,b)=>b.input.publishDate.localeCompare(a.input.publishDate))[0];
          job.previous=previous?.summaryKey||null;
          job.history=all.filter(x=>x.summaryKey&&x.input.channel===p.channel).sort((a,b)=>a.input.publishDate.localeCompare(b.input.publishDate)).slice(-10).map(x=>({key:x.summaryKey,date:x.input.publishDate,title:x.input.title}));
          await write(tx,'job:'+id,job);await tx.put('index',[...ids,id]);await tx.setAlarm(Date.now()+1000);return json(view(job),202);
        }));
      }
      return json({error:'없는 경로'},404);
    }catch{return json({error:'입력 또는 저장 상태를 확인하세요.'},400);}
  }
  async alarm(){
    const ids=await this.db.get('index')||[];
    for(const id of ids){
      const j=await read(this.db,'job:'+id);
      if(j.status==='running'){
        await this.db.transaction(async tx=>{j.status='uncertain';j.error='응답 또는 사용량 확인 필요. 자동 재호출하지 않습니다.';await write(tx,'job:'+id,j);await tx.put('halt',true);});return;
      }
    }
    if(await this.db.get('halt'))return;
    let job;for(const id of ids){const j=await read(this.db,'job:'+id);if(j.status==='queued'){job=j;break;}}
    if(!job)return;
    try{await this.advance(job);}catch(e){await this.db.put('halt',true);throw e;}finally{
      if(!await this.db.get('halt')){
        for(const id of await this.db.get('index')||[]){if((await read(this.db,'job:'+id)).status==='queued'){await this.db.setAlarm(Date.now()+1000);break;}}
      }
    }
  }
  async advance(j){
    if(!j.synthetic&&this.env.LIVE_AI!=='1'){j.status='blocked';j.error='실제 AI 모드가 꺼져 있습니다.';await this.db.transaction(tx=>write(tx,'job:'+j.id,j));return;}
    const s=stage(j);if(!s){j.status='succeeded';j.preview='';await this.db.transaction(tx=>write(tx,'job:'+j.id,j));return;}
    if(s.kind==='chunk')s.user=await read(this.db,j.chunkKeys[j.chunkIndex]);
    if(s.kind==='summary'){
      const source=await Promise.all((j.chunkKeys.length?j.digestKeys:j.rawKeys).map(k=>read(this.db,k)));
      const prev=j.previous?await read(this.db,j.previous):'';
      s.user=`오늘 날짜: ${j.date} UTC\n영상 게시일: ${j.input.publishDate||'미확인'}\n영상 제목: ${j.input.title}\n채널: ${j.input.channel}\n직전 요약:\n${prev||'없음'}\n[스크립트/구간별 정리]\n${source.join('\n\n')}`;
    }
    if(s.kind==='note'){
      const history=await Promise.all(j.history.map(async x=>`[${x.date} ${x.title}]\n${await read(this.db,x.key)}`));
      s.user=`최근 최대 10편과 이번 요약으로 판단노트를 갱신하세요. 전체 채널 기록은 아닙니다.\n${history.join('\n').slice(-60000)}\n[이번 요약]\n${await read(this.db,j.summaryKey)}`;
    }
    const key='cache:'+await hash([REV,j.synthetic,s.kind,s.model,s.system,s.kind==='profile'?j.input.channel:s.user]);
    const cached=await read(this.db,key);
    if(cached!==undefined){await this.complete(j,s,key,cached,0,true);return;}
    const amount=j.synthetic?0:reservation(s),period=month();
    const allowed=await this.db.transaction(async tx=>{
      const ledger=checkLedger(await tx.get('ledger:'+period)||{spent:0,held:0});
      const limit=Number(this.env.MONTHLY_LIMIT_USD)*1e6;
      if(!j.synthetic&&(!Number.isFinite(limit)||limit<=0||ledger.spent+ledger.held+amount>limit||!this.env.ANTHROPIC_API_KEY)){
        j.status='blocked';j.error='월 비용 한도 또는 API 키 설정을 확인하세요. 실제 호출 전 중단했습니다.';await write(tx,'job:'+j.id,j);return false;
      }
      ledger.held+=amount;j.status='running';j.step=s.kind;j.reserved=amount;j.period=period;
      await tx.put('ledger:'+period,ledger);await write(tx,'job:'+j.id,j);return true;
    });if(!allowed)return;
    try{
      const result=await provider(s,{...this.env,LIVE_AI:j.synthetic?'0':'1'});
      const cost=j.synthetic?0:actualCost(s,result.usage);
      if(cost>amount)throw Error('예약액 초과');
      // Account for paid truncated/malformed output before rejecting it.
      let text=result.text.replace(/```(?:html|json)?/g,'').trim();
      let valid=!!text&&!result.truncated;
      if(s.kind==='profile'){try{text=JSON.parse(text);valid=valid&&Array.isArray(text.출력섹션);}catch{valid=false;}}
      await this.db.transaction(async tx=>{
        const ledger=checkLedger(await tx.get('ledger:'+period));ledger.held-=amount;ledger.spent+=cost;checkLedger(ledger);
        await tx.put('ledger:'+period,ledger);
        if(valid){await write(tx,key,text);await this.complete(j,s,key,text,cost,false,tx);}
        else{j.status='failed';j.error='AI 출력이 비었거나 잘렸습니다. 비용은 기록했으며 자동 재호출하지 않습니다.';j.costs.push({stage:s.kind,model:s.model,microUsd:cost,cached:false});await write(tx,'job:'+j.id,j);}
      });
    }catch{
      await this.db.transaction(async tx=>{j.status='uncertain';j.error='AI 응답·사용량·저장 확인 실패. 예약액을 유지하고 추가 호출을 중단했습니다.';await write(tx,'job:'+j.id,j);await tx.put('halt',true);});
    }
  }
  async complete(j,s,key,text,cost,cached,tx){
    const apply=async store=>{
      if(s.kind==='profile')j.profile=text;
      if(s.kind==='chunk'){j.digestKeys.push(key);j.chunkIndex++;}
      if(s.kind==='summary')j.summaryKey=key;
      if(s.kind==='note')j.noteKey=key;
      j.costs.push({stage:s.kind,model:s.model,microUsd:cost,cached});j.status=stage(j)?'queued':'succeeded';j.step=s.kind;
      await write(store,'job:'+j.id,j);
    };if(tx)await apply(tx);else await this.db.transaction(apply);
  }
}
