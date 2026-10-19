import {onRequest} from 'firebase-functions/v2/https';
import {defineSecret} from 'firebase-functions/params';
import {initializeApp} from 'firebase-admin/app';
import {getAuth} from 'firebase-admin/auth';
import {getFirestore} from 'firebase-admin/firestore';
import {createMfLatestHandler} from './handler.js';

initializeApp();
// 기존 macroAi 와 같은 비밀값(본인 UID). 값은 코드·로그에 남기지 않는다.
const owner = defineSecret('MACRO_OWNER_UID');
// 클라이언트 규칙으로 비로그인 접근이 막혀 있음을 확인한 chatgpt_macro_private 하위(2026-10-19 비로그인 REST 403).
const LATEST = 'chatgpt_macro_private/multifactor_kr/snapshots/latest';

export const mfLatest = onRequest(
  {region: 'asia-northeast3', cors: ['https://20251014peru-gif.github.io'], secrets: [owner], timeoutSeconds: 30, memory: '256MiB', maxInstances: 2},
  createMfLatestHandler({
    verifyIdToken: (token, checkRevoked) => getAuth().verifyIdToken(token, checkRevoked),
    readLatest: async () => { const snap = await getFirestore().doc(LATEST).get(); return snap.exists ? snap.data() : null; },
    ownerUid: () => owner.value(),
  }),
);
