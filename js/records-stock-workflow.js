/* UI projections use existing records, stock metadata and canonical followups. No new database. */
function stockTaskHTML(x){
  var state={open:'미확인',working:'확인 중',done:'완료',paused:'보류'}[x.state]||x.state;
  var due=x.state==='done'?(x.completedAt?RecordStocks.kstDate(x.completedAt)+' 완료':'기존 완료'):x.dueAt||'날짜 미정';
  return '<button type="button" class="stockTask" data-open-fu="'+esc(x.id)+'"><span><b>'+esc(x.question)+'</b><small>'+esc(x.state==='done'?(x.result||'기존 완료 · 결과 미기록'):(x.expectation||state))+'</small></span><span class="taskDue'+(x.state!=='done'&&x.dueAt&&x.dueAt<todayStr()?' overdue':'')+'">'+esc(due)+'</span></button>';
}
function stockFocusHTML(name,summary){
  var info=RecordStocks.overview(stockItemOf(name)), done=summary.followups.filter(function(x){return x.state==='done';}).sort(function(a,b){return (b.completedAt||b.updatedAt||0)-(a.completedAt||a.updatedAt||0);});
  var paused=summary.followups.filter(function(x){return x.state==='paused';});
  function fields(list){return '<div class="stockSummary">'+list.map(function(f){return '<div><b>'+esc(f.label)+'</b>'+esc(f.value)+'</div>';}).join('')+'</div>';}
  var status=!(FU&&FU.ready)||FU.error?'<p class="stockHint" role="status">'+esc(FU&&FU.error||'확인 일정을 연결하는 중입니다…')+' <button type="button" class="infoBtn" data-fu-retry>다시 연결</button></p>':
    summary.pending.length?summary.pending.slice(0,3).map(stockTaskHTML).join('')+(summary.pending.length>3?'<details><summary>나머지 '+(summary.pending.length-3)+'건</summary>'+summary.pending.slice(3).map(stockTaskHTML).join('')+'</details>':''):'<p class="stockHint">확인할 질문을 남기면 예정일과 결과를 여기서 이어 볼 수 있습니다.</p>';
  return '<div class="stockFocusHd"><b style="font-size:20px">'+esc(name)+'</b><span><button type="button" class="infoBtn" id="stockAddRecord">＋ 기록 남기기</button><button type="button" class="infoBtn" data-stockopen="'+esc(name)+'">종목 정보 수정</button><button type="button" class="infoBtn" id="stockPrint">출력 보기</button></span></div>'
    +'<section class="stockOverview" aria-label="종목 요약">'+(info.core.length?fields(info.core):'<p class="stockHint">보유 상태·수량·단가는 종목 정보에서 입력할 수 있습니다.</p>')
    +(info.reason?'<p class="stockReason"><b>'+esc(info.reason.label)+'</b>'+esc(info.reason.value)+'</p>':'<p class="stockHint">관심 이유나 매수사유를 한 줄 남겨 보세요.</p>')
    +'</section>'+(info.details.length?'<details class="stockDetails"><summary>판단 기준·추가 정보 '+info.details.length+'개</summary>'+fields(info.details)+'</details>':'')
    +'<section class="stockChecks"><div class="stockSectionHd"><h3>다음 확인'+(FU&&FU.ready?' · '+summary.pending.length:'')+'</h3><button type="button" class="infoBtn" id="stockAddFollowup">＋ 확인할 질문</button></div>'+status+'</section>'
    +((done.length||paused.length)?'<details class="stockChecks"><summary>완료·복기 '+done.length+'건'+(paused.length?' · 보류 '+paused.length+'건':'')+'</summary><p class="stockHint">완료는 확인을 마쳤다는 뜻입니다. 예상의 적중 여부와 판단 변화는 결과를 열어 확인하세요.</p>'+done.concat(paused).map(stockTaskHTML).join('')+'</details>':'')
    +'<h3 class="stockFeedTitle">기록·변경 이력</h3><div class="stockTotals">연결 기록 '+summary.linked+'건 · 투자논지/정보 변경 '+summary.history+'건 · 최신 날짜순'+(curQ?' · 선택한 종목의 전체 이력':'')+'</div>';
}
function bindStockWorkflow(){
  document.querySelectorAll('#content [data-stockempty]').forEach(function(b){b.onclick=function(){
    var name=b.dataset.stockempty;if(!confirm('내용이 없는 ‘'+name+'’을 종목 목록에서 삭제할까요?'))return;
    stockSaveAction(b,function(){return changeStockMaster(function(list){
      var index=list.findIndex(function(x){return stockName(x)===name;});if(index<0)return;
      if(RecordStocks.summary(name,list[index],records,FU?FU.items:[]).hasContent)throw Error('내용이 생긴 종목은 지우지 않습니다. 다시 확인해 주세요.');list.splice(index,1);
    });},function(){render();});
  };});
  document.querySelectorAll('#content [data-open-fu]').forEach(function(b){b.onclick=function(){openFollowup(b.dataset.openFu);};});
  var add=document.getElementById('stockAddFollowup');if(add)add.onclick=function(){openFollowup(null,{stocks:[curStockTab]});};
  var retry=document.querySelector('#content [data-fu-retry]');if(retry)retry.onclick=followupsStart;
  var print=document.getElementById('stockPrint');if(print)print.onclick=function(){showStockPrint(curStockTab);};
  var register=document.getElementById('stockRegisterBtn');if(register)register.onclick=function(){
    var input=document.getElementById('stockRegisterInput'),name=input.value.trim();if(!name)return;
    stockSaveAction(register,function(){return addStockToMaster(name);},function(){navigateStock(name);});
  };
  var field=document.getElementById('stockRegisterInput');if(field)field.onkeydown=function(e){if(e.key==='Enter'){e.preventDefault();register.click();}};
}
function stockEmptyHTML(){
  var empty=allStockNames().filter(function(n){return !stockSummary(n).hasContent;});
  return empty.length?'<p class="stockHint">내용이 없는 이름만 정리할 수 있습니다.</p><div class="stockRegister">'+empty.map(function(n){return '<button type="button" class="infoBtn" data-stockempty="'+esc(n)+'">'+esc(n)+' · 삭제</button>';}).join('')+'</div>':'';
}
function calendarFollowups(arr){
  if(!FU||!FU.ready||FU.error)return [];
  return RecordStocks.schedules(FU.items,arr,{stock:stockMode?curStockTab:'',allRecords:records,
    all:!stockMode&&curKind==='전체'&&!curStock&&!curVerify&&!curTopic&&!curQ&&!curStudyStatus&&!curStar&&!curChannel&&!curDateRange});
}
function calendarConnectionHTML(){return !FU||!FU.ready||FU.error?'<p class="stockHint" role="status">'+esc(FU&&FU.error||'확인 일정 연결 중…')+' (기록 날짜만 표시 중)</p>':'';}
function showStockPrint(name){
  if(RecordWorkspace.active){toast('입력을 저장하거나 닫은 뒤 출력해 주세요');return;}
  var summary=stockSummary(name), panel=document.getElementById('stockPrintView');
  if(!panel){panel=document.createElement('div');panel.id='stockPrintView';panel.className='stockPrintView';document.body.appendChild(panel);}
  var scroll=window.scrollY;
  panel.innerHTML='<div class="stockPrintActions"><button type="button" class="infoBtn" data-print-close>← 종목으로 돌아가기</button><button type="button" class="infoBtn" data-print-now>인쇄 / PDF 저장</button></div><h1>'+esc(name)+' · 투자 기록</h1><p>저장된 내용 기준 · 출력 준비 '+esc(new Date().toLocaleString('ko-KR'))+'</p>'
    +'<section><h2>종목 요약·판단 기준</h2><dl>'+summary.fields.map(function(f){return '<dt>'+esc(f.label)+'</dt><dd>'+esc(f.value)+'</dd>';}).join('')+'</dl></section>'
    +'<section><h2>확인·복기</h2>'+(!(FU&&FU.ready)||FU.error?'<p>확인 기록 연결이 완료되지 않아 이 부분을 출력할 수 없습니다.</p>':summary.followups.length?summary.followups.map(function(x){return '<article><h3>'+esc(x.question)+'</h3><p>상태: '+esc({open:'미확인',working:'확인 중',paused:'보류',done:'완료'}[x.state]||x.state)+' · 예정일: '+esc(x.dueAt||'미정')+(x.completedAt?' · 완료일: '+RecordStocks.kstDate(x.completedAt):'')+'</p>'+[['당시 예상',x.expectation],['확인 결과',x.result],['판단 변화',({pending:'아직 판단 안 함',keep:'유지',change:'수정',withdraw:'철회'})[x.judgment]],['예상 비교',({same:'예상과 같음',partial:'일부 다름',different:'예상과 다름',unknown:'판단 유보'})[x.comparison]],['변화 이유',x.changeReason],['다음 행동',x.nextAction],['이후 관찰',x.observedChange],['배운 점',x.lesson]].filter(function(f){return f[1];}).map(function(f){return '<p><b>'+f[0]+'</b><br>'+esc(f[1])+'</p>';}).join('')+(x.links||[]).map(function(l){return '<p>근거: '+esc(l.url)+'</p>';}).join('')+stockPrintImages(x.assets||[])+'</article>';}).join(''):'<p>저장된 확인 기록이 없습니다.</p>')+'</section>'
    +'<section><h2>기록·변경 이력</h2>'+summary.entries.map(function(r){return '<article><h3>'+esc(r.title||'기록')+'</h3><p>'+esc(r.date||'날짜 미기록')+'</p><p>'+esc(r.body||r.summary||r.oneLiner||'본문은 원본 기록에서 확인하세요.')+'</p>'+(r.userJudgment?'<p><b>내 판단</b><br>'+esc(r.userJudgment)+'</p>':'')+(r.link?'<p>원본: '+esc(r.link)+'</p>':'')+stockPrintImages(r.attachments||(r.image?[{url:r.image}]:[]))+'</article>';}).join('')+'</section><p class="stockHint">현재 저장된 종목 정보와 기록의 출력용 요약입니다. 공부노트의 서식·관계도, 세부 확인 변경 이력은 원본에서 확인하세요. 완료 여부는 예상의 적중 여부와 별개입니다.</p>';
  panel.querySelector('[data-print-close]').onclick=function(){document.body.classList.remove('stock-printing');panel.innerHTML='';window.scrollTo(0,scroll);};
  panel.querySelector('[data-print-now]').onclick=function(){window.print();};
  panel.querySelectorAll('img').forEach(function(img){img.onerror=function(){img.replaceWith(document.createTextNode('사진을 불러오지 못했습니다. 원본에서 확인하세요.'));};});
  document.body.classList.add('stock-printing');window.scrollTo(0,0);
}
function stockPrintImages(images){return images.filter(function(a){return /^https?:\/\//i.test(a.url||'');}).map(function(a){return '<figure><img src="'+esc(a.url)+'" alt="'+esc(a.caption||a.name||'첨부 사진')+'"><figcaption>'+esc(a.caption||a.name||'첨부 사진')+'</figcaption></figure>';}).join('');}

var _recordOriginal=null,_recordNewId=null,_recordSaving=false,_recordBaseline='';
function recordFormSignature(){
  return JSON.stringify({fields:Array.from(document.querySelectorAll('#recModal input:not([type=file]),#recModal textarea,#recModal select')).map(function(e){return [e.id||e.className,e.value,e.checked];}),
    stocks:pickedStocks,attachments:pickedAttachments.map(function(a){return [a.id,a.caption,a.order,a.status,a.url];}),kind:curPickedKind(),star:document.getElementById('starRow').dataset.val});
}
function recordIsDirty(){return !!_recordBaseline&&recordFormSignature()!==_recordBaseline;}
function recordCanLeave(){
  if(_recordSaving||attHasBlocking()){toast('저장·사진 업로드가 끝난 뒤 이동해 주세요');return false;}
  return !recordIsDirty()||confirm('저장하지 않은 입력이 있습니다. 입력을 버리고 이동할까요?');
}
function stockCanLeave(){if(_stockSaving){toast('저장을 마친 뒤 이동해 주세요');return false;}return !stockHasUnsavedFields()||confirm('저장하지 않은 종목 정보가 있습니다. 변경을 버리고 닫을까요?');}
async function saveRecordForm(data){
  if(_recordSaving)return;
  _recordSaving=true;
  var controls=Array.from(document.querySelectorAll('#recModal button,#recModal input,#recModal textarea,#recModal select')),disabled=controls.map(function(e){return e.disabled;});
  controls.forEach(function(e){e.disabled=true;});
  var button=document.getElementById('mSave'),label=button.textContent;button.textContent='저장 중…';
  var id=EDIT||(_recordNewId=_recordNewId||db.collection('records').doc().id),ref=db.collection('records').doc(id),original=_recordOriginal,at=Date.now();
  try{
    await db.runTransaction(async function(tx){
      var snap=await tx.get(ref);
      if(original){
        if(!snap.exists)throw Error('다른 기기에서 삭제한 기록입니다. 입력을 복사한 뒤 새 기록으로 보관해 주세요.');
        var edits={};Object.keys(data).forEach(function(k){if(k!=='checks'&&JSON.stringify(data[k])!==JSON.stringify(original[k]))edits[k]=data[k];});
        var latest=snap.data();RecordStocks.mergeFields(latest,original,edits);tx.update(ref,Object.assign({},edits,{updatedAt:at}));
      }else if(snap.exists){
        var saved=snap.data();
        if(Object.keys(data).some(function(k){return JSON.stringify(saved[k])!==JSON.stringify(data[k]);}))throw Error('앞선 저장이 이미 접수되었습니다. 입력을 복사하고 기록을 다시 열어 비교해 주세요.');
      }else tx.set(ref,Object.assign({},data,{createdAt:at,updatedAt:at}));
    });
    attClearDraftAfterSave();_recordBaseline='';toast('기록을 저장했습니다');closeModal(true);
    // Record tags already make stocks discoverable; master registration is best effort, never duplicate a saved record.
    data.stocks.forEach(function(name){addStockToMaster(name).catch(function(e){logBug('종목 목록 등록: '+e.message);});});
  }catch(e){logBug('기록 저장 실패: '+e.message);toast('저장되지 않았습니다. 입력을 유지했습니다. '+e.message);}
  finally{_recordSaving=false;controls.forEach(function(e,i){e.disabled=disabled[i];});button.textContent=label;}
}
