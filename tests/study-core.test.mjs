import test from 'node:test';
import assert from 'node:assert/strict';
import * as S from '../js/study/study-core.mjs';

const T = (text, marks) => ({type: 'text', text, ...(marks ? {marks} : {})});
const P = (...c) => ({type: 'paragraph', content: c});
const H = (level, text) => ({type: 'heading', attrs: {level}, content: [T(text)]});
// 사진 속 ‘AI 속도 조절론’과 비슷한 서식 시험 문서(내용은 서식 시험용 예시 — 사실 확인 대상 아님)
const sample = {type: 'doc', content: [
  H(1, 'AI 속도 조절론 (서식 시험)'),
  P(T('핵심: '), T('굵게', [{type: 'bold'}]), T(' '), T('밑줄', [{type: 'underline'}]), T(' '), T('취소', [{type: 'strike'}]), T(' '), T('빨강', [{type: 'textStyle', attrs: {color: '#c0392b'}}]), T(' '), T('강조', [{type: 'highlight', attrs: {color: '#fff2a8'}}])),
  H(2, '근거'),
  {type: 'bulletList', content: [{type: 'listItem', content: [P(T('상위')), {type: 'bulletList', content: [{type: 'listItem', content: [P(T('하위'))]}]}]}]},
  {type: 'blockquote', content: [P(T('인용문'))]},
  {type: 'table', content: [{type: 'tableRow', content: [{type: 'tableHeader', content: [P(T('구분'))]}, {type: 'tableHeader', content: [P(T('값'))]}]}, {type: 'tableRow', content: [{type: 'tableCell', content: [P(T('A'))]}, {type: 'tableCell', attrs: {colspan: 1}, content: [P(T('1'))]}]}]},
  H(3, '세부'),
  P(T('링크', [{type: 'link', attrs: {href: 'https://example.com/a'}}])),
  {type: 'image', attrs: {assetId: 'a1', alt: '차트', status: 'stored', width: '50%'}},
  {type: 'horizontalRule'},
  H(2, '결론'),
  {type: 'orderedList', attrs: {start: 3}, content: [{type: 'listItem', content: [P(T('셋'))]}]},
  {type: 'taskList', content: [{type: 'taskItem', attrs: {checked: true}, content: [P(T('확인'))]}]}
]};
const assets = {a1: {url: 'https://firebasestorage.googleapis.com/v0/b/x/o/p.png?alt=media'}};

test('plain text projection keeps hierarchy, tables, lists, images', () => {
  const t = S.docToPlainText(sample);
  assert.match(t, /^AI 속도 조절론/);
  assert.match(t, /- 상위\n {2}- 하위/);
  assert.match(t, /> 인용문/);
  assert.match(t, /구분 \| 값\nA \| 1/);
  assert.match(t, /\[이미지: 차트\]/);
  assert.match(t, /3\. 셋/);
  assert.match(t, /\[x\] 확인/);
});

test('read renderer reproduces formats and builds nested collapsible sections', () => {
  const h = S.renderDocHTML(sample, {assets});
  for (const frag of ['<strong>굵게</strong>', '<u>밑줄</u>', '<s>취소</s>', 'color:#c0392b', '<mark style="background-color:#fff2a8">', '<blockquote>', '<table>', '<th>', 'href="https://example.com/a"', 'rel="noopener noreferrer nofollow"', 'style="width:50%"', '<ol start="3">', 'type="checkbox" disabled checked']) assert.ok(h.includes(frag), frag);
  assert.equal((h.match(/<details/g) || []).length, 4);
  assert.equal((h.match(/<details/g) || []).length, (h.match(/<\/details>/g) || []).length);
  assert.ok(h.indexOf('id="sec-2"') > h.indexOf('id="sec-1"'));
  assert.equal(S.headingsOf(sample).length, 4);
  assert.match(S.tocHTML(sample), /data-toc="sec-3"/);
});

test('renderer blocks script, event handlers, dangerous URLs and unknown colors', () => {
  const evil = {type: 'doc', content: [
    P(T('<img src=x onerror=alert(1)>'), T('x', [{type: 'link', attrs: {href: 'javascript:alert(1)'}}]), T('y', [{type: 'textStyle', attrs: {color: 'red;background:url(javascript:1)'}}]), T('z', [{type: 'highlight', attrs: {color: 'expression(1)'}}])),
    {type: 'image', attrs: {src: 'javascript:alert(1)', alt: '"><script>alert(1)</script>'}},
    {type: 'image', attrs: {src: 'data:image/svg+xml,<svg onload=alert(1)>'}},
    {type: 'script', content: [T('alert(1)')]}
  ]};
  const h = S.renderDocHTML(evil);
  assert.ok(!/<script|<img src=x|javascript:|data:image|expression\(/i.test(h), h);
  assert.ok(h.includes('&lt;img src=x onerror=alert(1)&gt;'));
  assert.equal(S.safeHref('JaVaScRiPt:alert(1)'), '');
  assert.equal(S.safeHref('https://a.b/c'), 'https://a.b/c');
});

test('external and missing images are never shown as preserved', () => {
  const h = S.renderDocHTML({type: 'doc', content: [{type: 'image', attrs: {status: 'external', src: 'https://other.site/a.png'}}, {type: 'image', attrs: {status: 'missing', note: 'blob 주소'}}]});
  assert.ok(!h.includes('<img'));
  assert.match(h, /보관되지 않은 외부 이미지/);
  assert.match(h, /가져오지 못한 이미지/);
  const st = S.docStats({type: 'doc', content: [{type: 'image', attrs: {status: 'external'}}, {type: 'image', attrs: {status: 'stored', assetId: 'a'}}]});
  assert.equal(st.imagesExternal, 1); assert.equal(st.imagesStored, 1);
});

test('palette mapping keeps meaning, drops default text/background colors', () => {
  assert.equal(S.nearestPalette('#fff2a8', 'highlight'), '#fff2a8');
  assert.equal(S.nearestPalette('rgb(255, 0, 0)', 'text'), '#c0392b');
  assert.equal(S.nearestPalette('#000', 'text'), null);
  assert.equal(S.nearestPalette('#ffffff', 'highlight'), null);
  assert.equal(S.nearestPalette('yellow', 'highlight'), '#fff2a8');
  assert.equal(S.nearestPalette('url(x)', 'text'), null);
});

test('study patch: title-only save works, body projection matches doc, unused assets dropped', () => {
  assert.throws(() => S.buildStudyPatch({title: ' '}, sample), /TITLE_REQUIRED/);
  const p = S.buildStudyPatch({title: '제목', topics: 'AI, ai , 반도체', assets: [{id: 'a1', url: assets.a1.url, path: 'records_images/x'}, {id: 'unused', url: 'https://x'}], sourceUrl: 'javascript:1'}, sample);
  assert.equal(p.kind, 'study'); assert.equal(p.studyType, 'concept'); assert.equal(p.studyStatus, 'learning');
  assert.deepEqual(p.topics, ['AI', '반도체']);
  assert.equal(p.body, S.docToPlainText(JSON.parse(p.contentDocJson)));
  assert.deepEqual(p.assets.map(a => a.id), ['a1']);
  assert.equal(p.link, ''); assert.equal(p.asOfDate, '');
  assert.equal(p.contentFormat, 'tiptap-json');
});

test('commit: preserves unknown fields via patch-only write, detects conflicts, bounded history', () => {
  const p1 = S.buildStudyPatch({title: 'A'}, S.textToDoc('one'));
  const c1 = S.commitStudy(null, p1, null, {now: 1000, date: '2026-09-17'}).result;
  assert.equal(c1.studyRevision, 1); assert.equal(c1.createdAt, 1000); assert.equal(c1.date, '2026-09-17');
  const stored = {...c1, radarArticleId: 'keep', relations: [{targetId: 'x', type: 'supports'}], researchRevision: 4};
  const exp = S.studyFingerprint(stored);
  const p2 = S.buildStudyPatch({title: 'A2'}, S.textToDoc('two'));
  const c2 = S.commitStudy(stored, p2, exp, {now: 2000}).result;
  assert.equal(c2.radarArticleId, undefined, 'patch must not contain foreign fields');
  assert.equal(c2.createdAt, undefined, 'createdAt untouched on update');
  assert.equal(c2.studyRevision, 2);
  assert.equal(c2.studyHistory.length, 0, 'within interval no checkpoint');
  const merged = {...stored, ...c2};
  assert.throws(() => S.commitStudy(merged, p1, exp, {now: 3000}), /CONFLICT/);
  let cur = merged;
  for (let i = 0; i < 8; i++) { const p = S.buildStudyPatch({title: 'v' + i}, S.textToDoc('body ' + i)); cur = {...cur, ...S.commitStudy(cur, p, S.studyFingerprint(cur), {now: 10000 + i, reason: 'import-version'}).result}; }
  assert.equal(cur.studyHistory.length, S.HISTORY_MAX);
  assert.equal(cur.studyHistory.at(-1).title, 'v6');
  assert.deepEqual(cur.relations, stored.relations);
});

test('commit: time-based checkpoint policy and size guard', () => {
  const base = {...S.commitStudy(null, S.buildStudyPatch({title: 'A'}, S.textToDoc('x')), null, {now: 0}).result};
  const r = S.commitStudy(base, S.buildStudyPatch({title: 'A'}, S.textToDoc('y')), S.studyFingerprint(base), {now: S.HISTORY_INTERVAL_MS + 1}).result;
  assert.equal(r.studyHistory.length, 1);
  const huge = S.textToDoc('가'.repeat(320 * 1024));
  assert.throws(() => S.commitStudy(null, S.buildStudyPatch({title: 'big'}, huge), null, {now: 1}), /SIZE_LIMIT/);
  const mid = S.textToDoc('a'.repeat(310 * 1024));
  const c = S.commitStudy(null, S.buildStudyPatch({title: 'mid'}, mid), null, {now: 1});
  assert.equal(c.level, 'warn');
});

test('relations merge only applies own add/remove; bidirectional view with missing targets', () => {
  const cur = [{targetId: 'n1', type: 'references', relationId: 'r1'}, {targetId: 'other', type: 'supports', relationId: 'r2'}];
  const m = S.mergeRelations(cur, {add: [{targetId: 'n2', type: 'references'}, {targetId: 'other', type: 'supports'}], remove: [{targetId: 'n1', type: 'references'}]}, 5);
  assert.deepEqual(m.map(x => x.targetId), ['other', 'n2']);
  const recs = [
    {id: 'note', kind: 'study', relations: [{targetId: 'A', type: 'references'}, {targetId: 'gone', type: 'references'}, {targetId: 'I', type: 'supports'}]},
    {id: 'A', kind: 'news'}, {id: 'I', kind: 'idea'}, {id: 'I2', kind: 'idea', relations: [{targetId: 'note', type: 'related'}]}
  ];
  const v = S.relationView(recs, 'note');
  assert.deepEqual(v.references.map(x => x.targetId), ['A', 'gone']);
  assert.equal(v.references[1].target, null);
  assert.deepEqual(v.hypotheses.map(x => x.targetId), ['I', 'I2']);
  const back = S.relationView(recs, 'A');
  assert.equal(back.backlinks[0].targetId, 'note');
  assert.equal(back.backlinks[0].type, 'references');
});

test('MarkFlow markers: highlights, image codes, video, title', () => {
  const rep = {converted: [], missing: []};
  const url = 'https://youtu.be/abc';
  const enc = Buffer.from(url).toString('base64');
  const out = S.preprocessMarkflowMarkdown('# 제목\n⟦2중요⟧ 문장\n⟦vid ' + enc + '⟧\n⟦vidfile:abc123⟧', rep);
  assert.match(out, /<mark data-mf-hl="2">중요<\/mark>/);
  assert.match(out, /\[▶ 동영상\]\(https:\/\/youtu\.be\/abc\)/);
  assert.equal(rep.missing.length, 1);
  assert.deepEqual(S.parseMarkflowImageAlt('차트 ⟪w50 h300 r90⟫'), {alt: '차트', width: '50%', rotation: 90, height: 300});
  assert.equal(S.markflowTitle('\n\n## ⟦1핵심⟧ 정리\n본문'), '핵심 정리');
  assert.equal(S.decodeMarkflowVideo('!!!'), '');
});

test('reimport candidates never match by file name, only hash or document id', async () => {
  const h = await S.sha256Hex('same');
  const recs = [{id: '1', kind: 'study', origin: {app: 'markflow', fileHash: h, fileName: 'a.md'}}, {id: '2', kind: 'study', origin: {app: 'markflow', fileHash: 'x', fileName: 'a.md', documentId: 'd9'}}, {id: '3', kind: 'memo', origin: {app: 'markflow', fileHash: h}}];
  assert.deepEqual(S.reimportCandidates(recs, {fileHash: h}).map(c => c.record.id), ['1']);
  assert.deepEqual(S.reimportCandidates(recs, {fileHash: 'none', documentId: 'd9'}).map(c => c.record.id), ['2']);
  assert.deepEqual(S.reimportCandidates(recs, {fileHash: 'none'}), []);
});

test('legacy text record opens as paragraphs without touching body; backup round trip', () => {
  const legacy = {id: 'L', kind: 'study', body: '줄1\n\n줄3'};
  const d = S.docForRecord(legacy);
  assert.equal(S.docToPlainText(d), '줄1\n\n줄3');
  assert.equal(legacy.body, '줄1\n\n줄3');
  const rec = {id: 'n', ...S.buildStudyPatch({title: 'B'}, sample), studyRevision: 3};
  const b = S.parseBackup(JSON.stringify(S.buildBackup(rec, {a1: 'data:image/png;base64,AAA'}, 0)));
  assert.equal(b.record.contentDocJson, rec.contentDocJson);
  assert.equal(b.record.body, rec.body);
  assert.equal(b.images.a1, 'data:image/png;base64,AAA');
  assert.throws(() => S.parseBackup({format: 'x'}), /BACKUP_FORMAT/);
});

test('review queue: needs_review status or due review date', () => {
  assert.ok(S.studyNeedsReview({kind: 'study', studyStatus: 'needs_review'}, '2026-09-17'));
  assert.ok(S.studyNeedsReview({kind: 'study', reviewAt: '2026-09-10'}, '2026-09-17'));
  assert.ok(!S.studyNeedsReview({kind: 'study', reviewAt: '2026-10-10', studyStatus: 'organized'}, '2026-09-17'));
  assert.ok(!S.studyNeedsReview({kind: 'idea', studyStatus: 'needs_review'}, '2026-09-17'));
});

test('persisted doc never keeps data:/blob: image addresses', () => {
  const d = {type: 'doc', content: [
    {type: 'image', attrs: {src: 'data:image/png;base64,AAAA', status: 'uploading', tempId: 't1'}},
    {type: 'image', attrs: {src: 'blob:https://x/y', status: 'stored'}},
    {type: 'image', attrs: {src: 'https://other/a.png', status: 'external'}},
    {type: 'image', attrs: {src: 'https://firebasestorage.googleapis.com/x', status: 'stored', assetId: 'a'}}
  ]};
  const p = S.buildStudyPatch({title: 't', assets: [{id: 'a', url: 'https://firebasestorage.googleapis.com/x'}]}, d);
  assert.ok(!/data:|blob:/.test(p.contentDocJson));
  const imgs = S.imagesOf(JSON.parse(p.contentDocJson));
  assert.deepEqual(imgs.map(i => i.status), ['missing', 'missing', 'external', 'stored']);
  assert.equal(imgs[2].originalSrc, 'https://other/a.png');
  assert.equal(imgs[0].tempId, undefined);
});
