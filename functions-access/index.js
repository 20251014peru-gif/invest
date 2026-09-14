import crypto from 'node:crypto';
import {initializeApp, getApps} from 'firebase-admin/app';
import {getFirestore, FieldValue} from 'firebase-admin/firestore';
import {onCall, HttpsError} from 'firebase-functions/v2/https';
import {defineSecret} from 'firebase-functions/params';

if (!getApps().length) initializeApp();
const db=getFirestore();
const AI_ACCESS_PIN=defineSecret('AI_ACCESS_PIN');
const REGION='asia-northeast3';
const MAX_FAILS_PER_DAY=5;

function kstDay(){
  const now=new Date(Date.now()+9*60*60*1000);
  return now.toISOString().slice(0,10);
}
function safeEqual(a,b){
  const aa=Buffer.from(String(a||'')); const bb=Buffer.from(String(b||''));
  if(aa.length!==bb.length) return false;
  return crypto.timingSafeEqual(aa,bb);
}

export const registerAiDevice=onCall({region:REGION,secrets:[AI_ACCESS_PIN],timeoutSeconds:30,memory:'128MiB'},async request=>{
  const uid=request.auth?.uid;
  if(!uid) throw new HttpsError('unauthenticated','Firebase sign-in required.');
  const pin=String(request.data?.pin||'').trim();
  if(pin.length<4||pin.length>64) throw new HttpsError('invalid-argument','Invalid access PIN.');
  const day=kstDay(); const failRef=db.collection('ai_access_failures').doc(`${uid}_${day}`);
  const failSnap=await failRef.get(); const fails=Number(failSnap.exists?failSnap.data()?.count||0:0);
  if(fails>=MAX_FAILS_PER_DAY) throw new HttpsError('resource-exhausted','Too many failed PIN attempts today.');
  if(!safeEqual(pin,AI_ACCESS_PIN.value())){
    await failRef.set({uid,day,count:FieldValue.increment(1),updatedAt:FieldValue.serverTimestamp()},{merge:true});
    throw new HttpsError('permission-denied','Access PIN does not match.');
  }
  await db.collection('ai_users').doc(uid).set({enabled:true,registeredAt:FieldValue.serverTimestamp(),registrationMethod:'PIN'},{merge:true});
  return {ok:true,uid};
});
