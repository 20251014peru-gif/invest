// 기록보관실 — 미업로드 사진 임시 저장(IndexedDB). base64로 localStorage/Firestore에 넣지 않는다는
// 원칙을 지키면서도 새로고침에 사진이 조용히 사라지지 않도록, 아직 Storage에 안 올라간 파일의 원본
// Blob과 이미 올라간 파일의 참조(URL)를 함께 보관한다. records.html이 dynamic import로 불러와 쓴다.

const DB_NAME = 'records_drafts_v1';
const STORE = 'drafts';

function openDb() {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === 'undefined' || !indexedDB) { reject(new Error('INDEXEDDB_UNAVAILABLE')); return; }
    let req;
    try { req = indexedDB.open(DB_NAME, 1); } catch (e) { reject(e); return; }
    req.onupgradeneeded = () => { req.result.createObjectStore(STORE, {keyPath: 'draftId'}); };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error || new Error('INDEXEDDB_OPEN_FAILED'));
    req.onblocked = () => reject(new Error('INDEXEDDB_BLOCKED'));
  });
}

export function isAvailable() {
  try { return typeof indexedDB !== 'undefined' && !!indexedDB; } catch (e) { return false; }
}

export async function saveDraft(draftId, payload) {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    let tx;
    try { tx = db.transaction(STORE, 'readwrite'); } catch (e) { reject(e); return; }
    tx.objectStore(STORE).put({draftId, updatedAt: Date.now(), ...payload});
    tx.oncomplete = () => resolve(true);
    tx.onerror = () => reject(tx.error || new Error('INDEXEDDB_WRITE_FAILED'));
    tx.onabort = () => reject(tx.error || new Error('INDEXEDDB_WRITE_ABORTED'));
  });
}

export async function loadDraft(draftId) {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    let tx;
    try { tx = db.transaction(STORE, 'readonly'); } catch (e) { reject(e); return; }
    const req = tx.objectStore(STORE).get(draftId);
    req.onsuccess = () => resolve(req.result || null);
    req.onerror = () => reject(req.error || new Error('INDEXEDDB_READ_FAILED'));
  });
}

export async function deleteDraft(draftId) {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    let tx;
    try { tx = db.transaction(STORE, 'readwrite'); } catch (e) { reject(e); return; }
    tx.objectStore(STORE).delete(draftId);
    tx.oncomplete = () => resolve(true);
    tx.onerror = () => reject(tx.error || new Error('INDEXEDDB_DELETE_FAILED'));
  });
}

export async function listDraftIds() {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    let tx;
    try { tx = db.transaction(STORE, 'readonly'); } catch (e) { reject(e); return; }
    const req = tx.objectStore(STORE).getAllKeys();
    req.onsuccess = () => resolve(req.result || []);
    req.onerror = () => reject(req.error || new Error('INDEXEDDB_LIST_FAILED'));
  });
}
