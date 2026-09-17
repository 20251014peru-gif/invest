// 공부노트 저장 어댑터 — 모든 공부노트 쓰기는 이 트랜잭션을 거친다(변경 버전 검사·재시도 중복 방지·관계 병합).
import {commitStudy, mergeRelations, studyFingerprint} from './study-core.mjs';

const EXT = {'image/png': 'png', 'image/jpeg': 'jpg', 'image/gif': 'gif', 'image/webp': 'webp', 'image/avif': 'avif', 'image/bmp': 'bmp'};
export const MAX_IMAGE_BYTES = 8 * 1024 * 1024;

export function makeStudyStore(db, storage, {now = () => Date.now(), kstDate, preserveChecks = () => false} = {}) {
  const col = () => db.collection('records');
  return {
    newId() { return col().doc().id; },
    async read(id) { const s = await col().doc(id).get(); return s.exists ? {id: s.id, ...s.data()} : null; },
    // expected: 편집 시작 시점 studyFingerprint(null=새 노트). 다른 기기 변경이면 CONFLICT(쓰기 없음).
    async save({id, patch, expected, reason = 'edit', relations = null, operationId}) {
      const ref = col().doc(id);
      return db.runTransaction(async tx => {
        const snap = await tx.get(ref);
        const current = snap.exists ? snap.data() : null;
        if (current && operationId && current.studyOperationId === operationId) return {record: {id, ...current}, repeated: true, bytes: 0, level: 'ok'};
        const t = now();
        const {result, bytes, level} = commitStudy(current, current && preserveChecks() ? {...patch, checks: current.checks || []} : patch, expected, {now: t, reason, relations, date: kstDate ? kstDate(t) : ''});
        result.studyOperationId = operationId || ('op_' + t);
        if (current) tx.update(ref, result); else tx.set(ref, result);
        return {record: {id, ...(current || {}), ...result}, repeated: false, bytes, level};
      });
    },
    // 관계만 바꾸는 경로(읽기 화면의 연결 추가/삭제) — 서버 최신 목록에 병합
    async changeRelations(id, change) {
      const ref = col().doc(id);
      return db.runTransaction(async tx => {
        const snap = await tx.get(ref);
        if (!snap.exists) throw new Error('NOT_FOUND');
        const rels = mergeRelations(snap.data().relations, change, now());
        tx.update(ref, {relations: rels});
        return rels;
      });
    },
    fingerprint: studyFingerprint,
    // 이미지 → Storage. 기존 기록보관실 이미지와 같은 경로 규칙(records_images/날짜/파일). 기존 파일은 지우지 않는다.
    async uploadImage(blob, {name = '', assetId} = {}) {
      if (!storage) throw new Error('STORAGE_UNAVAILABLE');
      const type = String(blob?.type || '');
      if (!/^image\//.test(type)) throw new Error('NOT_IMAGE');
      if (blob.size > MAX_IMAGE_BYTES) throw new Error('IMAGE_TOO_LARGE');
      const t = now();
      const id = assetId || ('img_' + t.toString(36) + '_' + Math.random().toString(36).slice(2, 8));
      const date = kstDate ? kstDate(t) : new Date(t).toISOString().slice(0, 10);
      const path = 'records_images/' + date + '/study_' + id + '.' + (EXT[type] || 'img');
      const snap = await storage.ref(path).put(blob, {contentType: type});
      const url = await snap.ref.getDownloadURL();
      return {id, path, url, name: String(name || '').slice(0, 120), size: blob.size, type, addedAt: t};
    }
  };
}
