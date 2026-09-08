import test from 'node:test';import assert from 'node:assert/strict';
import {assessNews,prioritizeNews,priorityHTML,deepFocus} from '../news-priority.js';import {newsSummaryQuestion} from '../news-summary.js';import {normalizeRequest} from '../backend/protocol.js';
const now=Date.parse('2026-09-08T12:00:00Z');
const make=(title,body='',extra={})=>({id:'news-a',title,body:body+'\n'+('기사의 관련 배경 설명입니다. '.repeat(20)),time:now-3600000,source:'예시',...extra});
test('같은 변화 문장에 수치와 실행 근거가 있는 최신 기사만 먼저 분석한다',()=>{
 const n=make('A사 공급계약 체결','A사는 100억원 규모 공급계약을 체결했다고 공시했다.');const a=assessNews(n,now);assert.equal(a.tier,'먼저 분석');assert.ok(a.areas.includes('이익 전망'));assert.match(a.quote,/100억원/);
 assert.equal(assessNews({...n,time:now-100*3600000},now).tier,'후속 확인');assert.equal(assessNews({...n,time:0},now).tier,'후속 확인');
 assert.equal(assessNews({...n,body:''},now).tier,'후속 확인');
});
test('유명인 이름이나 주가 급등만으로 승격하지 않고 계획·부정문을 보수적으로 처리한다',()=>{
 assert.equal(assessNews(make('젠슨 황의 자신감'),now).tier,'간단히 보기');
 assert.equal(assessNews(make('A사 주가 급등','A사는 100억원 공급계약을 체결했다고 공시했다.'),now).tier,'후속 확인');
 assert.equal(assessNews(make('공장 증설 검토','100억원을 투자해 공장을 증설할 계획이라고 발표했다.'),now).tier,'후속 확인');
 assert.notEqual(assessNews(make('공급계약 소식','100억원 공급계약은 확정되지 않았다고 공시했다.'),now).tier,'먼저 분석');
});
test('실적 전망치의 실제 하향 조정과 정책 시행을 포착한다',()=>{
 assert.equal(assessNews(make('영업이익 전망 하향','영업이익 전망은 15% 하향 조정됐다고 발표했다.'),now).tier,'먼저 분석');
 assert.equal(assessNews(make('관세 인상 시행','10% 관세 인상을 확정하고 시행했다.'),now).tier,'먼저 분석');
});
test('같은 제목만 묶고 원문을 보존하며 필터·빈 결과와 HTML을 안전하게 표시한다',()=>{
 const a=make('A사 계약 체결','100억원 공급계약 체결을 공시했다.');const b={...a,id:'news-b',title:'[속보] A사 계약 체결'};const c=make('<script>별도 기사</script>','',{id:'news-c'});
 const rows=prioritizeNews([a,b,c],now);assert.equal(rows.length,2);assert.equal(rows[0].duplicates.length,1);assert.equal(a.title,'A사 계약 체결');
 assert.doesNotMatch(priorityHTML([c],{now,tier:'간단히 보기'}),/<script>/);assert.match(priorityHTML([a],{now,area:'정책·자금'}),/후보가 없습니다/);
});
test('심층 요청은 기존 기사 분석 서버 한도와 해설형을 유지한다',()=>{
 const n=make('설비 투자 확대');const focus=deepFocus(n);assert.ok(focus.length<=500);const q=newsSummaryQuestion(focus);assert.ok(q.length<=2000);assert.match(q,/매출 대비 비중/);assert.match(q,/미확인/);
 assert.doesNotThrow(()=>normalizeRequest({kind:'news',question:q,evidence:[{id:'N:news-a',text:n.body}]}));
});
