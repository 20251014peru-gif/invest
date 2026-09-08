import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {FIXED,TOPICS,topic,marketBoard,attention,axes,snapshotTrend} from '../observatory.js';
import {mergeIndicators} from '../core.js';
const now=new Date('2026-09-08T05:00:00Z');
const row=(id,extra={})=>({id,value:100,prev:100,cycle:'D',as_of:'2026-09-07',unit:'pt',...extra});
test('실제 35개 자료가 핵심과 분야별 목록에 정확히 한 번씩 보존된다',()=>{
  const read=p=>JSON.parse(fs.readFileSync(new URL(p,import.meta.url),'utf8'));
  const items=mergeIndicators(read('../../data/indicators.json'),read('../../facts/macro.json'));
  const board=marketBoard(items,read('../../facts/macro_history.json'),now);
  const ids=[...board.fixed,...board.extras].map(x=>x.row.id).concat(board.remaining.map(x=>x.id));
  assert.equal(items.length,35);assert.equal(ids.length,35);assert.equal(new Set(ids).size,35);
  assert.deepEqual(board.fixed.map(x=>x.row.id),FIXED);assert.ok(board.extras.length>=2&&board.extras.length<=4);
  for(const r of board.remaining)assert.ok(TOPICS.some(([name])=>topic(r.id)===name));
});
test('큰 변화 승격은 최대 4개이며 동점 순서가 안정적이다',()=>{
  const items=[...FIXED.map(id=>row(id)),...['x','z','y','a','b'].map(id=>row(id,{prev:80}))];
  const board=marketBoard(items,{},now);assert.equal(board.extras.length,4);assert.equal(board.remaining.length,1);
  assert.deepEqual(board.extras.map(x=>x.row.id),['a','b','x','y']);
});
test('오류·누락·대기·오래된·미래 관측 자료는 승격하지 않는다',()=>{
  for(const extra of [{error:'fail'},{missing:true},{pending:true},{value:null},{as_of:'2025-01-01'},{as_of:'2026-09-09'}])assert.equal(attention(row('x',{prev:20,...extra}),{},now).score,0);
});
test('비일간은 수집 날짜만 새로워져서는 승격하지 않고 실제 값 변경이 있어야 한다',()=>{
  const r=row('cpi_yoy',{cycle:'M',as_of:'2026-08',value:3,prev:2,unit:'%'});
  assert.equal(attention(r,{},now).score,0);
  assert.equal(attention(r,{days:{'2026-09-06':{cpi_yoy:3},'2026-09-07':{cpi_yoy:3}}},now).score,0);
  assert.ok(attention(r,{days:{'2026-09-06':{cpi_yoy:2},'2026-09-07':{cpi_yoy:3}}},now).score>0);
  assert.equal(attention(r,{days:{'2026-01-06':{cpi_yoy:2},'2026-09-07':{cpi_yoy:3}}},now).score,0);
});
test('승격 없는 날은 신용·금리로 보완하고 가짜 지표를 만들지 않는다',()=>{
  const items=[...FIXED,'credit_spread','kr10y','us2y'].map(id=>row(id));
  const b=marketBoard(items,{},now);assert.equal(b.extras.length,3);assert.ok(b.extras.every(x=>x.reason==='시장 보완'));
  assert.equal(marketBoard([],{},now).fixed.length,0);
});
test('금리 변화는 %가 아닌 %p 기준이고 기준값 0도 처리한다',()=>{
  assert.equal(attention(row('us2y',{unit:'%',value:0.05,prev:0}),{},now).score,0);
  assert.ok(attention(row('us2y',{unit:'%',value:0.2,prev:0}),{},now).score>0);
});
test('요약 5축은 자료 부족과 엇갈린 설정 판정을 구분한다',()=>{
  assert.equal(axes([],now).length,5);assert.ok(axes([],now).every(x=>x.label==='확인 필요'));
  const result=axes([row('kospi',{judge:'강'}),row('sp500',{judge:'약'})],now);
  assert.equal(result.at(-1).label,'혼재');
});
test('5일 흐름에 오래된 스냅샷과 미래 날짜를 포함하지 않는다',()=>{
  const history={days:{'2026-08-01':{x:1},'2026-08-02':{x:2},'2026-09-09':{x:10}}};
  assert.equal(snapshotTrend(history,'x',now),'5일 내 수집 이력 부족');
  history.days['2026-09-07']={x:4};history.days['2026-09-08']={x:3};
  assert.equal(snapshotTrend(history,'x',now),'5일 내 수집 흐름 ↓');
});
