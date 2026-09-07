import {onRequest} from 'firebase-functions/v2/https';
import {defineSecret,defineString} from 'firebase-functions/params';
import {initializeApp} from 'firebase-admin/app';import {getAuth} from 'firebase-admin/auth';import {getFirestore} from 'firebase-admin/firestore';import {createHash} from 'node:crypto';
import {normalizeRequest,apiRequest,parseAnswer,PROMPT_VERSION} from './protocol.js';
initializeApp();const key=defineSecret('OPENAI_API_KEY'),owner=defineSecret('MACRO_OWNER_UID');const model=defineString('MACRO_AI_MODEL',{default:'gpt-5-mini'});
// 배포 전: 신규 private 경로의 공개 접근 차단과 본인 UID 확인 필수.
export const macroAi=onRequest({region:'asia-northeast3',cors:['https://20251014peru-gif.github.io'],secrets:[key,owner],timeoutSeconds:110,maxInstances:1,concurrency:1},async(req,res)=>{
 res.set('Cache-Control','no-store');if(req.method!=='POST'){res.status(405).json({error:'POST만 지원합니다'});return;}
 let uid;try{const token=(req.headers.authorization||'').match(/^Bearer (.+)$/)?.[1];if(!token)throw Error();const user=await getAuth().verifyIdToken(token,true);if(user.uid!==owner.value()||user.email_verified!==true||user.firebase?.sign_in_provider!=='google.com')throw Error();uid=user.uid;}catch{res.status(401).json({error:'본인 Google 로그인 확인이 필요합니다'});return;}
 let data;try{if(JSON.stringify(req.body).length>120000)throw Error();data=normalizeRequest(req.body);}catch{res.status(400).json({error:'질문 또는 근거 자료 형식을 확인하세요'});return;}
 const db=getFirestore(),root=db.collection('chatgpt_macro_private').doc(uid),m=model.value();const cacheId=createHash('sha256').update(JSON.stringify({data,model:m,prompt:PROMPT_VERSION})).digest('hex');const cache=root.collection('aiCache').doc(cacheId);
 try{if(data.kind==='news'){const c=await cache.get();if(c.exists){res.json({...c.data(),cached:true});return;}}
 const day=new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Seoul',dateStyle:'short'}).format(new Date()),quota=root.collection('aiUsage').doc(day);
 await db.runTransaction(async tx=>{const snap=await tx.get(quota),n=snap.data()?.requests||0;if(n>=30)throw Error('DAILY_LIMIT');tx.set(quota,{requests:n+1,updatedAt:new Date().toISOString()});});
 const response=await fetch('https://api.openai.com/v1/responses',{method:'POST',headers:{Authorization:'Bearer '+key.value(),'Content-Type':'application/json'},body:JSON.stringify(apiRequest(data,m)),signal:AbortSignal.timeout(80000)});
 if(!response.ok){res.status(502).json({error:'OpenAI 응답 실패 · 키·사용 한도·모델 연결을 확인하세요. 자동 재시도하지 않았습니다.'});return;}
 const answer=parseAnswer(await response.json(),data),result={...answer,model:m,generatedAt:new Date().toISOString(),promptVersion:PROMPT_VERSION};if(data.kind==='news')await cache.set(result);res.json({...result,cached:false});
 }catch(e){res.status(e.message==='DAILY_LIMIT'?429:502).json({error:e.message==='DAILY_LIMIT'?'서울 날짜 기준 하루 30회 분석 상한에 도달했습니다.':'분석을 완료하지 못했습니다. 입력은 보존됩니다. 자동 재시도하지 않습니다.'});}
});
