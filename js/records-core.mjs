// 기록보관실 — 가벼운 기록/사진 첨부/관계/나중에 볼 것: DOM 비의존 순수 로직.
// records.html 이 dynamic import 로 불러와 쓰고(js/records-core.test 로 단위 시험도 이 파일을 그대로 씀).

export const MAX_IMAGE_BYTES = 8 * 1024 * 1024;
export const EXT_BY_TYPE = {'image/png': 'png', 'image/jpeg': 'jpg', 'image/gif': 'gif', 'image/webp': 'webp', 'image/avif': 'avif', 'image/bmp': 'bmp', 'image/heic': 'heic', 'image/heif': 'heif'};
const PREVIEWABLE_TYPES = {'image/png': 1, 'image/jpeg': 1, 'image/gif': 1, 'image/webp': 1, 'image/avif': 1, 'image/bmp': 1};

export function extFromType(type) { return EXT_BY_TYPE[String(type || '').toLowerCase()] || 'img'; }
export function isPreviewableType(type) { return !!PREVIEWABLE_TYPES[String(type || '').toLowerCase()]; }

/* ── 첨부 어댑터 — 신규 attachments[] 와 구버전 단일 image/imagePath 를 한 형태로 ── */
export function getAttachments(r) {
  if (r && Array.isArray(r.attachments) && r.attachments.length) {
    return r.attachments.slice().sort(function (a, b) { return (a.order || 0) - (b.order || 0); });
  }
  if (r && r.image) {
    return [{id: 'legacy', path: r.imagePath || '', url: r.image, name: '', size: 0, type: '', caption: '', order: 0, addedAt: r.createdAt || 0, status: 'stored', legacy: true}];
  }
  return [];
}

/* 저장 시 image/imagePath 를 대표 사진(첫 장)의 투영으로 유지 — 구버전 소비 경로(갤러리뷰·종목 표지·내보내기) 호환 */
export function coverProjection(attachments) {
  var first = (attachments || [])[0];
  return {image: first ? (first.url || '') : '', imagePath: first ? (first.path || '') : ''};
}

export function newAttachmentId() {
  return 'att_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2, 8);
}

export function attachmentStoragePath(kstDateStr, assetId, type) {
  return 'records_images/' + kstDateStr + '/rec_' + assetId + '.' + extFromType(type);
}

/* ── 최소 저장 조건 — 제목/본문/링크/사진 중 하나만 있어도 저장 가능, 전부 비면 차단 ── */
export function isEmptyRecordDraft(d) {
  d = d || {};
  var hasAttachments = (d.attachmentsCount || 0) > 0;
  return !String(d.title || '').trim() && !String(d.body || '').trim() && !String(d.link || '').trim() && !hasAttachments;
}

/* ── 자동 제목 — 제목이 비어 있을 때만 1회 생성. 사용자가 적은 제목은 절대 덮지 않는다 ── */
export function autoTitle(d) {
  d = d || {};
  var body = String(d.body || '');
  var firstLine = body.split(/\r?\n/).map(function (s) { return s.trim(); }).filter(Boolean)[0];
  if (firstLine) return firstLine.length > 40 ? firstLine.slice(0, 40) + '…' : firstLine;
  var n = d.attachmentsCount || 0;
  if (n > 0) return '사진 기록' + (d.dateStr ? ' · ' + d.dateStr : '') + (n > 1 ? ' (' + n + '장)' : '');
  var link = String(d.link || '').trim();
  if (link) {
    try {
      var h = new URL(link).hostname.replace(/^www\./, '');
      return h + (d.dateStr ? ' · ' + d.dateStr : '');
    } catch (e) { /* 잘못된 URL 형식이면 무시하고 아래로 */ }
  }
  return (d.kindLabel || '기록') + (d.dateStr ? ' · ' + d.dateStr : '');
}

/* ── checks[] — 확인할 것/나중에 볼 것. id 는 새 항목에만 부여(기존은 인덱스로 대체) ── */
export function newCheckId() { return 'chk_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2, 6); }

export const FOLLOWUP_TYPES = {
  lookup: '🔎 알아보기',
  think: '💭 더 생각하기',
  reread: '📖 다시 읽기'
};

export function checkDueKey(recordId, check, index) {
  var suffix = (check && check.id) ? check.id : String(index);
  return recordId + '#' + suffix;
}

/* records/todos 스냅샷에서 "나중에 볼 것" 항목을 모은다.
   기존 "오늘의 체크리스트" 위젯과 신규 통합보기가 이 함수 하나를 같이 써서 중복/불일치를 막는다.
   opts.onlyDate: 그 날짜만(오늘 위젯). 생략하면 모든 날짜 + 빈 날짜(기한 없음) 포함(통합보기). */
export function collectDueChecks(records, todos, opts) {
  opts = opts || {};
  var doneKeys = {};
  (todos || []).forEach(function (t) { if (t && t.dueKey && t.done) doneKeys[t.dueKey] = true; });
  var out = [];
  (records || []).forEach(function (r) {
    (r.checks || []).forEach(function (c, i) {
      var d = String((c && c.date) || '');
      if (opts.onlyDate != null) { if (d !== opts.onlyDate) return; }
      else if (!d && opts.includeNoDate === false) return;
      var key = checkDueKey(r.id, c, i);
      var done = !!doneKeys[key];
      if (opts.onlyUndone && done) return;
      if (opts.onlyDone && !done) return;
      out.push({recordId: r.id, record: r, check: c, index: i, dueKey: key, done: done, date: d, followUpType: (c && c.followUpType) || ''});
    });
  });
  return out;
}

/* ── 나중에 볼 것 통합보기 — 공부노트 재검토 항목(읽기 전용 행)도 같은 형태로 섞는다 ── */
export function studyReviewItems(records, isStudyNeedsReview) {
  return (records || []).filter(function (r) { return isStudyNeedsReview(r); }).map(function (r) {
    return {recordId: r.id, record: r, isStudy: true, date: r.reviewAt || '', done: false, followUpType: 'reread'};
  });
}

/* ── 관계 — 기존 REL_TYPE_LBL/REL_REV_LBL 에 추가할 신규 타입 2개(기존 타입은 그대로 보존) ── */
export const NEW_REL_TYPES = {
  derived_from: {fwd: '생각의 출발점', rev: '이 기록에서 생각이 이어짐'},
  synthesizes: {fwd: '정리에 사용한 자료', rev: '이 기록이 정리에 포함됨'}
};

export function relationsHasType(relations, targetId, type) {
  return (relations || []).some(function (x) { return x && x.targetId === targetId && (x.type || 'related') === type; });
}

export function makeRelation(targetId, type, note) {
  return {relationId: 'rel_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2, 6), targetId: targetId, type: type || 'related', note: note || '', createdAt: Date.now()};
}
