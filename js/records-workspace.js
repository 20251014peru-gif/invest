/* One persistent editing surface. Existing forms, listeners and storage remain authoritative. */
(function(root){
  'use strict';
  var panels=new Map(),active=null,session=null,host,generation=0;
  function step(number,title,hint){
    var section=document.createElement('section');section.className='rw-step';
    section.innerHTML='<div class="rw-step-head"><span>'+number+'</span><div><h3>'+title+'</h3><p>'+hint+'</p></div></div>';
    return section;
  }
  function arrange(el){
    var body=el.querySelector('.mbody'),grid=document.createElement('div');grid.className='rw-grid';
    var intro=document.createElement('p');intro.className='rw-intro';
    function row(id){return document.getElementById(id).closest('.frow');}
    function put(section,nodes){nodes.forEach(function(n){section.appendChild(n);});grid.appendChild(section);}
    function cancel(footer,target){var b=document.createElement('button');b.type='button';b.className='rw-cancel';b.textContent='닫기';b.onclick=function(){document.getElementById(target).click();};footer.prepend(b);}
    if(el.id==='recModal'){
      body.appendChild(grid);
      intro.textContent='왼쪽부터 필요한 칸만 작성하세요. 내용이나 사진을 남기고, 판단과 다음 확인을 이어 적습니다.';
      var basic=step('01','무엇을 기록하나요?','종류 · 종목 · 날짜'),content=step('02','내용과 근거','본문 · 사진 · 출처'),decision=step('03','판단과 다음 확인','내 생각 · 확인할 일');
      basic.id='recordBasics';content.id='recordContent';decision.id='recordDecision';
      put(basic,[body.querySelector('.kindSwitchRow'),document.getElementById('kindPick'),row('fTitle'),row('stockInput'),row('fDate'),row('fTopics')]);
      var zone=document.getElementById('primaryZone');
      put(content,[zone,row('fChannel'),row('fLink')]);
      put(decision,[row('fOneLiner'),row('fUserJudge'),document.getElementById('rowAction').parentElement,row('fVerify'),row('checkAddBtn')]);
      var more=document.getElementById('moreFields');more.querySelector('summary').firstChild.textContent='더 자세히: AI 해석 · 시나리오 (선택) ';
      body.prepend(intro,grid);body.appendChild(more);
      document.getElementById('kindSwitchBtn').hidden=true;
      document.getElementById('mSave').textContent='기록 저장';cancel(el.querySelector('.mfoot'),'mClose');
    }else if(el.id==='stockDetailModal'){
      body.appendChild(grid);
      intro.textContent='보유 정보와 판단 기준을 나란히 수정하세요. 추가·수정·삭제한 항목은 마지막에 한 번에 저장됩니다.';
      grid.classList.add('rw-grid-stock');
      var holding=step('01','보유·매매 정보','현재 직접 관리하는 값'),criteria=step('02','판단 기준','관심 이유 · 목표 · 위험 조건');
      var trade=document.getElementById('sdTradeInfo');trade.open=true;trade.querySelector('summary').hidden=true;
      put(holding,[body.querySelector('.sdMetaRow'),trade]);put(criteria,[document.getElementById('sdCustomFields').parentElement]);
      var history=document.createElement('details');history.className='rw-history';history.innerHTML='<summary>기존 기록·변경 이력 보기</summary><div class="rw-history-grid"></div>';
      [document.getElementById('sdThesisLog').parentElement,document.getElementById('sdRelatedRecords').parentElement].forEach(function(d){d.open=true;history.lastChild.appendChild(d);});
      var footer=document.createElement('div');footer.className='mfoot';footer.appendChild(document.getElementById('sdSaveFields'));footer.lastChild.textContent='종목 정보 저장';footer.lastChild.style.marginTop='0';cancel(footer,'sdClose');
      body.prepend(intro,grid);body.appendChild(history);footer.prepend(document.getElementById('stockSaveStatus'));el.querySelector('.modal').appendChild(footer);
    }
    // The same controls are moved, never cloned: existing listeners, drafts and IDs stay intact.
    el.querySelectorAll('.frow').forEach(function(r){var label=r.querySelector('label'),input=r.querySelector('input:not([type=file]),textarea,select');if(label&&input&&input.id&&!label.htmlFor)label.htmlFor=input.id;});
  }
  function sync(){
    var visible=Array.from(panels.values()).filter(function(p){return p.el.classList.contains('on');});
    var next=visible.find(function(p){return p!==active;})||visible[0];
    if(next){
      if(!session)session={scroll:window.scrollY,focus:document.activeElement};
      visible.forEach(function(p){if(p!==next)p.el.classList.remove('on');});
      var changed=active!==next;active=next;host.hidden=false;document.body.classList.add('rw-active');
      if(changed)requestAnimationFrame(function(){host.scrollIntoView({block:'start'});var title=next.el.querySelector('.mhd');if(title){title.tabIndex=-1;title.focus({preventScroll:true});}});
    }else if(active){
      active=null;host.hidden=true;document.body.classList.remove('rw-active');
      var previous=session;session=null;
      root.dispatchEvent(new Event('records-editor-closed'));
      requestAnimationFrame(function(){if(previous){window.scrollTo(0,previous.scroll);if(previous.focus&&previous.focus.isConnected)previous.focus.focus({preventScroll:true});}});
    }
  }
  function register(id,canLeave){
    if(panels.has(id))return;
    host=host||document.getElementById('recordEditorHost');
    var el=document.getElementById(id);if(!el||!host)return;
    arrange(el);
    el.classList.add('rw-panel');el.removeAttribute('aria-modal');el.setAttribute('role','region');
    host.appendChild(el);panels.set(id,{el:el,canLeave:canLeave});
    new MutationObserver(sync).observe(el,{attributes:true,attributeFilter:['class']});
  }
  function prepare(id){
    var current=active||Array.from(panels.values()).find(function(p){return p.el.classList.contains('on');});
    if(current&&current.canLeave&&!current.canLeave())return false;
    generation++;return true;
  }
  root.RecordWorkspace={register:register,prepare:prepare,get generation(){return generation;},get active(){return active&&active.el.id;}};
})(window);
