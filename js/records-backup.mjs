// 기록보관실 — 일반 기록(youtube/news/idea/chart/memo, kind!=='study') 전체 내보내기/복원.
// 공부노트는 이미 자기 전용 백업(js/study/study-core.mjs buildBackup/parseBackup)이 있으므로
// 이 모듈은 그것과 별개로 존재하고, 공부노트 기록은 다루지 않는다(호출 쪽에서 kind로 분기).
// 이미지도 실제 파일(base64)로 함께 담는다 — study 쪽과 같은 원칙, Storage 참조만 남기지 않는다.

export const RECORD_BACKUP_FORMAT = 'records-backup/1';

/* record: records.html 의 in-memory 레코드 객체(반드시 attachments[] 가 최신 어댑터로 정규화된 상태로 전달 —
   getAttachments(r) 를 먼저 거쳐서 넘길 것. 이 함수는 그 필드가 무엇이든 그대로 백업에 담기만 한다).
   images: {attachmentId: dataURL} — 실제로 base64 변환에 성공한 것만. */
export function buildRecordBackup(record, images, now) {
  if (!record || typeof record !== 'object') throw new Error('NO_RECORD');
  if (record.kind === 'study') throw new Error('USE_STUDY_BACKUP');
  const {id, ...fields} = record;
  return {format: RECORD_BACKUP_FORMAT, exportedAt: new Date(now || Date.now()).toISOString(), recordId: id, record: fields, images: images || {}};
}

export function parseRecordBackup(json) {
  let b;
  try { b = typeof json === 'string' ? JSON.parse(json) : json; } catch (e) { throw new Error('BACKUP_PARSE'); }
  if (!b || b.format !== RECORD_BACKUP_FORMAT || !b.record || typeof b.record !== 'object') throw new Error('BACKUP_FORMAT');
  if (b.record.kind === 'study') throw new Error('USE_STUDY_RESTORE');
  return b;
}

/* 복원용 attachments[] 재구성 — 파일(base64)이 있으면 '다시 올릴 대상'으로, 없으면 원본 주소를 그대로
   쓸지(reachable) 판단은 호출 쪽(records.html, 실제 업로드/이미지 로드는 DOM API 필요)이 한다.
   여기서는 "이 항목이 이미지 데이터를 갖고 있는가"만 순수하게 판단. */
export function backupHasImageFor(backup, attachmentId) {
  return !!(backup && backup.images && backup.images[attachmentId]);
}

/* 복원된 첨부 배열을 만든다 — reupload(id)=>{path,url}|null, keepOriginal(id)=>boolean(원본 주소가 지금도 열리는지)
   는 호출 쪽에서 실제로 fetch/Storage 업로드/이미지 로드 확인을 마친 뒤 넘겨주는 동기 맵으로 받는다
   (비동기 작업 자체는 DOM 쪽에서 수행 — 이 함수는 그 결과를 attachments[] 모양으로 정리하는 순수 로직). */
export function rebuildAttachmentsFromResults(originalAttachments, results) {
  return (originalAttachments || []).map(function (a) {
    const r = (results && results[a.id]) || null;
    if (r && r.status === 'reuploaded') return {id: a.id, path: r.path, url: r.url, name: a.name || '', size: a.size || 0, type: a.type || '', caption: a.caption || '', order: a.order || 0, addedAt: a.addedAt || Date.now()};
    if (r && r.status === 'linked') return {id: a.id, path: a.path || '', url: a.url, name: a.name || '', size: a.size || 0, type: a.type || '', caption: a.caption || '', order: a.order || 0, addedAt: a.addedAt || Date.now()};
    return {id: a.id, path: '', url: '', name: a.name || '', size: a.size || 0, type: a.type || '', caption: a.caption || '', order: a.order || 0, addedAt: a.addedAt || Date.now(), status: 'missing'};
  });
}
