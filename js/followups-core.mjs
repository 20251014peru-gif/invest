// 확인·복기: UI와 분리된 상태/이력 규칙. 기존 records/checks/todos를 삭제하거나 수정하지 않는다.
export const STATES={open:'미확인',working:'확인 중',done:'완료',paused:'보류'};
export const JUDGMENTS={pending:'아직 판단 안 함',keep:'유지',change:'수정',withdraw:'철회'};
export const COMPARISONS={'':'비교 없음',same:'예상과 같음',partial:'일부 다름',different:'예상과 다름',unknown:'판단 유보'};
export const FORMAT='record-followups/1';
export const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function safeURL(s){try{const u=new URL(String(s));return /^https?:$/.test(u.protocol)?u.href:'';}catch{return '';}}
export const day=t=>new Date(t+9*3600000).toISOString().slice(0,10);
export function group(item,today){if(item.state==='done')return '완료';if(item.state==='paused')return '보류';if(!item.dueAt)return '기한 없음';return item.dueAt<today?'기한 지남':item.dueAt===today?'오늘':'예정';}
export async function stableId(key){const b=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(key));return 'fu_'+Array.from(new Uint8Array(b)).map(x=>x.toString(16).padStart(2,'0')).join('');}
export async function legacyItems(records,todos,needsReview=()=>false){
  const out=[],usedMarkers=new Set();
  for(const r of records){
    const occurrences={};
    for(const [i,c] of (r.checks||[]).entries()){
      if(!c)continue;
      const fingerprint=JSON.stringify([c.what||'',c.date||'',c.action||'',c.followUpType||'']);
      const occurrence=occurrences[fingerprint]||0;occurrences[fingerprint]=occurrence+1;
      const key=r.id+'#'+(c.id||('text:'+fingerprint+':'+occurrence));
      const keys=[r.id+'#'+(c.id||i),r.id+'#'+i];
      const markers=todos.filter(t=>keys.includes(t.dueKey));
      markers.forEach(t=>usedMarkers.add(t));
      const completed=markers.filter(t=>t.done);
      const latest=completed.slice().sort((a,b)=>(b.createdAt||0)-(a.createdAt||0))[0];
      out.push({id:await stableId(key),question:c.what||r.title||'확인할 것',dueAt:c.date||'',originalDueAt:c.date||'',expectation:c.action||'',state:completed.length?'done':'open',result:'',judgment:'pending',comparison:'',completedAt:latest?.createdAt||null,legacyCompleted:!!completed.length,sourceIds:[r.id],sourceSnapshots:[{id:r.id,title:r.title||'',url:r.link||'',kind:r.kind||''}],topics:r.topics||[],stocks:r.stocks||[],followUpType:c.followUpType||'lookup',legacy:{key,keys,index:i,check:JSON.parse(JSON.stringify(c)),markers:JSON.parse(JSON.stringify(markers))}});
    }
    if(needsReview(r))out.push({id:await stableId('review:'+r.id+':'+(r.reviewAt||r.studyStatus||'')),question:r.title||'공부노트 재검토',dueAt:r.reviewAt||'',originalDueAt:r.reviewAt||'',state:'open',result:'',expectation:'공부노트 재검토',judgment:'pending',comparison:'',sourceIds:[r.id],sourceSnapshots:[{id:r.id,title:r.title||'',kind:r.kind||''}],topics:r.topics||[],stocks:r.stocks||[],followUpType:'reread',legacy:{key:'review:'+r.id+':'+(r.reviewAt||r.studyStatus||''),reviewAt:r.reviewAt||''}});
  }
  // 원본 질문이 사라진 오래된 완료 표식도 버리지 않는다. 추측 병합 없이 독립 보존한다.
  const orphanGroups={};todos.filter(t=>t.done&&t.dueKey&&!usedMarkers.has(t)).forEach(t=>(orphanGroups[t.dueKey]||(orphanGroups[t.dueKey]=[])).push(t));
  for(const [key,markers] of Object.entries(orphanGroups)){
    const latest=markers.slice().sort((a,b)=>(b.createdAt||0)-(a.createdAt||0))[0],sourceId=key.split('#')[0];
    out.push({id:await stableId('orphan:'+key),question:latest.text||'원본을 찾을 수 없는 이전 확인',dueAt:'',originalDueAt:'',state:'done',result:'',expectation:'',judgment:'pending',comparison:'',completedAt:latest.createdAt||null,legacyCompleted:true,sourceIds:[sourceId],sourceSnapshots:[{id:sourceId,title:'이전 원본 · 질문 대응 확인 필요'}],legacy:{key,keys:[key],markers:JSON.parse(JSON.stringify(markers)),unmatched:true}});
  }
  return out;
}
export function saveTransition(current,patch,{expected,operationId,now=Date.now(),id}={}){
  if(current?.operationId===operationId&&operationId)return {item:current,repeated:true};
  if((current?.revision||0)!==expected)throw Error('CONFLICT');
  const allowed=['question','dueAt','expectation','result','judgment','comparison','changeReason','nextAction','observedChange','lesson','basisDate','links','assets','sourceIds','sourceSnapshots','parentFollowupId','topics','stocks','followUpType'];
  const clean={};for(const k of allowed)if(patch[k]!==undefined)clean[k]=patch[k];
  const state=patch.state||current?.state||'open';if(!STATES[state])throw Error('BAD_STATE');
  const item={...(current||{}),...clean,id,state};
  if(!String(item.question||'').trim())throw Error('QUESTION_REQUIRED');
  if(state==='done'&&!String(item.result||'').trim()&&!(current?.legacyCompleted&&current.state==='done'))throw Error('RESULT_REQUIRED');
  if(state==='paused'&&!String(item.result||'').trim())throw Error('PAUSE_REASON_REQUIRED');
  if((item.links||[]).some(l=>!safeURL(l.url)))throw Error('BAD_URL');
  if((item.assets||[]).some(a=>a.url&&!safeURL(a.url)))throw Error('BAD_IMAGE_URL');
  if(!JUDGMENTS[item.judgment||'pending'])throw Error('BAD_JUDGMENT');
  item.createdAt=current?.createdAt||now;item.updatedAt=now;item.revision=(current?.revision||0)+1;item.operationId=operationId;
  item.originalDueAt=current?.originalDueAt??item.dueAt??'';
  item.completedAt=state==='done'?(current?.state==='done'?current.completedAt||now:now):null;
  item.legacyCompleted=!!current?.legacyCompleted&&current.state==='done'&&state==='done'&&!item.result;
  if(new TextEncoder().encode(JSON.stringify(item)).length>750000)throw Error('TOO_LARGE');
  const {legacy,...snapshot}=item;
  return {item,review:{...snapshot,event:!current?'created':state==='done'&&current.state!=='done'?'completed':current.state==='done'&&state!=='done'?'reopened':'updated',recordedAt:now,previousRevision:current?.revision||0}};
}
export function filterItems(items,{state='undone',q='',comparison='',judgment='',today=day(Date.now())}={}){
  return items.filter(x=>state==='all'||state==='done'?state==='all'||x.state==='done':state==='paused'?x.state==='paused':x.state==='open'||x.state==='working')
    .filter(x=>!comparison||x.comparison===comparison).filter(x=>!judgment||x.judgment===judgment)
    .filter(x=>!q||[x.question,x.result,x.expectation,x.changeReason,x.observedChange,x.lesson,(x.topics||[]).join(' '),(x.links||[]).map(l=>l.url+' '+(l.title||'')).join(' '),(x.sourceSnapshots||[]).map(r=>r.title).join(' ')].join(' ').toLowerCase().includes(q.toLowerCase()))
    .sort((a,b)=>state==='done'?(b.completedAt||0)-(a.completedAt||0):['기한 지남','오늘','예정','기한 없음','보류','완료'].indexOf(group(a,today))-['기한 지남','오늘','예정','기한 없음','보류','완료'].indexOf(group(b,today))||(a.dueAt||'9999').localeCompare(b.dueAt||'9999'));
}
export function parseBackup(input){const b=typeof input==='string'?JSON.parse(input):input;if(b?.format!==FORMAT||!Array.isArray(b.items)||!Array.isArray(b.reviews))throw Error('BACKUP_FORMAT');if(new Set(b.items.map(x=>x.id)).size!==b.items.length)throw Error('DUPLICATE_ID');return b;}
