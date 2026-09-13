import {revisionPatch} from './research-core.mjs';
// Same public Firebase app configuration and records collection as records.html.
const config={apiKey:'AIzaSyAyG1chECYsbO7cSZUuXmNa0_KDYBmahPY',authDomain:'my-system-25497.firebaseapp.com',projectId:'my-system-25497',storageBucket:'my-system-25497.firebasestorage.app'};
const sdk='https://www.gstatic.com/firebasejs/10.12.2/';
function script(name){return new Promise((resolve,reject)=>{const s=document.createElement('script');const timer=setTimeout(()=>reject(new Error('연결 시간 초과')),15000);s.src=sdk+name;s.onload=()=>{clearTimeout(timer);resolve();};s.onerror=()=>{clearTimeout(timer);s.remove();reject(new Error('기록보관실 연결 파일을 불러오지 못했습니다.'));};document.head.append(s);});}
export function makeRepository(db){return {
  watch(next,error){return db.collection('records').where('topics','array-contains','CPI').onSnapshot(s=>next(s.docs.map(d=>({id:d.id,...d.data()})).sort((a,b)=>(b.updatedAt||b.createdAt||0)-(a.updatedAt||a.createdAt||0))),error);},
  async save(id,patch,expected,operationId){const ref=db.collection('records').doc(id);return db.runTransaction(async tx=>{const snap=await tx.get(ref),current=snap.exists?snap.data():null;if(current?.researchOperationId===operationId)return current;const result={...revisionPatch(current,patch,expected,Date.now()),researchOperationId:operationId};tx.set(ref,result,{merge:true});return {...current,...result};});},
  async read(id){const s=await db.collection('records').doc(id).get();return s.exists?{id:s.id,...s.data()}:null;}
};}
export async function connectRecords(){if(!globalThis.firebase?.initializeApp)await script('firebase-app-compat.js');if(!firebase.auth)await script('firebase-auth-compat.js');if(!firebase.firestore)await script('firebase-firestore-compat.js');const app=firebase.apps.length?firebase.app():firebase.initializeApp(config);const auth=app.auth();let user=auth.currentUser;if(!user){user=await new Promise((resolve,reject)=>{const off=auth.onAuthStateChanged(u=>{off();resolve(u);},reject);});}if(!user)user=(await auth.signInAnonymously()).user;return {...makeRepository(app.firestore()),uid:user.uid};}
