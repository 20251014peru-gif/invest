const {test}=require('node:test');
const assert=require('node:assert/strict');
const R=require('../js/records-reading.js');

test('YouTube columns use explicit headings and preserve source records',()=>{
  const r={id:'x',title:'<img src=x onerror=alert(1)>',oneLiner:'짧은 결론',body:'01\n⚡ 30초 판단\n상세한 핵심 설명\n02\n직전 영상 대비\n기존 의견 유지\n03\n신호 요약 — 배경\n추가 맥락\n04\n선행 지표 현황\n지표 수치 없음',star:5};
  const before=JSON.stringify(r),c=R.youtubeColumns(r);
  assert.deepEqual(c.core.map(x=>x.text),['상세한 핵심 설명','추가 맥락']);
  assert.equal(c.evidence[0].text,'지표 수치 없음');assert.equal(c.change[0].text,'기존 의견 유지');
  const html=R.youtubeTableHTML([r]);assert.ok(html.includes('&lt;img'));assert.ok(!html.includes('<img'));
  assert.equal(JSON.stringify(r),before);
});
test('YouTube unstructured text does not invent evidence or change',()=>{
  const c=R.youtubeColumns({oneLiner:'관망',body:'어제보다 올랐다는 이야기'});
  assert.equal(c.core[0].text,'관망');assert.deepEqual(c.evidence,[]);assert.deepEqual(c.change,[]);
  assert.match(R.youtubeTableHTML([{id:'a',body:'첫 문단\n\n뒤 문단'}]),/본문 발췌/);
});
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
