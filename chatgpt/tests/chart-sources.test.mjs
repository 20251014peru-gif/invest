import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {mergeIndicators} from '../core.js';
import {chartSource,chartTitle,chartPanel} from '../chart-sources.js';
const read=p=>JSON.parse(fs.readFileSync(new URL(p,import.meta.url),'utf8'));
const items=mergeIndicators(read('../../data/indicators.json'),read('../../facts/macro.json'));
test('모든 35개 지표에 명시적인 차트 경로 또는 정확한 제한 안내가 있다',()=>{
  assert.equal(items.length,35);for(const r of items){const c=chartSource(r.id);assert.ok(c,r.id);assert.equal(new URL(c.url).protocol,'https:');assert.ok(c.note);}
  assert.equal(items.filter(r=>chartSource(r.id).kind==='chart').length,33);
  assert.equal(chartSource('unknown'),null);
});
test('미국 물가·임금은 전년비, 고용은 증감으로 연결한다',()=>{
  for(const id of ['cpi_yoy','core_pce_yoy','ahe_yoy'])assert.equal(chartSource(id).units,'pc1');
  assert.equal(chartSource('payems_chg').units,'chg');
  for(const [id,g] of Object.entries({cpi_yoy:'1Yh9Z',core_pce_yoy:'1Yha5',payems_chg:'1Yhab',ahe_yoy:'1Yhaw'}))assert.equal(new URL(chartSource(id).url).searchParams.get('g'),g);
  assert.ok(chartSource('spread_10_2').url.endsWith('/series/T10Y2Y'));
});
test('달러지수·선물·ETF를 다른 원지표로 바꾸지 않는다',()=>{
  assert.ok(decodeURIComponent(chartSource('dxy').url).includes('DX-Y.NYB'));
  for(const [id,symbol]of [['wti','CL=F'],['gold','GC=F'],['copper','HG=F'],['bdry','BDRY'],['nasdaq','^IXIC']])assert.ok(decodeURIComponent(chartSource(id).url).includes(symbol));
});
test('ECOS 홈 대신 개별 그래프를 열고 예외를 숨기지 않는다',()=>{
  assert.ok(chartSource('kr_lead').url.endsWith('/K254'));
  assert.equal(chartSource('credit_spread').kind,'components');assert.equal(chartSource('credit_spread').extra.length,1);
  assert.equal(chartSource('kr_bbb3').kind,'selection');
  assert.match(chartPanel({id:'kr_bbb3'}),/010320000/);
});
test('카드 제목은 항상 내부 상세로 이동하고 외부 차트는 전용 링크로 분리한다',()=>{
  for(const r of items){assert.match(chartTitle(r),/#\/indicators\//);assert.doesNotMatch(chartTitle(r),/data-external|target=/);}
  assert.match(chartPanel({id:'usdkrw'}),/data-external/);
  assert.match(chartTitle({id:'kr_bbb3',name:'BBB'}),/#\/indicators\/kr_bbb3/);
  assert.ok(!chartTitle({id:'usdkrw',name:'<script>'}).includes('<script>'));
});
