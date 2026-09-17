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
  /* v7.29.2: 원문의 글자/순서를 유지하면서 소제목과 문단만 구분한다. */
  function formattedHTML(text){
    var lines=String(text||'').split('\n');
    function lineHTML(line){
      var trimmed=line.trim(), label=line.match(/^(\s*(?:핵심\s*(?:1줄|한\s*줄)|전체 흐름|볼 가치|액션|전제|근거|반대 근거|리스크|확인할 것|결론|투자 시사점|달님(?:의)? 시사점)\s*[|｜:：])([\s\S]*)$/);
      if(label)return '<p class="pg-labelled"><strong>'+esc(label[1])+'</strong>'+esc(label[2])+'</p>';
      var sub=line.match(/^(\s*\*\*[^*]{1,100}\*\*)([\s\S]*)$/);
      if(sub)return '<p class="pg-subtopic"><strong>'+esc(sub[1]).replace(/\*\*/g,'<span class="pg-source-marker">**</span>')+'</strong>'+esc(sub[2])+'</p>';
      if(/^[▸▹▶►▾▼]+$/.test(trimmed)||/^↑\s*목차로$/.test(trimmed))return '<span class="pg-source-marker">'+esc(line)+'</span>';
      var heading=trimmed.length<=100 && (/^#{1,6}\s/.test(trimmed) || /[▸▹▶►▾▼]$/.test(trimmed) || /^(?:[\p{So}\p{Sk}\uFE0F\s]*)(?:달님(?:의)?\s*시사점|투자 시사점|핵심 정리|반대 시나리오|리스크|확인할 것|결론)\s*[:：]?$/u.test(trimmed));
      if(heading)return '<h4 class="pg-text-heading">'+esc(line)+'</h4>';
      return '<p class="pg-text-line'+(!trimmed?' is-blank':'')+'">'+esc(line)+'</p>';
    }
    var marks=[];lines.forEach(function(l,i){if(/^0?[1-9]$/.test(l.trim()))marks.push({n:Number(l.trim()),i:i});});
    if(marks.length<2||marks.some(function(m,i){return m.n!==i+1;}))return '<div class="pg-readable">'+lines.map(lineHTML).join('\n')+'</div>';
    var end=lines.length;
    for(var j=marks[marks.length-1].i+1;j<lines.length;j++){if(/^(핵심\s*(1줄|한\s*줄)|전체 흐름|볼 가치)\s*[|｜:]/.test(lines[j].trim())){end=j;break;}}
    var prefix=lines.slice(0,marks[0].i),suffix=lines.slice(end);
    return '<div class="pg-readable">'+prefix.map(lineHTML).join('\n')+(prefix.length?'\n':'')+'<div class="pg-source-overview">'+marks.map(function(m,i){
      var section=lines.slice(m.i,i+1<marks.length?marks[i+1].i:end);
      return '<section class="pg-source-section'+(m.n===9?' full':'')+'"><h4>'+esc(section.slice(0,2).join('\n'))+'</h4>'+(section.length>2?'\n'+section.slice(2).map(lineHTML).join('\n'):'')+'</section>';
    }).join('\n')+'</div>'+(suffix.length?'\n'+suffix.map(lineHTML).join('\n'):'')+'</div>';
  }
  function bodyHTML(text){
    var items=outline(text);
    if(!items.length) return formattedHTML(text);
    var short=items.filter(function(x){return x.number<=8&&!/달님.*시사점/.test(x.title);});
    var long=items.filter(function(x){return short.indexOf(x)<0;});
    // 실제 저장 원문은 번호 목차 뒤에 ‘■ 제목▸’ 절들이 이어진다. 번호 9에 뒷 절을 합치지 않는다.
    var lines=String(text||'').split('\n'),sections=[],heads=[];
    lines.forEach(function(line,i){var m=line.match(/^\s*■\s*(.+?)[▸▹▶►▾▼]?\s*$/);if(m)heads.push({i:i,title:m[1].replace(/[▸▹▶►▾▼]$/,'').trim()});});
    function key(s){return s.replace(/[^0-9a-zA-Z가-힣]/g,'').toLowerCase();}
    heads.forEach(function(h,i){
      if(short.some(function(x){return key(h.title)===key(x.title)||key(h.title)===key(x.title.split(/\s+[—–]\s+/)[0]);}))return;
      sections.push({title:h.title,text:lines.slice(h.i+1,i+1<heads.length?heads[i+1].i:lines.length).join('\n')});
    });
    if(sections.length)long=sections;
    return '<div class="pg-reader"><div class="pg-readswitch"><button type="button" data-readmode="outline" aria-pressed="true">한눈에 보기</button><button type="button" data-readmode="full" aria-pressed="false">전체 원문</button></div>'
      + '<div data-readview="outline"><div class="pg-overview"><div class="pg-outline">'+short.map(function(x){return '<section class="pg-outline-item"><h4>'+String(x.number).padStart(2,'0')+' · '+esc(x.title)+'</h4>'+formattedHTML(x.text)+'</section>';}).join('')+'</div></div>'
      + long.map(function(x){return '<section class="pg-implications"><h3>'+(x.number?String(x.number).padStart(2,'0')+' · ':'')+esc(x.title)+'</h3>'+formattedHTML(sections.length?x.text:(x.detail||x.text))+'</section>';}).join('')+'</div>'
      + '<div data-readview="full" hidden>'+formattedHTML(text)+'</div></div>';
  }
  function tabsHTML(content,relations,later){
    var labels=['내용','연결','확인 기록'], panels=[content,relations,later];
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
  function prepare(host){
    var meta=host.querySelector('.pg-meta'),title=host.querySelector('h2');
    if(meta){
      var extra=document.createElement('details');extra.className='pg-extra';extra.innerHTML='<summary>추가 속성</summary><div></div>';
      meta.querySelectorAll('.action,.stars,.vbadge,[class*="st-status"]').forEach(function(x){extra.lastElementChild.appendChild(x);});
      if(extra.lastElementChild.childNodes.length)meta.appendChild(extra);
      if(title)title.after(meta);
    }
    var tags=Array.from(host.querySelectorAll('.pg-stocks'));if(tags.length){tags.slice(1).forEach(function(t){while(t.firstChild)tags[0].appendChild(t.firstChild);t.remove();});}
    var exportBtn=host.querySelector('#recExportBtn,#stExportBtn');if(exportBtn){var holder=exportBtn.parentElement;var menu=document.createElement('details');menu.className='pg-export-menu';menu.innerHTML='<summary>⋯</summary>';menu.appendChild(exportBtn);holder.replaceWith(menu);}
    var full=host.querySelector('[data-readview="full"]'),nav=host.querySelector('.pg-readtabs');
    if(full&&nav){
      var first=nav.querySelector('[data-readtab="0"]');first.textContent='한눈에 보기';
      var b=document.createElement('button');b.type='button';b.id='pg-tab-full';b.dataset.readtab='full';b.setAttribute('role','tab');b.setAttribute('aria-selected','false');b.setAttribute('aria-controls','pg-panel-full');b.tabIndex=-1;b.textContent='전체 원문';first.after(b);
      var panel=document.createElement('section');panel.id='pg-panel-full';panel.dataset.readpanel='full';panel.setAttribute('role','tabpanel');panel.setAttribute('aria-labelledby','pg-tab-full');panel.hidden=true;full.hidden=false;panel.appendChild(full);nav.after(panel);
      host.querySelector('.pg-readswitch').remove();
    }
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
  var api={outline:outline,formattedHTML:formattedHTML,bodyHTML:bodyHTML,tabsHTML:tabsHTML,studyTabs:studyTabs,prepare:prepare,bind:bind,resetTop:resetTop,drawer:drawer};
  if(typeof module==='object'&&module.exports)module.exports=api;else root.RecordReading=api;
})(typeof window!=='undefined'?window:globalThis);
