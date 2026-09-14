import crypto from 'node:crypto';
import {initializeApp, getApps} from 'firebase-admin/app';
import {getFirestore, FieldValue} from 'firebase-admin/firestore';
import {onCall, HttpsError} from 'firebase-functions/v2/https';
import {defineSecret} from 'firebase-functions/params';

if (!getApps().length) initializeApp();
const db=getFirestore();
const AI_ACCESS_CODE=defineSecret('AI_ACCESS_CODE');
const REGION='asia-northeast3';
const MAX_UID_FAILS_PER_DAY=5;
const MAX_IP_FAILS_PER_DAY=20;
const MIN_CODE_LENGTH=16;

function kstDay(){
  const now=new Date(Date.now()+9*60*60*1000);
  return now.toISOString().slice(0,10);
}
function sha256(v){return crypto.createHash('sha256').update(String(v||'')).digest('hex');}
function safeEqual(a,b){
  const aa=Buffer.from(String(a||'')); const bb=Buffer.from(String(b||''));
  if(aa.length!==bb.length) return false;
  return crypto.timingSafeEqual(aa,bb);
}
async function failureCount(ref){const s=await ref.get();return Number(s.exists?s.data()?.count||0:0);}

export const registerAiDevice=onCall({region:REGION,secrets:[AI_ACCESS_CODE],timeoutSeconds:30,memory:'128MiB'},async request=>{
  const uid=request.auth?.uid;
  if(!uid) throw new HttpsError('unauthenticated','Firebase sign-in required.');
  const code=String(request.data?.code||'').trim();
  if(code.length<MIN_CODE_LENGTH||code.length>128) throw new HttpsError('invalid-argument',`Access code must be ${MIN_CODE_LENGTH}-128 characters.`);

  const day=kstDay();
  const ip=String(request.rawRequest?.ip||request.rawRequest?.headers?.['x-forwarded-for']||'unknown').split(',')[0].trim();
  const ipHash=sha256(ip).slice(0,24);
  const uidFailRef=db.collection('ai_access_failures').doc(`uid_${uid}_${day}`);
  const ipFailRef=db.collection('ai_access_failures').doc(`ip_${ipHash}_${day}`);
  const [uidFails,ipFails]=await Promise.all([failureCount(uidFailRef),failureCount(ipFailRef)]);
  if(uidFails>=MAX_UID_FAILS_PER_DAY||ipFails>=MAX_IP_FAILS_PER_DAY){
    throw new HttpsError('resource-exhausted','Too many failed access-code attempts today.');
  }

  if(!safeEqual(code,AI_ACCESS_CODE.value())){
    const patch={day,count:FieldValue.increment(1),updatedAt:FieldValue.serverTimestamp()};
    await Promise.all([
      uidFailRef.set({...patch,scope:'uid'}, {merge:true}),
      ipFailRef.set({...patch,scope:'ip'}, {merge:true})
    ]);
    throw new HttpsError('permission-denied','Access code does not match.');
  }

  await db.collection('ai_users').doc(uid).set({
    enabled:true,registeredAt:FieldValue.serverTimestamp(),registrationMethod:'ACCESS_CODE'
  },{merge:true});
  return {ok:true,uid};
});
