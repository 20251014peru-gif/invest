import test from 'node:test';
import assert from 'node:assert/strict';
import * as D from '../js/records-drafts.mjs';

// node:test 환경에는 IndexedDB가 없다 — 이 자체가 "이 기기에 임시 저장할 수 없는 상황"의 자연스러운
// 재현이다(사생활 보호 모드·저장소 접근 차단 등과 같은 실패 모드). 조용히 무시하지 않고 명확히
// reject 하는지, 그리고 그 실패를 records.html 쪽 코드가 사용자에게 알릴 수 있는 형태인지 확인한다.

test('isAvailable() is false when indexedDB is absent (e.g. node, or a browser that blocks it)', () => {
  assert.equal(D.isAvailable(), false);
});

test('saveDraft/loadDraft/deleteDraft reject with a clear, catchable error instead of hanging or silently no-op-ing', async () => {
  await assert.rejects(() => D.saveDraft('new', {items: [{id: 'a'}]}), /INDEXEDDB_UNAVAILABLE/);
  await assert.rejects(() => D.loadDraft('new'), /INDEXEDDB_UNAVAILABLE/);
  await assert.rejects(() => D.deleteDraft('new'), /INDEXEDDB_UNAVAILABLE/);
  await assert.rejects(() => D.listDraftIds(), /INDEXEDDB_UNAVAILABLE/);
});
