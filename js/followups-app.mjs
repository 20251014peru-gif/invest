import * as C from './followups-core.mjs';
import {makeFollowupStore} from './followups-store.mjs?v=7.30.0.1';
const uid=()=>crypto.randomUUID();
const errorText=e=>({CONFLICT:'다른 기기에서 변경됐습니다. 입력은 그대로 두고, 새로 열어 최신 내용과 비교해 주세요.',RESULT_REQUIRED:'확인 결과를 한 줄 적어 주세요.',QUESTION_REQUIRED:'확인할 질문을 적어 주세요.',PAUSE_REASON_REQUIRED:'보류 이유를 결과 칸에 적어 주세요.',BAD_URL:'근거 링크는 http 또는 https 주소로 넣어 주세요.',TOO_LARGE:'내용이 너무 큽니다. 후속 확인으로 나눠 주세요.',IMAGE_SIZE:'사진은 한 장당 8MB까지 가능합니다.',IMAGE_TYPE:'PNG·JPG·GIF·WebP 사진을 선택해 주세요.'}[e.message]||'저장소 연결을 확인하고 다시 시도해 주세요. ('+(e.code||e.message)+')');
const button=(text,action,cls='')=>'<button type="button" class="fu-button '+cls+'" data-fu="'+action+'">'+text+'</button>';
const options=(map,value)=>Object.entries(map).map(([k,v])=>'<option value="'+C.esc(k)+'"'+(value===k?' selected':'')+'>'+C.esc(v)+'</option>').join('');
const field=(label,id,value,type='text')=>'<label class="fu-field">'+label+(type==='textarea'?'<textarea id="'+id+'" rows="3">'+C.esc(value)+'</textarea>':'<input id="'+id+'" type="'+type+'" value="'+C.esc(value)+'">')+'</label>';
const stamp=t=>t?new Date(t).toLocaleString('ko-KR',{timeZone:'Asia/Seoul',hour12:false}):'';
function download(data,name){const u=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=u;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(u),30000);}
async function dataURL(blob){return new Promise((ok,no)=>{const r=new FileReader();r.onload=()=>ok(r.result);r.onerror=no;r.readAsDataURL(blob);});}
export function init(bridge){
  const store=makeFollowupStore(bridge.db,bridge.storage);
  let items=[],ready=false,loading=null,failure='',state='undone',comparison='',judgment='',page=1,selection=new Set(),sig='',unsubscribe=null;
  let active=null,dirty=false,busy=false,assets=[],op=null,editingSources=[],parentId='',draftKey='';
  const overlay=document.createElement('div');overlay.id='followupModal';overlay.className='ovwrap';overlay.setAttribute('role','dialog');overlay.setAttribute('aria-modal','true');overlay.setAttribute('aria-label','확인·복기');
  overlay.innerHTML='<div class="modal fu-modal"><div class="mhd"><b>🔎 확인·복기</b><button class="x" data-fu="close" aria-label="닫기">✕</button></div><div class="mbody" id="fuBody"></div><div class="mfoot fu-foot">'+button('닫기','close')+button('저장','save')+button('보류','pause')+button('저장하고 완료','complete','primary')+'</div></div>';
  document.body.appendChild(overlay);overlay.addEventListener('input',()=>{dirty=true;op=null;draft();});overlay.addEventListener('change',()=>{dirty=true;op=null;draft();});
  const $=id=>overlay.querySelector('#'+id);
  function changed(){bridge.changed?.();}
  async function start(){
    if(loading)return loading;
    loading=(async()=>{failure='';
      const snap=await bridge.db.collection('records').get({source:'server'});
      const source=snap.docs.map(d=>({id:d.id,...d.data()}));
      const nextSig=JSON.stringify(source.map(r=>[r.id,r.checks,r.reviewAt,r.studyStatus]));
      if(sig!==nextSig){await store.migrate(source,bridge.studyNeedsReview);sig=nextSig;}
      items=await store.all();ready=true;
      if(!unsubscribe)unsubscribe=bridge.db.collection('record_followups').onSnapshot(s=>{items=s.docs.map(d=>({id:d.id,...d.data()}));changed();},e=>{failure=errorText(e);changed();});
      changed();
    })().catch(e=>{failure=errorText(e);ready=false;changed();throw e;}).finally(()=>{loading=null;});
    return loading;
  }
  function cardRow(x,withSelect=true){
    const completed=x.state==='done',label=completed?(x.completedAt?stamp(x.completedAt)+' 완료':'기존 완료'):x.dueAt?(x.dueAt+' · '+C.group(x,C.day(Date.now()))):C.group(x,C.day(Date.now()));
    return '<div class="fu-row">'+(withSelect?'<input type="checkbox" data-select="'+C.esc(x.id)+'" aria-label="정리에 포함"'+(selection.has(x.id)?' checked':'')+'>':'')+'<button class="fu-open" type="button" data-open-fu="'+C.esc(x.id)+'"><b>'+C.esc(x.question)+'</b><span>'+C.esc(completed?(x.result||'기존 완료 · 결과 미기록'):(x.result||x.expectation||'확인 결과를 남겨 주세요'))+'</span></button><div class="fu-row-status"><strong>'+C.STATES[x.state]+'</strong><small>'+C.esc(label)+'</small>'+(completed?'<small>판단: '+C.esc(C.JUDGMENTS[x.judgment]||'아직 판단 안 함')+'</small>':'')+'</div></div>';
  }
  function render(host,q=''){
    if(!ready){host.innerHTML='<div class="fu-loading">'+C.esc(failure||'전체 기간 완료 기록을 확인하는 중입니다…')+(failure?button('다시 연결','refresh'):'')+'</div>';bindList(host);return;}
    const filtered=C.filterItems(items,{state,q,comparison,judgment}),shown=filtered.slice(0,page*50);
    host.innerHTML='<div class="fu-listbar"><div>'+[['undone','미완료'],['done','완료·복기'],['paused','보류'],['all','전체']].map(([k,n])=>'<button class="fu-button '+(state===k?'selected':'')+'" data-state="'+k+'">'+n+'</button>').join('')+'</div><span>'+filtered.length+'건</span>'+button('＋ 확인할 질문','new','primary')+button('새로고침','refresh')+'<details class="fu-filter"><summary>필터·백업</summary><label>예상 비교 <select data-filter="comparison">'+options(C.COMPARISONS,comparison)+'</select></label><label>판단 변화 <select data-filter="judgment">'+options({'':'전체',...C.JUDGMENTS},judgment)+'</select></label>'+button('전체 확인 기록 백업','export')+button('확인 기록 복원','restore')+'</details></div>'
      +(selection.size?'<div class="fu-selection">'+selection.size+'개 선택 '+button('공부노트로 모아 정리','synthesize')+'</div>':'')
      +'<div class="fu-list">'+(shown.length?shown.map(x=>cardRow(x)).join(''):'<p class="fu-muted">해당하는 확인 기록이 없습니다.</p>')+'</div>'+(shown.length<filtered.length?button('50개 더 보기','more'):'');
    bridge.count?.(filtered.length);bindList(host);
  }
  function bindList(host){
    host.querySelectorAll('[data-open-fu]').forEach(b=>b.onclick=()=>open(b.dataset.openFu));
    host.querySelectorAll('[data-state]').forEach(b=>b.onclick=()=>{state=b.dataset.state;page=1;selection.clear();changed();});
    host.querySelectorAll('[data-select]').forEach(b=>b.onchange=()=>{b.checked?selection.add(b.dataset.select):selection.delete(b.dataset.select);changed();});
    host.querySelectorAll('[data-filter]').forEach(b=>b.onchange=()=>{if(b.dataset.filter==='comparison')comparison=b.value;else judgment=b.value;page=1;changed();});
    host.querySelectorAll('[data-fu]').forEach(b=>b.onclick=()=>listAction(b.dataset.fu));
  }
  async function listAction(action){
    try{if(action==='new')await open();if(action==='refresh')await start();if(action==='more'){page++;changed();}if(action==='export')await exportAll();if(action==='restore')restoreChoose();if(action==='synthesize')await synthesize();}catch(e){bridge.toast(errorText(e));}
  }
  function sourceSnapshots(ids){return ids.map(id=>{const r=bridge.records().find(x=>x.id===id);return {id,title:r?.title||'원본 없음',kind:r?.kind||'',url:r?.link||''};});}
  function collect(){return {question:$('fuQuestion').value.trim(),dueAt:$('fuDue').value,expectation:$('fuExpected').value,result:$('fuResult').value.trim(),judgment:$('fuJudgment').value,comparison:$('fuComparison').value,changeReason:$('fuReason').value,nextAction:$('fuNext').value,observedChange:$('fuObserved').value,lesson:$('fuLesson').value,basisDate:$('fuBasis').value,links:$('fuLinks').value.split('\n').map(s=>s.trim()).filter(Boolean).map(url=>({url})),assets,sourceIds:editingSources,sourceSnapshots:editingSources.map(id=>sourceSnapshots([id])[0].title!=='원본 없음'?sourceSnapshots([id])[0]:(active?.sourceSnapshots||[]).find(x=>x.id===id)||sourceSnapshots([id])[0]),parentFollowupId:parentId,followUpType:active?.followUpType||'lookup'};}
  function draft(){if(!$('fuQuestion')||!active)return;try{localStorage.setItem('fu_draft_'+draftKey,JSON.stringify({revision:active.revision||0,patch:collect()}));}catch{$('fuError').textContent='이 기기에 임시 보관하지 못했습니다. 창을 닫기 전에 저장해 주세요.';}}
  async function open(id,prefill={}){
    if(overlay.classList.contains('on')&&dirty&&!confirm('저장하지 않은 내용을 이 기기에 남기고 다른 확인 기록을 열까요?'))return;
    try{
      if(!ready)await start();
      const current=id?await store.read(id):null;if(id&&!current)throw Error('NOT_FOUND');
      active=current||{id:store.newId(),revision:0,state:'open',judgment:'pending',comparison:'',...prefill};assets=(active.assets||[]).slice();editingSources=(active.sourceIds||[]).slice();parentId=active.parentFollowupId||'';dirty=false;op=null;
      draftKey=current?current.id:'new';
      let savedDraft=null;try{savedDraft=JSON.parse(localStorage.getItem('fu_draft_'+draftKey)||'null');}catch{}
      const r=active;
      $('fuBody').innerHTML='<div class="fu-status">'+C.STATES[r.state]+(r.legacyCompleted?' · 기존 완료 · 결과 미기록':'')+'</div>'+(savedDraft?'<div class="fu-draft">이 기기에 저장 전 내용이 있습니다. '+button('입력 복원','draft')+button('임시 내용 버리기','discard')+'</div>':'')
        +field('확인할 질문','fuQuestion',r.question)+ '<div class="fu-two">'+field('다음 확인 예정일','fuDue',r.dueAt,'date')+field('자료 기준일 (선택)','fuBasis',r.basisDate,'date')+'</div>'
        +'<details '+(r.expectation?'open':'')+'><summary>당시 예상·조건</summary>'+field('무엇을 예상했는가','fuExpected',r.expectation,'textarea')+'</details>'
        +field('확인 결과 · 보류라면 이유','fuResult',r.result,'textarea')
        +'<div class="fu-evidence"><label class="fu-upload">📷 사진 추가<input id="fuFiles" type="file" accept="image/png,image/jpeg,image/webp,image/gif" multiple hidden></label><div id="fuAssets"></div>'+field('근거 링크 (한 줄에 하나)','fuLinks',(r.links||[]).map(l=>l.url).join('\n'),'textarea')+'</div>'
        +'<div class="fu-two"><label class="fu-field">판단 변화<select id="fuJudgment">'+options(C.JUDGMENTS,r.judgment||'pending')+'</select></label><label class="fu-field">예상과 비교<select id="fuComparison">'+options(C.COMPARISONS,r.comparison||'')+'</select></label></div>'
        +'<details '+(r.changeReason||r.nextAction||r.observedChange||r.lesson?'open':'')+'><summary>변화 이유 · 다음 행동 · 사후 복기</summary>'+field('판단을 바꾼 이유','fuReason',r.changeReason,'textarea')+field('다음에 할 일','fuNext',r.nextAction,'textarea')+field('이후 실제로 관찰한 변화','fuObserved',r.observedChange,'textarea')+field('배운 점','fuLesson',r.lesson,'textarea')+'</details>'
        +'<details><summary>관련 자료 · 후속 확인</summary><div id="fuSources"></div>'+button('관련 자료 선택','sources')+(r.parentFollowupId?button('앞선 확인 기록','parent'):'')+items.filter(x=>x.parentFollowupId===r.id).map(x=>'<button class="fu-button" data-open-fu="'+C.esc(x.id)+'">'+C.esc(x.question)+'</button>').join('')+'</details>'
        +'<div class="fu-actions">'+button('확인 이력 보기','history')+(r.revision?button('후속 질문 만들기','followup'):'')+(['done','paused'].includes(r.state)?button(r.state==='paused'?'확인 재개':'다시 열기','reopen'):'')+'</div><div id="fuHistory"></div><p class="fu-error" id="fuError" role="status"></p>';
      overlay.classList.add('on');overlay.scrollTop=0;overlay.querySelector('.modal').scrollTop=0;drawAssets();drawSources();
      $('fuJudgment').onchange=function(){if(this.value==='change'||this.value==='withdraw')$('fuReason').closest('details').open=true;};
      $('fuFiles').onchange=async e=>{setBusy(true);$('fuError').textContent='사진을 보관하는 중입니다…';try{for(const f of e.target.files)assets.push(await store.upload(f));dirty=true;op=null;drawAssets();draft();$('fuError').textContent='사진 보관됨 · 결과를 저장해 주세요';}catch(err){$('fuError').textContent=errorText(err);}finally{e.target.value='';setBusy(false);}};
      overlay.querySelectorAll('[data-open-fu]').forEach(b=>b.onclick=()=>open(b.dataset.openFu));
      overlay.querySelectorAll('[data-fu]').forEach(b=>b.onclick=()=>editorAction(b.dataset.fu,savedDraft));
    }catch(e){bridge.toast(errorText(e));}
  }
  function drawSources(){$('fuSources').innerHTML=editingSources.map(id=>{const r=bridge.records().find(x=>x.id===id),old=active.sourceSnapshots?.find(x=>x.id===id);return r?'<button class="fu-button" type="button" data-source="'+C.esc(id)+'">'+C.esc(r.title)+'</button>':'<p class="fu-muted">원본 없음 · '+C.esc(old?.title||id)+'</p>';}).join('')||'<span class="fu-muted">연결된 자료 없음</span>';$('fuSources').querySelectorAll('[data-source]').forEach(b=>b.onclick=()=>{if(dirty&&!confirm('입력은 이 기기에 남기고 원본 자료를 열까요?'))return;overlay.classList.remove('on');bridge.openRecord(b.dataset.source);});}
  function drawAssets(){$('fuAssets').innerHTML=assets.map((a,i)=>'<figure>'+(C.safeURL(a.url)?'<a href="'+C.esc(C.safeURL(a.url))+'" target="_blank" rel="noopener"><img src="'+C.esc(C.safeURL(a.url))+'" alt="확인 근거 사진"></a>':'<span>사진 누락</span>')+'<figcaption>'+C.esc(a.name||'근거 사진')+'</figcaption><button type="button" data-remove="'+i+'">첨부 해제</button></figure>').join('');$('fuAssets').querySelectorAll('[data-remove]').forEach(b=>b.onclick=()=>{assets.splice(Number(b.dataset.remove),1);dirty=true;op=null;drawAssets();draft();});}
  function setBusy(on){busy=on;overlay.querySelectorAll('button,input,textarea,select').forEach(e=>e.disabled=on);}
  function clearDraft(){try{localStorage.removeItem('fu_draft_'+draftKey);}catch{}}
  async function save(stateNext){
    if(busy)return false;const patch=collect();patch.state=stateNext||active.state;op=op||uid();setBusy(true);$('fuError').textContent='서버 저장 중…';
    try{const item=await store.save(active.id,patch,active.revision||0,op);clearDraft();active=item;dirty=false;items=items.filter(x=>x.id!==item.id).concat(item);changed();bridge.toast('확인 기록을 저장했습니다');return true;}catch(e){$('fuError').textContent=errorText(e);draft();return false;}finally{setBusy(false);}
  }
  function close(){if(busy)return;if(dirty&&!confirm('저장 전 내용은 이 기기에 남습니다. 닫을까요?'))return;overlay.classList.remove('on');}
  async function editorAction(action,savedDraft){
    if(busy)return;
    if(action==='close')return close();
    if(action==='save'||action==='complete'||action==='pause'||action==='reopen'){
      const next={complete:'done',pause:'paused',reopen:'working'}[action]|| (active.state==='open'?'working':active.state);
      if(await save(next))overlay.classList.remove('on');return;
    }
    if(action==='history'){try{const list=await store.history(active.id);$('fuHistory').innerHTML=list.length?list.map(h=>'<article class="fu-history"><b>'+C.esc(stamp(h.recordedAt))+' · '+C.esc({migrated:'기존 기록 보존',created:'생성',completed:'완료',reopened:'재개',updated:'수정'}[h.event]||'확인')+'</b><p>당시 예상: '+C.esc(h.expectation||'미기록')+'</p><p>결과: '+C.esc(h.result||(h.legacyCompleted?'기존 완료 · 결과 미기록':'미기록'))+'</p><p>판단: '+C.esc(C.JUDGMENTS[h.judgment]||'아직 판단 안 함')+' '+C.esc(h.changeReason||'')+'</p><p>관찰: '+C.esc(h.observedChange||'미기록')+'</p><p>배운 점: '+C.esc(h.lesson||'미기록')+'</p>'+(h.links||[]).filter(l=>C.safeURL(l.url)).map(l=>'<a target="_blank" rel="noopener" href="'+C.esc(C.safeURL(l.url))+'">'+C.esc(l.url)+'</a>').join('<br>')+(h.assets||[]).filter(a=>C.safeURL(a.url)).map(a=>'<a target="_blank" rel="noopener" href="'+C.esc(C.safeURL(a.url))+'"> · 사진 근거</a>').join('')+'</article>').join(''):'<p>저장된 이력이 없습니다.</p>';}catch(e){$('fuError').textContent=errorText(e);}return;}
    if(action==='followup'){if(dirty&&!await save())return;return open(null,{sourceIds:editingSources,sourceSnapshots:sourceSnapshots(editingSources),parentFollowupId:active.id,expectation:'앞선 확인 결과: '+(active.result||'결과 미기록')});}
    if(action==='parent')return open(parentId);
    if(action==='sources'){
      const host=$('fuSources');host.innerHTML='<p>연결할 자료를 선택하세요</p>'+bridge.records().map(r=>'<label class="fu-source-check"><input type="checkbox" value="'+C.esc(r.id)+'"'+(editingSources.includes(r.id)?' checked':'')+'>'+C.esc(r.title)+'</label>').join('');
      host.querySelectorAll('input').forEach(i=>i.onchange=()=>{editingSources=Array.from(host.querySelectorAll('input:checked')).map(x=>x.value);dirty=true;op=null;draft();});return;
    }
    if(action==='discard'){clearDraft();overlay.querySelector('.fu-draft')?.remove();return;}
    if(action==='draft'&&savedDraft){if(savedDraft.revision!==(active.revision||0)){$('fuError').textContent='다른 기기에서 수정된 이후의 초안입니다. 기존 결과와 비교해 필요한 내용만 옮겨 주세요.';$('fuHistory').textContent=JSON.stringify(savedDraft.patch,null,2);return;}
      const p=savedDraft.patch;const map={question:'fuQuestion',dueAt:'fuDue',expectation:'fuExpected',result:'fuResult',judgment:'fuJudgment',comparison:'fuComparison',changeReason:'fuReason',nextAction:'fuNext',observedChange:'fuObserved',lesson:'fuLesson',basisDate:'fuBasis'};for(const k in map)$(map[k]).value=p[k]||'';$('fuLinks').value=(p.links||[]).map(l=>l.url).join('\n');assets=p.assets||[];editingSources=p.sourceIds||[];parentId=p.parentFollowupId||'';drawAssets();drawSources();dirty=true;overlay.querySelector('.fu-draft')?.remove();}
  }
  function decoratePage(host,recordId){const panel=host.querySelector('[data-readpanel="2"]');if(!panel)return;const record=bridge.records().find(x=>x.id===recordId);const linked=items.filter(x=>(x.sourceIds||[]).includes(recordId)||(record?.followupIds||[]).includes(x.id));panel.innerHTML=button('＋ 확인할 질문','new')+(ready?linked.map(x=>cardRow(x,false)).join(''):'<p>확인 기록 연결 중…</p>');panel.querySelector('[data-fu="new"]').onclick=()=>open(null,{sourceIds:[recordId],sourceSnapshots:sourceSnapshots([recordId])});panel.querySelectorAll('[data-open-fu]').forEach(b=>b.onclick=()=>open(b.dataset.openFu));}
  async function synthesize(){
    const chosen=items.filter(x=>selection.has(x.id));if(!chosen.length)return;
    const title=prompt('공부노트 제목','확인 결과 모아 정리');if(!title)return;
    const id=bridge.db.collection('records').doc().id;
    const sourceIds=[...new Set(chosen.flatMap(x=>x.sourceIds||[]))];
    await bridge.db.collection('records').doc(id).set({kind:'study',title,date:C.day(Date.now()),body:chosen.map(x=>x.question+'\n확인 결과: '+(x.result||'미기록')+'\n판단 변화: '+(C.JUDGMENTS[x.judgment]||'아직 판단 안 함')+'\n'+(x.changeReason||'')).join('\n\n'),followupIds:chosen.map(x=>x.id),relations:sourceIds.map(targetId=>({targetId,type:'synthesizes'})),createdAt:Date.now(),updatedAt:Date.now(),studyStatus:'learning'});
    selection.clear();bridge.toast('완료 결과를 연결한 공부노트를 만들었습니다');bridge.openRecord(id);
  }
  async function exportAll(){
    bridge.toast('확인 기록과 근거 사진을 백업하는 중입니다');const current=await store.all(),history=[];for(const x of current)history.push(...await store.history(x.id));
    const images={},missing=[];for(const a of [...current,...history].flatMap(x=>x.assets||[])){if(images[a.id]||missing.includes(a.id))continue;try{if(!C.safeURL(a.url))throw Error();const r=await fetch(a.url,{signal:AbortSignal.timeout(15000)});if(!r.ok)throw Error();images[a.id]=await dataURL(await r.blob());}catch{missing.push(a.id);}}
    download({format:C.FORMAT,exportedAt:new Date().toISOString(),items:current,reviews:history,images,missing},'확인복기-'+C.day(Date.now())+'.json');bridge.toast(missing.length?'백업됨 · 가져오지 못한 사진 '+missing.length+'개 표시':'확인 기록·이력·사진 백업 완료');
  }
  function restoreChoose(){const input=document.createElement('input');input.type='file';input.accept='.json';input.onchange=async()=>{try{const b=C.parseBackup(await input.files[0].text());if(!confirm(b.items.length+'개 확인 기록을 새 사본으로 복원합니다. 기존 기록은 유지됩니다.'))return;await restore(b);}catch(e){bridge.toast(errorText(e));}};input.click();}
  async function restore(b){
    const operation=await C.stableId(JSON.stringify(b)),mapping=Object.fromEntries(await Promise.all(b.items.map(async x=>[x.id,await C.stableId(operation+':'+x.id)])));
    const existing=await store.all();const pending=b.items.filter(x=>!existing.some(e=>e.id===mapping[x.id]&&e.restoreOperation===operation));
    if(!pending.length){bridge.toast('이미 복원한 파일입니다. 중복 생성하지 않았습니다.');return;}
    const imageResults={};let missing=0,done=0;
    try{
      for(const x of [...b.items,...b.reviews])for(const a of x.assets||[]){if(imageResults[a.id])continue;
        if(b.images?.[a.id]){const raw=b.images[a.id];if(!/^data:image\/(png|jpeg|gif|webp|avif|bmp);base64,/.test(raw))throw Error('BAD_IMAGE');const blob=await (await fetch(raw)).blob();imageResults[a.id]=await store.upload(blob);}
        else {imageResults[a.id]={...a,url:'',path:'',status:'missing'};missing++;}
      }
      const remap=x=>({...x,id:mapping[x.id]||x.id,parentFollowupId:mapping[x.parentFollowupId]||x.parentFollowupId||'',assets:(x.assets||[]).map(a=>({...a,...imageResults[a.id]}))});
      for(const item of b.items){const x=remap(item);x.restoredFrom=item.id;const history=b.reviews.filter(r=>r.followupId===item.id).map(remap);await store.restoreItem(x,history,operation);done++;}
      items=await store.all();changed();bridge.toast(done+'개 복원'+(missing?' · 사진 누락 '+missing+'개':''));
    }catch(e){bridge.toast(done+'개 복원 후 중단됐습니다. 같은 파일로 재시도하면 중복 없이 이어집니다. '+errorText(e));throw e;}
  }
  return {start,render,open,decoratePage,exportAll,restore,get ready(){return ready;},get items(){return items;},get pending(){return items.filter(x=>x.state==='open'||x.state==='working');},get error(){return failure;}};
}
