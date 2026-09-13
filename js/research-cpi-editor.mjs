import {esc,buildRecord,recordFingerprint,validateData} from './research-core.mjs';
export async function mountCpiEditor(host,get){
 host.textContent='CPI 분석 초안 확인 중…';
 try{
 const data=validateData(await fetch('data/research-cpi.json').then(r=>{if(!r.ok)throw Error('CPI 확인본 연결 실패');return r.json();}));
 const key='invest.research.cpi.workspace.v1';let cached={};try{cached=JSON.parse(localStorage.getItem(key)||'{}');}catch{}
 const blank=()=>({id:crypto.randomUUID(),title:'CPI 분석',oneLiner:'',body:'',evidence:[],expected:null,dirty:false,operation:null});
 let draft=cached.draft&&typeof cached.draft.body==='string'?cached.draft:blank(),busy=false;
 const persist=()=>localStorage.setItem(key,JSON.stringify({...cached,draft}));
 const draw=()=>{host.innerHTML=`<h1>CPI 분석 · 기록보관실</h1><p>기존 CPI 작성 초안과 채택한 근거를 이어갑니다.</p><form><label>제목<input name="title" maxlength="160" value="${esc(draft.title)}"></label><label>핵심 한 줄<input name="oneLiner" maxlength="300" value="${esc(draft.oneLiner)}"></label><label>내 분석<textarea name="body" maxlength="20000">${esc(draft.body)}</textarea></label><h2>채택한 공식 근거</h2>${data.evidence.map(e=>`<label><input type="checkbox" name="evidence" value="${esc(e.id)}" ${draft.evidence.includes(e.id)?'checked':''}>${esc(e.label)}</label><p>${esc(e.text)}</p>`).join('')}<div class="row"><button type="submit">기록보관실에 저장</button><button type="button" data-export>초안 내려받기</button><button type="button" data-new>새 분석</button></div><p role="status" data-save-status>초안은 이 브라우저에 보관됩니다. 온라인 저장은 버튼을 누를 때만 수행합니다.</p></form>`;
 const form=host.querySelector('form'),status=t=>host.querySelector('[data-save-status]').textContent=t;
 form.oninput=()=>{const v=new FormData(form);draft={...draft,title:v.get('title'),oneLiner:v.get('oneLiner'),body:v.get('body'),evidence:v.getAll('evidence'),dirty:true,operation:null};try{persist();status('초안 보관됨');}catch{status('초안 보관 실패 · 내려받기로 보관해 주세요.');}};
 host.querySelector('[data-export]').onclick=()=>{const url=URL.createObjectURL(new Blob([JSON.stringify({schema:'research-draft/1',draft},null,2)],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download='CPI-분석-초안.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
 host.querySelector('[data-new]').onclick=()=>{if(draft.dirty){status('현재 초안을 먼저 저장해 주세요.');return;}draft=blank();persist();draw();};
 form.onsubmit=async e=>{e.preventDefault();if(busy)return;try{const repo=get().repository;if(!repo)throw Error('기록보관실 연결 후 다시 저장해 주세요.');if(!draft.dirty&&draft.expected){status('변경한 내용이 없습니다.');return;}const patch=buildRecord(draft,data);draft.operation ||=crypto.randomUUID();persist();busy=true;form.querySelectorAll('input,textarea,button').forEach(n=>n.disabled=true);const saved=await repo.save(draft.id,patch,draft.expected,draft.operation);draft.expected=recordFingerprint(saved);draft.dirty=false;draft.operation=null;persist();status('기록보관실에 저장했습니다.');}catch(e){status(e.message==='CONFLICT'?'다른 화면에서 변경되었습니다. 초안은 보존하고 덮어쓰지 않았습니다.':e.message+' · 초안 유지');}finally{busy=false;form.querySelectorAll('input,textarea,button').forEach(n=>n.disabled=false);}};
 };draw();
 }catch(e){host.textContent=e.message;}
}
