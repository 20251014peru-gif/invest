const {test}=require('node:test');
const assert=require('node:assert/strict');
const R=require('../js/records-reading.js');
test('unknown structure stays as escaped, complete original',()=>{
  const text='메모\n<script>alert(1)</script>\n3\n순서 없는 번호';
  assert.deepEqual(R.outline(text),[]);
  assert.ok(R.bodyHTML(text).includes('&lt;script&gt;'));
  assert.ok(!R.bodyHTML(text).includes('<script>'));
});
test('outline maps matching full sections without rewriting original',()=>{
  const text='이 요약 한눈에\n01\n직전 영상 대비\n요약 A\n▸\n02\n신호 요약 — 배경\n요약 B\n핵심 1줄 | 핵심\n직전 영상 대비 ▸\n상세 A\n신호 요약 ▸\n상세 B';
  const items=R.outline(text);
  assert.equal(items.length,2);assert.equal(items[0].detail,'상세 A');assert.equal(items[1].detail,'상세 B');
  assert.equal(items[1].text,'요약 B');
  assert.ok(R.bodyHTML(text).includes('pg-source-overview'));
  assert.equal(R.formattedHTML(text).replace(/<[^>]+>/g,''),text);
});
test('no sequential headings means no speculative split',()=>{
  assert.deepEqual(R.outline('01\nA\n03\nC'),[]);
  assert.deepEqual(R.outline('01\nA\n01\nB'),[]);
});
test('only content panel is initially visible',()=>{
  const html=R.tabsHTML('본문','관계','할 일');
  assert.match(html,/data-readpanel="0">본문/);
  assert.match(html,/data-readpanel="1" hidden>관계/);
  assert.match(html,/data-readpanel="2" hidden>할 일/);
});
