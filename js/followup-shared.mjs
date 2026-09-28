// Both apps render the calendar's live editor and use its original save API.
export function makeSharedFollowup(bridge){
 let shell=null,frame=null,recordId='',account='',context=null,writes=0;
 const canLeave=()=>{if(writes){bridge.toast('저장이 끝난 뒤 이동해 주세요.');return false;}return !shell||!shell.isConnected||!frame?.contentWindow?.followupDirty||confirm('저장하지 않은 입력이 있습니다. 이동할까요?');};
 function close(force=false){if(!force&&!canLeave())return false;shell?.remove();shell=null;window.FollowupSharedContext=null;return true;}
 window.addEventListener('beforeunload',e=>{if(shell?.isConnected&&(frame?.contentWindow?.followupDirty||writes)){e.preventDefault();e.returnValue='';}});
 async function open(id,onLegacy){
  if(!canLeave())return;close(true);recordId='investment-followup:'+id;account=bridge.account?.();
  shell=document.createElement('div');shell.id='followupSharedModal';shell.style.cssText='position:fixed;inset:0;z-index:10000;background:#f8f5f8;';
  frame=document.createElement('iframe');frame.title='달님 캘린더와 같은 확인·복기';frame.style.cssText='width:100%;height:100%;border:0;display:block';
  const activeShell=shell;
  context={id:recordId,legacy:()=>{if(!canLeave())return;close(true);onLegacy();},close:()=>close(true),changed:()=>bridge.changed?.(),
   request:async(path,method='GET',body)=>{
    if(activeShell!==shell)throw Error('다시 열어 주세요.');
    if(!['/investment-items/detail','/investment-items/resolve','/investment-items/save','/events','/subscriptions'].includes(path))throw Error('지원하지 않는 요청입니다.');
    if(path.startsWith('/investment-items/')&&body?.id!==recordId)throw Error('다른 항목의 요청입니다.');
    const user=window.firebase?.auth().currentUser;if(!user||user.isAnonymous||user.uid!==account)throw Error('보관실에서 본인 계정으로 로그인해 주세요.');
    const changing=method==='POST'&&['/events','/investment-items/save'].includes(path);if(changing)writes++;try{const token=await user.getIdToken();const r=await fetch('https://calendarapi-ng2m4osziq-du.a.run.app'+path,{method,headers:{Authorization:'Bearer '+token,'X-Workspace-Id':'family','Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{})});
    const data=await r.json();if(!r.ok)throw Object.assign(Error(data.error||'캘린더 서버 연결 실패'),{status:r.status});return data;}finally{if(changing)writes--;}
   }};
  window.FollowupSharedContext=context;frame.src='followup-shared.html?v=7.40.0';shell.append(frame);document.body.append(shell);
 }
 return {open,close,canLeave};
}
