import test from 'node:test';
import assert from 'node:assert/strict';
import * as B from '../js/records-backup.mjs';

const sampleRecord = {
  id: 'rec1', kind: 'memo', date: '2026-09-17', title: '백업 시험',
  attachments: [
    {id: 'a1', path: 'records_images/2026-09-17/rec_a1.png', url: 'https://x/a1.png', name: 'a1.png', size: 100, type: 'image/png', caption: '첫 장', order: 0, addedAt: 1},
    {id: 'a2', path: 'records_images/2026-09-17/rec_a2.png', url: 'https://x/a2.png', name: 'a2.png', size: 200, type: 'image/png', caption: '둘째 장', order: 1, addedAt: 2}
  ],
  relations: [{relationId: 'rel1', targetId: 'rec2', type: 'related', note: '', createdAt: 1}],
  checks: [{id: 'chk1', date: '', what: '나중에 볼 것', action: '', followUpType: 'lookup'}]
};

test('buildRecordBackup: strips id into recordId, keeps all other fields (relations/checks/attachments) unfiltered', () => {
  const images = {a1: 'data:image/png;base64,AAA='};
  const backup = B.buildRecordBackup(sampleRecord, images, 1758100000000);
  assert.equal(backup.format, 'records-backup/1');
  assert.equal(backup.recordId, 'rec1');
  assert.equal(backup.record.id, undefined);
  assert.equal(backup.record.title, '백업 시험');
  assert.deepEqual(backup.record.attachments, sampleRecord.attachments);
  assert.deepEqual(backup.record.relations, sampleRecord.relations);
  assert.deepEqual(backup.record.checks, sampleRecord.checks);
  assert.deepEqual(backup.images, images);
});

test('buildRecordBackup refuses study records (they have their own backup format)', () => {
  assert.throws(() => B.buildRecordBackup({...sampleRecord, kind: 'study'}, {}), /USE_STUDY_BACKUP/);
});

test('parseRecordBackup: round-trips buildRecordBackup output, rejects wrong format/study records', () => {
  const backup = B.buildRecordBackup(sampleRecord, {}, Date.now());
  const parsed = B.parseRecordBackup(JSON.stringify(backup));
  assert.equal(parsed.recordId, 'rec1');
  assert.throws(() => B.parseRecordBackup('{"format":"something-else","record":{}}'), /BACKUP_FORMAT/);
  assert.throws(() => B.parseRecordBackup('not json'), /BACKUP_PARSE/);
  assert.throws(() => B.parseRecordBackup(JSON.stringify({format: 'records-backup/1', record: {kind: 'study'}})), /USE_STUDY_RESTORE/);
});

test('backupHasImageFor', () => {
  const backup = B.buildRecordBackup(sampleRecord, {a1: 'data:x'}, Date.now());
  assert.equal(B.backupHasImageFor(backup, 'a1'), true);
  assert.equal(B.backupHasImageFor(backup, 'a2'), false);
  assert.equal(B.backupHasImageFor(null, 'a1'), false);
});

test('rebuildAttachmentsFromResults: reuploaded > linked(original url still reachable) > missing(neither)', () => {
  const results = {
    a1: {status: 'reuploaded', path: 'new/path/a1.png', url: 'https://new/a1.png'},
    a2: {status: 'linked'}
  };
  const rebuilt = B.rebuildAttachmentsFromResults(sampleRecord.attachments, results);
  assert.equal(rebuilt[0].url, 'https://new/a1.png');
  assert.equal(rebuilt[0].path, 'new/path/a1.png');
  assert.equal(rebuilt[0].caption, '첫 장'); // 순서/설명 보존
  assert.equal(rebuilt[1].url, 'https://x/a2.png'); // linked — 원래 주소 그대로
  assert.equal(rebuilt[1].caption, '둘째 장');

  const noResults = B.rebuildAttachmentsFromResults(sampleRecord.attachments, {});
  assert.equal(noResults[0].status, 'missing');
  assert.equal(noResults[0].url, '');
  assert.equal(noResults[0].caption, '첫 장'); // 누락돼도 설명·순서는 남겨 자리 표시
});
