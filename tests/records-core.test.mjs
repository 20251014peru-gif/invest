import test from 'node:test';
import assert from 'node:assert/strict';
import * as R from '../js/records-core.mjs';

test('getAttachments: prefers attachments[], falls back to legacy image, sorts by order', () => {
  assert.deepEqual(R.getAttachments({}), []);
  const legacy = R.getAttachments({image: 'https://x/a.png', imagePath: 'p/a.png'});
  assert.equal(legacy.length, 1);
  assert.equal(legacy[0].url, 'https://x/a.png');
  assert.equal(legacy[0].legacy, true);
  const multi = R.getAttachments({attachments: [{id: 'b', order: 2, url: 'u2'}, {id: 'a', order: 1, url: 'u1'}]});
  assert.deepEqual(multi.map(a => a.id), ['a', 'b']);
  // attachments[] takes priority over legacy image even if both exist
  const both = R.getAttachments({image: 'https://legacy', attachments: [{id: 'x', order: 0, url: 'u'}]});
  assert.equal(both.length, 1);
  assert.equal(both[0].id, 'x');
});

test('coverProjection mirrors first attachment for legacy consumers', () => {
  assert.deepEqual(R.coverProjection([]), {image: '', imagePath: ''});
  assert.deepEqual(R.coverProjection([{url: 'u1', path: 'p1'}, {url: 'u2', path: 'p2'}]), {image: 'u1', imagePath: 'p1'});
});

test('isEmptyRecordDraft blocks only when title/body/link/attachments are all empty', () => {
  assert.equal(R.isEmptyRecordDraft({}), true);
  assert.equal(R.isEmptyRecordDraft({title: '  '}), true);
  assert.equal(R.isEmptyRecordDraft({title: '제목'}), false);
  assert.equal(R.isEmptyRecordDraft({body: '문장 하나'}), false);
  assert.equal(R.isEmptyRecordDraft({link: 'https://a.b'}), false);
  assert.equal(R.isEmptyRecordDraft({attachmentsCount: 1}), false);
  assert.equal(R.isEmptyRecordDraft({attachmentsCount: 0}), true);
});

test('autoTitle: body first line > photo-only > link domain > kind fallback, never called when title exists', () => {
  assert.equal(R.autoTitle({body: '오늘 생각난 것\n둘째 줄'}), '오늘 생각난 것');
  const long = 'a'.repeat(60);
  assert.equal(R.autoTitle({body: long}), 'a'.repeat(40) + '…');
  assert.equal(R.autoTitle({attachmentsCount: 1, dateStr: '2026-09-17'}), '사진 기록 · 2026-09-17');
  assert.equal(R.autoTitle({attachmentsCount: 3, dateStr: '2026-09-17'}), '사진 기록 · 2026-09-17 (3장)');
  assert.equal(R.autoTitle({link: 'https://www.naver.com/x', dateStr: '2026-09-17'}), 'naver.com · 2026-09-17');
  assert.equal(R.autoTitle({link: 'not a url', kindLabel: '메모', dateStr: '2026-09-17'}), '메모 · 2026-09-17');
  assert.equal(R.autoTitle({kindLabel: '메모', dateStr: '2026-09-17'}), '메모 · 2026-09-17');
});

test('checkDueKey: stable per check id, falls back to index for legacy checks (no id)', () => {
  assert.equal(R.checkDueKey('rec1', {id: 'chk_a'}, 0), 'rec1#chk_a');
  assert.equal(R.checkDueKey('rec1', {}, 2), 'rec1#2');
});

test('collectDueChecks: onlyDate scopes to one day (today widget), omitted scopes to all dates incl. blank (later view)', () => {
  const records = [
    {id: 'r1', checks: [{date: '2026-09-17', what: 'A'}, {date: '', what: 'B (기한 없음)'}]},
    {id: 'r2', checks: [{date: '2026-09-18', what: 'C'}]}
  ];
  const today = R.collectDueChecks(records, [], {onlyDate: '2026-09-17'});
  assert.deepEqual(today.map(x => x.dueKey), ['r1#0']);

  const all = R.collectDueChecks(records, [], {});
  assert.deepEqual(all.map(x => x.dueKey).sort(), ['r1#0', 'r1#1', 'r2#0'].sort());

  const noBlank = R.collectDueChecks(records, [], {includeNoDate: false});
  assert.ok(!noBlank.some(x => x.dueKey === 'r1#1'));
});

test('collectDueChecks: reconciles completion against records_todos dueKey markers (same mechanism as existing widget)', () => {
  const records = [{id: 'r1', checks: [{date: '2026-09-17', what: 'A'}]}];
  const todos = [{dueKey: 'r1#0', done: true}];
  const items = R.collectDueChecks(records, todos, {});
  assert.equal(items[0].done, true);
  const onlyUndone = R.collectDueChecks(records, todos, {onlyUndone: true});
  assert.equal(onlyUndone.length, 0);
  const onlyDone = R.collectDueChecks(records, todos, {onlyDone: true});
  assert.equal(onlyDone.length, 1);
});

test('collectDueChecks does not duplicate when the same record has multiple checks with distinct ids', () => {
  const records = [{id: 'r1', checks: [{id: 'chk_a', date: '', what: 'X'}, {id: 'chk_b', date: '', what: 'Y'}]}];
  const items = R.collectDueChecks(records, [], {});
  assert.deepEqual(items.map(x => x.dueKey).sort(), ['r1#chk_a', 'r1#chk_b']);
});

test('studyReviewItems maps needs-review study notes into the same shape, read-only (reread)', () => {
  const records = [{id: 's1', kind: 'study', reviewAt: '2026-09-01'}, {id: 's2', kind: 'study'}];
  const needsReview = r => r.id === 's1';
  const items = R.studyReviewItems(records, needsReview);
  assert.equal(items.length, 1);
  assert.equal(items[0].recordId, 's1');
  assert.equal(items[0].followUpType, 'reread');
  assert.equal(items[0].isStudy, true);
});

test('relationsHasType / makeRelation', () => {
  const rels = [{targetId: 't1', type: 'related'}];
  assert.equal(R.relationsHasType(rels, 't1', 'related'), true);
  assert.equal(R.relationsHasType(rels, 't1', 'derived_from'), false);
  const rel = R.makeRelation('t2', 'derived_from', '');
  assert.equal(rel.targetId, 't2');
  assert.equal(rel.type, 'derived_from');
  assert.ok(rel.relationId);
  assert.ok(rel.createdAt > 0);
});

test('draftNeedsBlob: only non-stored items need their original file bytes kept for retry', () => {
  assert.equal(R.draftNeedsBlob({status: 'stored'}), false);
  assert.equal(R.draftNeedsBlob({status: 'uploading'}), true);
  assert.equal(R.draftNeedsBlob({status: 'error'}), true);
  assert.equal(R.draftNeedsBlob(null), false);
});

test('mergeDraftAttachments: appends draft-only items, current (already loaded) wins on id clash', () => {
  const current = [{id: 'a', url: 'u-a', status: 'stored'}];
  const draft = [{id: 'a', url: 'stale', status: 'stored'}, {id: 'b', url: 'u-b', status: 'uploading'}];
  const merged = R.mergeDraftAttachments(current, draft);
  assert.deepEqual(merged.map(x => x.id), ['a', 'b']);
  assert.equal(merged[0].url, 'u-a'); // 현재(이미 기록에 저장된) 것을 임시 저장분으로 덮어쓰지 않음
  assert.equal(R.mergeDraftAttachments([], null).length, 0);
  assert.equal(R.mergeDraftAttachments(null, [{id: 'x'}]).length, 1);
});

test('attachmentStoragePath / extFromType / isPreviewableType', () => {
  assert.equal(R.attachmentStoragePath('2026-09-17', 'att_1', 'image/png'), 'records_images/2026-09-17/rec_att_1.png');
  assert.equal(R.extFromType('image/heic'), 'heic');
  assert.equal(R.isPreviewableType('image/heic'), false);
  assert.equal(R.isPreviewableType('image/png'), true);
});
