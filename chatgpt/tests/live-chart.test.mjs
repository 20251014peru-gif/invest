import test from 'node:test';
import assert from 'node:assert/strict';
import {liveSource,livePanel} from '../live-chart.js';
test('국내 지수 네이버 선호와 선물·종합지수 원종목을 유지한다',()=>{
  assert.deepEqual(liveSource('kospi'),{type:'external',symbol:'KOSPI'});
  assert.deepEqual(liveSource('kosdaq'),{type:'external',symbol:'KOSDAQ'});
  assert.equal(liveSource('usdkrw').symbol,'FX_IDC:USDKRW');
  assert.equal(liveSource('nasdaq').symbol,'NASDAQ:IXIC');
  assert.equal(liveSource('wti').symbol,'NYMEX:CL1!');
  assert.equal(liveSource('bdry').symbol,'AMEX:BDRY');
});
test('FRED 파생지표는 검증된 단위를 보존하는 공유 차트를 삽입한다',()=>{
  assert.deepEqual(liveSource('cpi_yoy'),{type:'fred',query:'g=1Yh9Z'});
  assert.equal(liveSource('payems_chg').query,'g=1Yhab');
  assert.equal(liveSource('us10y').query,'id=DGS10');
  assert.match(livePanel({id:'cpi_yoy'}),/실시간 거래 시세가 아닙니다/);
});
test('미지원 차트를 가짜 실시간이나 수집 스냅샷으로 대체하지 않는다',()=>{
  for(const id of ['kr_bbb3','credit_spread','unknown']){assert.equal(liveSource(id),null);assert.match(livePanel({id}),/아직 지원하지 않습니다/);}
  assert.doesNotMatch(livePanel({id:'usdkrw'}),/수집 이력 그래프/);
});

test('국내 지수는 삽입 제한을 알리고 이미지 대신 네이버 전용 차트로 연결한다',()=>{for(const id of ['kospi','kosdaq']){const h=livePanel({id});assert.match(h,/fchart\/domestic\/index\//);assert.doesNotMatch(h,/<img|<iframe|data-live-chart=/);assert.match(h,/data-external/);}});
