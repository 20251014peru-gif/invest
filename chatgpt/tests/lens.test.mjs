import test from 'node:test';import assert from 'node:assert/strict';
import {priority,sector,usable,macroReading} from '../lens.js';
const now=new Date('2026-09-08T00:00:00Z');const row=(id,value,prev)=>({id,value,prev,cycle:'M',as_of:'2026-08'});
test('확인 우선순위는 목적별이고 ETF는 상황별이다',()=>{assert.equal(priority('sox').rank,1);assert.equal(priority('bdry').rank,3);assert.equal(priority('kr_aa3').rank,2);});
test('제목으로 복수 분야를 분류하고 모르면 대기한다',()=>{assert.match(sector({title:'반도체 실적 발표',keyword:''}),/반도체·AI.*기업·공시/);assert.equal(sector({title:'오늘의 이야기',keyword:''}),'기타·분류 대기');});
test('오류·결측·너무 오래된 자료는 해석에서 제외한다',()=>{assert.equal(usable({...row('a',1,0),error:'fail'},now),false);assert.equal(usable({...row('a',1,0),as_of:'2024-01'},now),false);assert.equal(usable(row('a',0,1),now),true);});
test('핵심 자료가 부족하면 국면을 만들어내지 않는다',()=>{assert.equal(macroReading([row('ism_pmi',54,53)],now).enough,false);assert.match(macroReading([],now).title,/확인이 더 필요/);});
test('제조업 확장과 물가 혼합을 구분한다',()=>{const rows=[row('ism_pmi',54,53),row('payems_chg',162,21),row('cpi_yoy',3.54,3.73),row('core_pce_yoy',3.34,3.34),row('kr_cpi_yoy',3.09,2.79)];assert.match(macroReading(rows,now).title,/고르지 않습니다/);assert.equal(macroReading(rows,now).rows[0].evidence[2].valid,false);});
