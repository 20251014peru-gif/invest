import {esc,kst,safeUrl,hashRoute} from './core.js';
import {draftRead,draftWrite} from './storage.js';

// A news snapshot keeps the note readable after the news feed expires.
export function newsNote(article,values,previous=null){
 return {kind:'news-note',indicatorId:'',targetId:article.id,url:safeUrl(article.url),
  id:previous?.id,title:values.title.trim(),text:values.text,
  snapshot:previous?.snapshot||{newsId:article.id,title:article.title,url:safeUrl(article.url),source:article.source||'',date:article.date||''}};
}
export function initNotebook(get){
 const popup=document.createElement('dialog');popup.className='notebook-dialog';popup.setAttribute('aria-label','내 뉴스 노트');
 popup.innerHTML='<div class="dialog-top"><h2>내 뉴스 노트</h2><button type="button" aria-label="노트 닫기">✕</button></div><div class="notebook-host ai-body"></div>';document.body.append(popup);
 popup.querySelector('button').onclick=()=>popup.close();let standalone;
 function mount(host,article,getAnswer=()=>'',initial=null){
  let editing=initial,saving=false,epoch=0,dirty=false,queue=Promise.resolve();
  const key=()=>editing?'news-edit:'+editing.id:'news-new:'+article.id;
  host.innerHTML=`<section class="news-notebook"><div class="panel-head"><h2>내 노트</h2><span class="tag">날짜순 누적</span></div><p>기사의 주장과 내 판단을 구분해 남겨보세요. 붙여넣기는 Ctrl+V · 휴대폰은 입력칸을 길게 누르세요.</p><p class="notebook-source">${esc(article.title)}</p><form class="note-form"><label>노트 제목<input name="title" maxlength="200" placeholder="오늘 발견한 힌트"></label><label>내 생각·메모<textarea name="text" maxlength="20000" rows="9" placeholder="관찰한 사실\n\n내 해석\n\n다음에 확인할 조건"></textarea></label><div class="pill-row"><button type="button" data-note-append>AI 요약을 메모에 넣기</button><button type="button" data-note-copy>메모 복사</button></div><p class="note-status" role="status"></p><div class="pill-row"><button class="primary" type="submit">새 노트 저장</button><button type="button" data-note-new>새 노트 쓰기</button><button type="button" data-note-login>Google 로그인</button></div></form><h3 class="note-list-title">이 기사에 쌓인 노트</h3><div class="note-list"></div></section>`;
  const $=s=>host.querySelector(s),form=$('form'),status=t=>$('.note-status').textContent=t;
  const values=()=>({title:form.elements.title.value,text:form.elements.text.value});
  const setValues=v=>{form.elements.title.value=v.title||'';form.elements.text.value=v.text||'';};
  function persist(){dirty=true;const k=key(),v=JSON.stringify(values());queue=queue.catch(()=>{}).then(()=>draftWrite(k,v));queue.then(()=>{if(k===key())status('이 기기에 임시 보관됨 · 온라인 저장하면 다른 기기에서도 볼 수 있습니다.');}).catch(()=>status('임시 보관 실패 · 메모를 복사해 보관해주세요.'));return queue;}
  form.oninput=persist;
  async function load(rec=null){const token=++epoch;editing=rec;dirty=false;setValues(rec||{});form.querySelector('[type=submit]').textContent=rec?'수정본 저장':'새 노트 저장';status(rec?`${rec.revision}판 수정 중 · 이전 내용은 이력에 보존됩니다.`:'입력은 이 기기에 임시 보관합니다.');try{const raw=await draftRead(key());if(token===epoch&&!dirty&&raw){setValues(JSON.parse(raw));status('작성 중이던 노트를 복원했습니다.');}}catch{status('임시 입력 읽기 실패');}}
  function refresh(){const rows=(get().cloud?.records||[]).filter(r=>!r.deleted&&r.kind==='news-note'&&r.targetId===article.id).sort((a,b)=>String(b.updatedAt).localeCompare(String(a.updatedAt)));$('.note-list').innerHTML=rows.map(r=>`<article class="notebook-entry"><div class="news-meta">${esc(kst(r.updatedAt))} · ${r.revision}판</div><h3>${esc(r.title||'제목 없는 노트')}</h3><p class="note-text">${esc(r.text)}</p><div class="pill-row"><button type="button" data-note-edit="${esc(r.id)}">수정</button><button type="button" data-note-history="${esc(r.id)}">수정 이력</button><button type="button" data-note-url="${esc(r.id)}">노트 주소 복사</button></div><div class="note-history"></div></article>`).join('')||'<p class="muted">아직 저장한 노트가 없습니다. 생각이 바뀔 때 새 노트를 추가해보세요.</p>';}
  async function copy(text){try{await navigator.clipboard.writeText(text);status('복사했습니다.');}catch{status('복사 권한을 확인해주세요. 글을 선택해 직접 복사할 수도 있습니다.');}}
  host.onclick=async e=>{const b=e.target.closest('button');if(!b)return;try{
   if(b.hasAttribute('data-note-append')){const a=getAnswer();if(!a){status('먼저 AI 요약을 생성해주세요.');return;}const addition='\n\n[AI 요약 · 검증 전]\n'+a+'\n\n[내 생각]\n';if(form.elements.text.value.length+addition.length>20000){status('메모는 20,000자까지 저장할 수 있습니다.');return;}form.elements.text.value+=addition;await persist();}
   if(b.hasAttribute('data-note-copy'))await copy(values().title+'\n\n'+values().text);
   if(b.hasAttribute('data-note-new')&&!saving){await queue.catch(()=>{});if(dirty){status('작성 중인 내용을 먼저 저장하거나 비워주세요.');return;}await load();}
   if(b.hasAttribute('data-note-login'))await get().cloud.login();
   if(b.dataset.noteEdit&&!saving){if(dirty){status('작성 중인 내용을 먼저 저장해주세요.');return;}await load(get().cloud.records.find(r=>r.id===b.dataset.noteEdit));}
   if(b.dataset.noteHistory){const rows=await get().cloud.versions(b.dataset.noteHistory);b.closest('article').querySelector('.note-history').innerHTML=rows.map(r=>`<details><summary>${r.revision}판 · ${esc(kst(r.updatedAt))}</summary><h3>${esc(r.title)}</h3><p class="note-text">${esc(r.text)}</p></details>`).join('');}
   if(b.dataset.noteUrl)await copy(location.href.split('#')[0]+hashRoute('records',b.dataset.noteUrl));
  }catch(err){status(err.message);}};
  form.onsubmit=async e=>{e.preventDefault();if(saving)return;const v=values();if(!v.title.trim()&&!v.text.trim()){status('제목이나 메모를 입력해주세요.');return;}saving=true;const k=key();form.querySelectorAll('button,input,textarea').forEach(b=>b.disabled=true);try{await queue;await get().cloud.save(newsNote(article,v,editing),editing?.revision??null);await draftWrite(k,'');dirty=false;await load();status('온라인에 저장했습니다. 새 노트를 이어서 작성할 수 있습니다.');refresh();}catch(err){status(err.message);}finally{saving=false;form.querySelectorAll('button,input,textarea').forEach(b=>b.disabled=false);}};
  load(initial);refresh();return {refresh,get saving(){return saving;}};
 }
 function openRecord(rec){if(standalone?.saving){if(!popup.open)popup.showModal();return;}const a=rec.snapshot||{};standalone=mount(popup.querySelector('.notebook-host'),{...a,id:rec.targetId,title:a.title||rec.title},()=>'',rec);if(!popup.open)popup.showModal();}
 return {mount,openRecord,refresh:()=>standalone?.refresh()};
}
