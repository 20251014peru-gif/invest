// Read-only, owner-authenticated deployment backup. Never writes to Firestore or Storage.
const config = {apiKey:'AIzaSyAyG1chECYsbO7cSZUuXmNa0_KDYBmahPY',authDomain:'my-system-25497.firebaseapp.com',projectId:'my-system-25497',storageBucket:'my-system-25497.firebasestorage.app'};
firebase.initializeApp(config);
const db=firebase.firestore(),auth=firebase.auth(),names=['records','records_meta','records_todos','record_followups','record_followup_reviews'];
const el=id=>document.getElementById(id),say=x=>{el('status').textContent=typeof x==='string'?x:JSON.stringify(x,null,2);};
const stable=x=>JSON.stringify(x,(_,v)=>v&&typeof v==='object'&&!Array.isArray(v)?Object.keys(v).sort().reduce((o,k)=>(o[k]=v[k],o),{}):v);
async function hash(text){return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(text))),x=>x.toString(16).padStart(2,'0')).join('');}
auth.onAuthStateChanged(u=>{const signed=!!u?.providerData.some(p=>p.providerId==='google.com');el('auth').textContent=signed?'본인 계정 로그인됨':'Google 로그인 필요';el('snapshot').disabled=el('compare').disabled=!signed;});
el('login').onclick=async()=>{try{const p=new firebase.auth.GoogleAuthProvider();p.setCustomParameters({prompt:'select_account'});await auth.signInWithPopup(p);}catch(e){say('로그인 실패: '+e.message);}};
async function read(){
  if(!auth.currentUser?.providerData.some(p=>p.providerId==='google.com'))throw Error('Google 로그인이 필요합니다');
  const collections={};
  for(const name of names){say(name+' 서버 원본 읽는 중…');const s=await db.collection(name).get({source:'server'});collections[name]=Object.fromEntries(s.docs.map(d=>[d.id,d.data()]));}
  return collections;
}
function photoUrls(value,set=new Set()){
  if(typeof value==='string'){
    for(const m of value.matchAll(/https:\/\/firebasestorage\.googleapis\.com\/v0\/b\/my-system-25497\.firebasestorage\.app\/o\/[^\s"'<>\\]+/g)){
      try{const u=new URL(m[0].replace(/&amp;/g,'&'));if(u.searchParams.get('alt')==='media')set.add(u.href);}catch(_){}
    }
  }else if(value&&typeof value==='object')Object.values(value).forEach(x=>photoUrls(x,set));
  return set;
}
async function imagesFor(collections){
  const images={},missing=[],urls=[...photoUrls(collections)];
  for(const [i,url] of urls.entries()){
    say('사진 백업 '+(i+1)+'/'+urls.length);
    try{const r=await fetch(url,{signal:AbortSignal.timeout(30000)});if(!r.ok)throw Error('HTTP '+r.status);const blob=await r.blob();if(!blob.type.startsWith('image/'))throw Error('이미지가 아닌 응답');images[url]=await new Promise((resolve,reject)=>{const fr=new FileReader();fr.onload=()=>resolve(fr.result);fr.onerror=reject;fr.readAsDataURL(blob);});}
    catch(e){missing.push({url,error:e.message});}
  }
  return {images,missing};
}
function busy(on){el('snapshot').disabled=el('compare').disabled=on;}
el('snapshot').onclick=async()=>{
  busy(true);
  try{
    const collections=await read(),photos=await imagesFor(collections),sha256=await hash(stable(collections));
    const backup={format:'records-deployment-snapshot/v1',project:config.projectId,exportedAt:new Date().toISOString(),collections,...photos,sha256};
    el('snapshotText').textContent=JSON.stringify(backup);
    let localBackup='';
    if(location.hostname==='localhost'&&location.port==='8925'){
      const r=await fetch('/__backup',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(backup)});
      if(!r.ok)throw Error('개발 PC 백업 저장 실패');localBackup=(await r.json()).file;
    }
    const url=URL.createObjectURL(new Blob([JSON.stringify(backup)],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download='records-snapshot-'+new Date().toISOString().replace(/[:.]/g,'-')+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),30000);
    say({result:photos.missing.length?'사진 일부 누락 — 누락 확인 필요':'서버 원본·사진 백업 완료',counts:Object.fromEntries(names.map(n=>[n,Object.keys(collections[n]).length])),images:Object.keys(photos.images).length,missingImages:photos.missing.length,sha256,...(localBackup?{localBackup}:{})});
  }catch(e){say('백업 실패: '+e.message);}finally{busy(false);}
};
el('compare').onchange=async event=>{
  const file=event.target.files[0];if(!file)return;busy(true);
  try{
    const old=JSON.parse(await file.text());if(old.format!=='records-deployment-snapshot/v1'||old.project!==config.projectId)throw Error('다른 형식이나 프로젝트의 파일입니다');
    if(await hash(stable(old.collections))!==old.sha256)throw Error('백업 무결성 검사 실패');
    const now=await read(),report={};
    for(const name of names){const a=old.collections[name],b=now[name];report[name]={before:Object.keys(a).length,now:Object.keys(b).length,changed:Object.keys(a).filter(id=>id in b&&stable(a[id])!==stable(b[id])),removed:Object.keys(a).filter(id=>!(id in b)),added:Object.keys(b).filter(id=>!(id in a))};}
    say({result:'서버 원본 대조 완료',collections:report});
  }catch(e){say('대조 실패: '+e.message);}finally{busy(false);event.target.value='';}
};
