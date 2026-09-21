/* One persistent editing surface. Existing forms, listeners and storage remain authoritative. */
(function(root){
  'use strict';
  var panels=new Map(),active=null,session=null,host,generation=0;
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
