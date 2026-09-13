// Preserve the original archive editor without replacing its save implementation.
export function preserveArchiveDraft(frame,id,report){
 const w=frame.contentWindow,d=frame.contentDocument,key='invest.workspace.archive.'+(id||'new');
 const fields=['kind','date','title','oneLiner','channel','link','stocks','action','body','checks','star','image','imagePath','verifyState','topics','aiInterpretation','userJudgment','scenarios'];
 const signature=r=>JSON.stringify(fields.map(k=>r?.[k]??null));let baseline=signature(w.records.find(r=>r.id===id)),dirty=false;
 let cached;try{cached=JSON.parse(localStorage.getItem(key)||'null');}catch{}
 const modal=d.querySelector('#recModal');
 const snapshot=()=>{if(!modal.classList.contains('on'))return;dirty=true;const values=Object.fromEntries([...modal.querySelectorAll('input[id],textarea[id],select[id]')].filter(n=>n.type!=='file').map(n=>[n.id,{value:n.value,checked:n.checked}]));try{localStorage.setItem(key,JSON.stringify({values,baseline,kind:w.curPickedKind(),stocks:w.pickedStocks,image:w.pickedImage,star:d.querySelector('#starRow')?.getAttribute('data-val'),checks:w.collectChecks(),scenario:w.readScenarioForm(),action:w.readActionValue()}));}catch{report('작성 초안을 보관하지 못했습니다.');}};
 if(cached){w._curEditingAction=cached.action||'';w.renderKindPick(cached.kind);w.applyKindFields(cached.kind);w.renderChecksBox(cached.checks||[]);w.fillScenarioForm(cached.scenario||null);for(const [key,value] of Object.entries(cached.values||{})){const n=d.getElementById(key);if(n&&n.type!=='file'){n.value=value.value;n.checked=value.checked;}}w.pickedStocks=cached.stocks||[];w.renderStockTags();w.pickedImage=cached.image||{url:'',path:''};w.showImagePreview(w.pickedImage.url);w.setStar(Number(cached.star)||0);baseline=cached.baseline;dirty=true;report('기록보관실 작성 중 초안을 복원했습니다.');}
 modal.addEventListener('input',snapshot);modal.addEventListener('change',snapshot);modal.addEventListener('click',()=>setTimeout(snapshot,0));
 d.getElementById('mSave').addEventListener('click',e=>{if(id&&signature(w.records.find(r=>r.id===id))!==baseline){e.stopImmediatePropagation();report('다른 화면에서 원본이 변경되었습니다. 초안을 보존하고 저장을 중단했습니다. 최신 기록을 확인해 주세요.');}},true);
 const originalToast=w.toast;w.toast=function(message){if(['수정했습니다','기록했습니다','지웠습니다'].includes(message)){localStorage.removeItem(key);dirty=false;baseline=signature(w.records.find(r=>r.id===id));report(message);}return originalToast.apply(this,arguments);};
 window.addEventListener('pagehide',()=>{if(dirty)snapshot();});
}
