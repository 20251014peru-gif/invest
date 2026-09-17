/* v7.29.1: 읽기 화면만 정리한다. 저장된 본문/관계/할 일은 변경하지 않는다. */
(function(root){
  'use strict';
  function esc(s){ return String(s||'').replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];}); }
  /* 번호만 있는 연속 목차만 인식. 인식되지 않는 문서는 전체 원문으로 표시한다. */
  function outline(text){
    var lines=String(text||'').replace(/\r\n?/g,'\n').split('\n'), marks=[];
    lines.forEach(function(line,i){if(/^0?[1-9]$/.test(line.trim())) marks.push({n:Number(line.trim()),i:i});});
    if(marks.length<2 || marks.some(function(m,i){return m.n!==i+1;})) return [];
    var tail=[];
    var items=marks.map(function(m,i){
      var chunk=lines.slice(m.i+1,i+1<marks.length?marks[i+1].i:lines.length);
      // 마지막 목차 아래에 붙여 넣은 전체 설명은 개요 카드에 중복 표시하지 않는다.
      var end=chunk.findIndex(function(l){return /^(핵심\s*(1줄|한\s*줄)|전체 흐름|볼 가치)\s*[|｜:]/.test(l.trim());});
      if(end>=0){if(i===marks.length-1)tail=chunk.slice(end);chunk=chunk.slice(0,end);}
      chunk=chunk.filter(function(l){return l.trim() && !/^[▸▹▶►▾▼]+$/.test(l.trim());});
      return {number:m.n,title:chunk[0]||('항목 '+m.n),text:chunk.slice(1).join('\n')};
    });
    // 원문에 같은 제목의 상세 절이 있으면 해당 절을 연결한다. 추측해서 내용을 재작성하지 않는다.
    function key(s){return s.replace(/[^0-9a-zA-Z가-힣]/g,'').toLowerCase();}
    var headings=[];
    tail.forEach(function(line,i){
      var match=items.findIndex(function(x){return key(line)===key(x.title)||key(line)===key(x.title.split(/\s+[—–]\s+/)[0]);});
      if(match>=0&&key(line))headings.push({index:i,item:match});
    });
    headings.forEach(function(h,i){items[h.item].detail=tail.slice(h.index+1,i+1<headings.length?headings[i+1].index:tail.length).join('\n').trim();});
    return items;
  }
  function bodyHTML(text){
    var items=outline(text);
    if(!items.length) return '<div class="pg-body">'+esc(text)+'</div>';
    return '<div class="pg-reader"><div class="pg-readswitch"><button type="button" data-readmode="outline" aria-pressed="true">한눈에 보기</button><button type="button" data-readmode="full" aria-pressed="false">전체 원문</button></div>'
      + '<div data-readview="outline"><div class="pg-outline">'+items.map(function(x,i){return '<button type="button" class="pg-outline-card" data-outline="'+i+'" aria-expanded="false"><b>'+String(x.number).padStart(2,'0')+' · '+esc(x.title)+'</b><span>'+esc(x.text.split('\n')[0]||'내용 보기')+'</span></button>';}).join('')+'</div>'
      + items.map(function(x,i){return '<section class="pg-outline-detail" data-outline-panel="'+i+'" hidden><h3>'+esc(x.title)+'</h3><div class="pg-body">'+esc(x.detail||x.text||x.title)+'</div><p class="pg-readhint">'+(x.detail?'원문의 해당 절입니다.':'선택한 목차의 요약입니다. 자세한 설명은 ‘전체 원문’에서 볼 수 있습니다.')+'</p></section>';}).join('')+'</div>'
      + '<div class="pg-body" data-readview="full" hidden>'+esc(text)+'</div></div>';
  }
  function tabsHTML(content,relations,later){
    var labels=['내용','연결된 기록','나중에 볼 것'], panels=[content,relations,later];
    return '<div class="pg-readtabs" role="tablist" aria-label="기록 읽기">'+labels.map(function(s,i){return '<button type="button" id="pg-tab-'+i+'" role="tab" data-readtab="'+i+'" aria-controls="pg-panel-'+i+'" aria-selected="'+(i===0)+'" tabindex="'+(i===0?0:-1)+'">'+s+'</button>';}).join('')+'</div>'
      + panels.map(function(s,i){return '<section id="pg-panel-'+i+'" role="tabpanel" aria-labelledby="pg-tab-'+i+'" data-readpanel="'+i+'"'+(i?' hidden':'')+'>'+(s||'<p class="pg-readhint">등록된 내용이 없습니다.</p>')+'</section>';}).join('');
  }
  function studyTabs(host){
    var page=host.querySelector('.st-page'),start=page&&page.querySelector('.st-readbar'),rel=page&&page.querySelector('.st-readrels');
    if(!start||!rel)return;
    var content=document.createElement('div'),relations=document.createElement('div'),later=document.createElement('div'),node=start;
    while(node&&node!==rel){var next=node.nextSibling;content.appendChild(node);node=next;}
    node=rel.nextSibling;
    while(node){var next=node.nextSibling;later.appendChild(node);node=next;}
    relations.appendChild(rel);
    var shell=document.createElement('div');shell.innerHTML=tabsHTML('','','');page.appendChild(shell);
    [content,relations,later].forEach(function(part,i){if(part.childNodes.length)shell.querySelector('[data-readpanel="'+i+'"]').replaceChildren(part);});
  }
  function bind(host){
    var tabs=Array.from(host.querySelectorAll('[data-readtab]'));
    tabs.forEach(function(b,i){
      b.addEventListener('click',function(){
        tabs.forEach(function(t){var on=t===b;t.setAttribute('aria-selected',on);t.tabIndex=on?0:-1;});
        host.querySelectorAll('[data-readpanel]').forEach(function(p){p.hidden=p.dataset.readpanel!==b.dataset.readtab;});
      });
      b.addEventListener('keydown',function(e){var n=e.key==='ArrowRight'?(i+1)%tabs.length:e.key==='ArrowLeft'?(i+tabs.length-1)%tabs.length:e.key==='Home'?0:e.key==='End'?tabs.length-1:-1;if(n>=0){e.preventDefault();tabs[n].click();tabs[n].focus();}});
    });
    host.querySelectorAll('[data-readmode]').forEach(function(b){b.addEventListener('click',function(){
      var reader=b.closest('.pg-reader');
      reader.querySelectorAll('[data-readview]').forEach(function(p){p.hidden=p.dataset.readview!==b.dataset.readmode;});
      reader.querySelectorAll('[data-readmode]').forEach(function(t){t.setAttribute('aria-pressed',t===b);});
    });});
    host.querySelectorAll('[data-outline]').forEach(function(b){b.addEventListener('click',function(){
      var reader=b.closest('.pg-reader'),open=b.getAttribute('aria-expanded')!=='true';
      reader.querySelectorAll('[data-outline]').forEach(function(t){t.setAttribute('aria-expanded',t===b&&open);});
      reader.querySelectorAll('[data-outline-panel]').forEach(function(p){p.hidden=!open||p.dataset.outlinePanel!==b.dataset.outline;});
      if(open) reader.querySelector('[data-outline-panel="'+b.dataset.outline+'"]').scrollIntoView({block:'nearest'});
    });});
  }
  function resetTop(){
    var overlay=document.getElementById('pageModal'),modal=overlay.querySelector('.modal');
    overlay.scrollTop=0;modal.scrollTop=0;
  }
  function drawer(){
    var side=document.getElementById('recSide'),edge=document.getElementById('widgetEdge'),btn=document.getElementById('btnSideToggle'),close=document.getElementById('widgetClose'),pinned=false,timer;
    function show(on){
      clearTimeout(timer);side.classList.toggle('is-open',on);side.inert=!on;
      side.setAttribute('aria-hidden',String(!on));
      [edge,btn].forEach(function(b){b.setAttribute('aria-expanded',String(on));});
    }
    function hide(){pinned=false;show(false);}
    function leave(){timer=setTimeout(function(){if(!pinned&&!side.matches(':hover')&&!side.contains(document.activeElement))show(false);},180);}
    [edge,side].forEach(function(el){el.addEventListener('pointerenter',function(e){if(e.pointerType==='mouse')show(true);});el.addEventListener('pointerleave',leave);});
    [edge,btn].forEach(function(b){b.addEventListener('click',function(){pinned=!pinned;show(pinned);});});
    close.addEventListener('click',function(){hide();edge.focus();});
    side.addEventListener('focusout',leave);
    document.addEventListener('keydown',function(e){if(e.key==='Escape'&&side.classList.contains('is-open')){hide();edge.focus();}});
    document.addEventListener('pointerdown',function(e){if(!side.contains(e.target)&&e.target!==edge&&!btn.contains(e.target))hide();});
    show(false);
    return {open:function(){pinned=true;show(true);},close:hide};
  }
  var api={outline:outline,bodyHTML:bodyHTML,tabsHTML:tabsHTML,studyTabs:studyTabs,bind:bind,resetTop:resetTop,drawer:drawer};
  if(typeof module==='object'&&module.exports)module.exports=api;else root.RecordReading=api;
})(typeof window!=='undefined'?window:globalThis);
