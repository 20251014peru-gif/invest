import test from 'node:test';import assert from 'node:assert/strict';
import {newsSummaryQuestion,NEWS_SUMMARY_FOCUS} from '../news-summary.js';
import {normalizeRequest} from '../backend/protocol.js';
test('숫자 중심 요약 지침은 현재 서버 요청 제한 안에서 사용자 초점을 유지한다',()=>{
 const question=newsSummaryQuestion('매출과 영업이익 비교');assert.match(question,/매출과 영업이익 비교/);
 const r=normalizeRequest({kind:'news',question,evidence:[{id:'N:sample',title:'실적',text:'매출 100억원, 영업이익 10억원'}]});assert.equal(r.question,question);
 assert.ok(newsSummaryQuestion('가'.repeat(2000)).length<=2000);assert.match(NEWS_SUMMARY_FOCUS,/핵심 사실·숫자/);
});
test('새 기본 요청은 기존 캐시 키와 달라지고 숫자·원문 부족을 명시한다',()=>{
 const q=newsSummaryQuestion();assert.notEqual(q,'이 기사의 핵심 주장, 경제적 의미, 확인할 근거와 불확실성을 구분해 요약해줘.');
 assert.match(q,/%와 %p/);assert.match(q,/기본금리와 조건부 최고금리/);assert.match(q,/원문 전체인지 확인되지/);
});
