import test from 'node:test';
import assert from 'node:assert/strict';
import {newsNote} from '../notebook.js';
test('뉴스가 수집 목록에서 사라져도 제목과 출처를 보존한다',()=>{
 const article={id:'news-1',title:'검사 기사',url:'https://example.com/article',source:'검사 매체',date:'2026-09-08'};
 const n=newsNote(article,{title:' 내 판단 ',text:'첫째\n\n둘째'});
 assert.equal(n.kind,'news-note');assert.equal(n.targetId,'news-1');assert.equal(n.text,'첫째\n\n둘째');assert.equal(n.snapshot.title,'검사 기사');
 const revised=newsNote({...article,title:'바뀐 제목'},{title:'수정',text:'새 판단'},{...n,id:'saved-id'});
 assert.equal(revised.id,'saved-id');assert.equal(revised.snapshot.title,'검사 기사');
});
test('출처에 실행 주소를 저장하지 않는다',()=>{
 const n=newsNote({id:'n',title:'제목',url:'javascript:alert(1)'},{title:'',text:'내용'});
 assert.equal(n.url,'');assert.equal(n.snapshot.url,'');
});
