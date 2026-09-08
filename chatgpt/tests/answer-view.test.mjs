import test from 'node:test';import assert from 'node:assert/strict';import {formatAnswer} from '../answer-view.js';
const evidence=[{id:'N:news-one',title:'기사 하나',url:'https://example.com/one'},{id:'I:rate',title:'금리',url:'javascript:alert(1)'}];
test('같은 문단의 반복 코드를 하나로 묶고 복사·노트용 텍스트에도 번호와 출처를 보존한다',()=>{
 const x=formatAnswer('발표했다[N:news-one]. 이어진다 [N:news-one].\n\n다음 확인[N:news-one].',evidence,['N:news-one']);
 assert.equal((x.html.match(/data-cite="1"/g)||[]).length,2);assert.doesNotMatch(x.html,/N:news/);assert.doesNotMatch(x.plain,/N:news/);assert.match(x.plain,/출처\n\[1\] 기사 하나/);assert.match(x.sourceHTML,/id="ai-source-1"/);
});
test('여러 근거는 첫 인용 순서로 번호를 붙이고 알 수 없는 근거는 확인 필요로 표시한다',()=>{
 const x=formatAnswer('금리[I:rate], 기사[N:news-one], 없음[N:missing].',evidence,['N:news-one']);assert.match(x.sourceHTML,/\[1\] 금리/);assert.match(x.sourceHTML,/\[2\]/);assert.match(x.html,/출처 확인 필요/);assert.doesNotMatch(x.html,/N:missing/);
});
test('답변과 출처 HTML을 이스케이프하고 실행 URL을 링크로 만들지 않는다',()=>{
 const x=formatAnswer('<img src=x onerror=alert(1)>[I:rate]',evidence);assert.doesNotMatch(x.html,/<img/);assert.doesNotMatch(x.sourceHTML,/javascript:/);assert.match(x.html,/&lt;img/);
});
