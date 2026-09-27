(function(root){
'use strict';
const endpoint='https://asia-northeast3-my-system-25497.cloudfunctions.net/macroAi';
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const money=n=>typeof n==='number'?'$'+(n/1e9).toFixed(9).replace(/0+$/,'').replace(/\.$/,''):'미확인';
let costButton,dialog;
async function call(action,data={}){const user=firebase.auth().currentUser;if(!user||user.isAnonymous)throw Error('본인 Google 로그인이 필요합니다.');const token=await user.getIdToken();const r=await fetch(endpoint,{method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:JSON.stringify({action,...data})});const out=await r.json();if(!r.ok)throw Error(out.error||'서버 연결 실패');if(out.schema!=='records-synthesis-1')throw Error('종합분석 서버 연결 준비 중입니다.');return out;}
async function refreshCost(){
 if(!costButton)return;costButton.textContent='AI 비용 · 조회 중';
 try{const out=await call('records-costs'),t=out.totals;costButton.textContent=t?'AI 비용 · '+money(t.spentNano)+' (계산액)':'AI 비용 · 계측 전';costButton.dataset.detail=JSON.stringify(out);if(t&&(t.pending||t.unknown))costButton.textContent+=' · 미정산 있음';}
 catch(e){costButton.textContent='AI 비용 · 조회 불가';costButton.dataset.detail=JSON.stringify({error:e.message});}
}
function initCosts(){if(costButton)return;costButton=document.createElement('button');costButton.className='navbtn';costButton.id='recordsAiCost';costButton.type='button';costButton.textContent='AI 비용 · 로그인 필요';document.querySelector('.recordsHome').closest('h1').after(costButton);
 dialog=document.createElement('dialog');dialog.className='rai-dialog';dialog.innerHTML='<button data-close>닫기</button><h2>AI 비용</h2><div data-cost-content></div><button data-refresh>서버 기록 새로고침</button>';document.body.append(dialog);dialog.querySelector('[data-close]').onclick=()=>dialog.close();
 const show=()=>{const out=JSON.parse(costButton.dataset.detail||'{}'),t=out.totals;dialog.querySelector('[data-cost-content]').innerHTML=out.error?'<p>'+esc(out.error)+'</p>':'<p><b>범위: 투자 기록보관실 종합분석</b></p><dl><dt>사용량 기준 누적 계산액</dt><dd>'+money(t?.spentNano)+'</dd><dt>제공사 청구 대조액</dt><dd>미연결 · 확정 청구액이 아닙니다</dd><dt>처리 중 / 비용 미확인</dt><dd>'+(t?esc(t.pending||0)+'건 / '+esc(t.unknown||0)+'건':'계측 전')+'</dd><dt>계측 시작</dt><dd>'+esc(t?.startedAt||'아직 기록 없음')+'</dd><dt>서버 조회 시각</dt><dd>'+esc(out.asOf||'미조회')+'</dd></dl><p>'+esc(out.coverage||'')+'</p><p>USD 기준입니다. 환율·세금·카드 수수료를 포함한 원화 결제액은 아닙니다. 단가와 실제 응답 토큰으로 계산하며, 조회 실패·미정산을 0원으로 표시하지 않습니다.</p>';};
 costButton.onclick=async()=>{dialog.showModal();show();await refreshCost();show();};dialog.querySelector('[data-refresh]').onclick=async()=>{await refreshCost();show();};firebase.auth().onAuthStateChanged(()=>refreshCost());window.addEventListener('focus',refreshCost);
}
function mount(host,currentId,getRecords){
 const tab=host.querySelector('[data-readtab="1"]'),panel=host.querySelector('[data-readpanel="1"]');if(!tab||!panel)return;tab.textContent='AI 종합분석';
 const old=document.createElement('details');old.innerHTML='<summary>기존 연결 기록</summary>';while(panel.firstChild)old.appendChild(panel.firstChild);
 const form=document.createElement('section');form.className='rai-panel';form.innerHTML='<h3>자료를 함께 읽고 새로운 의미 찾기</h3><p>자료에 적힌 내용과 AI의 재해석을 구분하고, 각 결론의 근거를 표시합니다.</p><label>함께 분석할 기록 찾기<input data-search placeholder="제목·채널로 검색"></label><div data-selected></div><div data-options class="rai-options"></div><label>알고 싶은 점<textarea data-question maxlength="1500">이 자료들을 함께 보면 어떤 새로운 의미가 드러나는가? 공통점·충돌·변화를 비교해 줘.</textarea></label><p class="rai-note">선택한 기록의 본문·제목·출처를 OpenAI로 보냅니다. 이미지와 링크 페이지는 읽지 않습니다. 동일 자료·질문은 저장 결과를 재사용합니다. GPT-5 mini · 입력 $0.25 / 출력 $2 (100만 토큰당), 일 $1·월 $20 서버 예산.</p><button data-run>선택 자료로 AI 분석</button> <button data-history>저장된 분석 보기</button><p data-status role="status"></p><div data-result></div>';
 panel.append(form,old);old.querySelectorAll('#relAddBtn,#contBtn,#synthBtn').forEach(b=>b.hidden=true);
 const selected=new Set([currentId]);let busy=false;
 const $=s=>form.querySelector(s),status=t=>$('[data-status]').textContent=t;
 const list=()=>{const rows=getRecords(),q=$('[data-search]').value.toLowerCase();$('[data-selected]').textContent='선택 '+selected.size+'개: '+rows.filter(r=>selected.has(r.id)).map(r=>r.title||'제목 없음').join(' · ');$('[data-options]').innerHTML=rows.filter(r=>selected.has(r.id)||(r.title+' '+r.channel).toLowerCase().includes(q)).slice(0,60).map(r=>'<label><input type="checkbox" value="'+esc(r.id)+'" '+(selected.has(r.id)?'checked':'')+'> '+esc(r.title||'제목 없음')+' <small>'+esc(r.date||'')+'</small></label>').join('');};
 $('[data-search]').oninput=list;$('[data-options]').onchange=e=>{if(e.target.checked&&selected.size>=8){e.target.checked=false;status('최대 8개를 선택할 수 있습니다.');return;}e.target.checked?selected.add(e.target.value):selected.delete(e.target.value);list();};list();
 function render(item){
  if(item.status!=='completed'){status(item.status==='pending'?'서버 처리 중이거나 결과 확인이 필요합니다. 저장된 분석에서 다시 확인하세요.':item.error||'분석 실패 · 비용 기록을 확인하세요.');return;}
  const sources=item.sources||[],link=id=>{const s=sources.find(x=>x.id===id);return '<a href="#record='+encodeURIComponent(id)+'">'+esc(s?.title||id)+'</a>';},o=item.output;
  const block=(title,rows)=>'<section><h4>'+title+'</h4>'+(rows.length?rows.join(''):'<p>도출된 내용 없음</p>')+'</section>';
  $('[data-result]').innerHTML='<p>'+esc(item.model)+' · '+esc(item.createdAt)+' · 이 분석 계산액 '+money(item.costNano)+'</p><div class="rai-results">'+block('자료에서 확인한 내용 · 독립 사실 검증 전',o.facts.map(x=>'<article><p>'+esc(x.text)+'</p><blockquote>'+esc(x.quote)+'</blockquote>'+link(x.sourceId)+'</article>'))+block('AI 종합해석 · 사실과 구분',o.interpretations.map(x=>'<article><b>'+esc(x.text)+'</b><p>'+esc(x.reasoning)+'</p><p>반대 가능성: '+esc(x.counterargument)+'</p>'+x.sourceIds.map(link).join(' · ')+'</article>'))+block('주장의 충돌',o.conflicts.map(x=>'<article>'+esc(x.text)+'<p>'+x.sourceIds.map(link).join(' · ')+'</p></article>'))+block('불확실성 / 다음 확인',o.unknowns.concat(o.nextChecks).map(x=>'<p>'+esc(x)+'</p>'))+'</div>';status(item.cached?'저장된 결과입니다. 추가 AI 호출 없음.':'분석과 비용 기록을 서버에 저장했습니다.');
 }
 $('[data-run]').onclick=async()=>{if(busy)return;if(selected.size<2){status('함께 읽을 기록을 2개 이상 선택하세요.');return;}busy=true;$('[data-run]').disabled=true;status('서버에서 자료를 읽고 분석 중입니다. 창을 닫아도 저장된 분석에서 확인할 수 있습니다.');try{render(await call('records-analyze',{recordIds:[...selected],question:$('[data-question]').value}));}catch(e){status(e.message+' 저장된 분석과 비용을 확인한 뒤 진행하세요.');}finally{busy=false;$('[data-run]').disabled=false;await refreshCost();}};
 $('[data-history]').onclick=async()=>{try{const out=await call('records-history');const items=out.items.filter(x=>x.sourceIds?.includes(currentId));$('[data-result]').replaceChildren();status(items.length?'저장된 결과를 선택하세요.':'저장된 분석이 없습니다.');for(const item of items){const b=document.createElement('button');b.textContent=item.createdAt+' · '+item.question+' · '+item.status;b.onclick=()=>render(item);$('[data-result]').append(b);}}catch(e){status(e.message);}};
}
root.RecordAI={mount,initCosts,refreshCost};
})(window);
