import {test} from 'node:test';
import assert from 'node:assert/strict';
import * as C from '../js/followups-core.mjs';
test('future study review dates appear in the canonical schedule before becoming overdue',async()=>{
  const source=[{id:'study',kind:'study',title:'미래 재검토',reviewAt:'2099-12-31',stocks:['A']}];
  const before=JSON.stringify(source),items=await C.legacyItems(source,[],()=>false);
  assert.equal(items.length,1);assert.equal(items[0].dueAt,'2099-12-31');assert.equal(JSON.stringify(source),before);
  assert.equal(C.filterItems(items,{q:'A'}).length,1);
});
test('full-period legacy completion survives >14 days and duplicate questions retain separate IDs',async()=>{
  const records=[{id:'r',title:'원본',checks:[{what:'확인',date:'2020-01-01'},{what:'확인',date:'2020-01-01'}]}];
  const rows=await C.legacyItems(records,[{id:'old',dueKey:'r#0',done:true,date:'2020-01-01',createdAt:1}]);
  assert.equal(rows[0].state,'done');assert.equal(rows[0].result,'');assert.ok(rows[0].legacyCompleted);assert.equal(rows[1].state,'open');assert.notEqual(rows[0].id,rows[1].id);
  assert.deepEqual(await C.legacyItems(records,[{id:'old',dueKey:'r#0',done:true,date:'2020-01-01',createdAt:1}]),rows);
});
test('stable IDs survive reordering questions',async()=>{
  const checks=[{what:'a'},{what:'b'}];const a=await C.legacyItems([{id:'r',checks}],[]);const b=await C.legacyItems([{id:'r',checks:checks.slice().reverse()}],[]);assert.equal(a[0].id,b[1].id);
});
test('completion requires result; reopening preserves result and captures state transition',()=>{
  assert.throws(()=>C.saveTransition(null,{question:'질문',state:'done'},{expected:0,id:'a',operationId:'o'}),/RESULT_REQUIRED/);
  const first=C.saveTransition(null,{question:'질문',state:'done',result:'미집행 확인'},{expected:0,id:'a',operationId:'o',now:1});
  const second=C.saveTransition(first.item,{state:'working'},{expected:1,id:'a',operationId:'p',now:2});
  assert.equal(second.item.result,'미집행 확인');assert.equal(second.item.completedAt,null);assert.equal(second.review.event,'reopened');assert.equal(first.item.state,'done');
});
test('idempotent retry returns once, conflicting device cannot overwrite',()=>{
  const {item}=C.saveTransition(null,{question:'질문'},{expected:0,id:'a',operationId:'o'});
  assert.ok(C.saveTransition(item,{question:'변경'},{expected:0,id:'a',operationId:'o'}).repeated);
  assert.throws(()=>C.saveTransition(item,{result:'덮어쓰기'},{expected:0,id:'a',operationId:'p'}),/CONFLICT/);
});
test('completion of old record retains unknown legacy fields',()=>{
  const old={id:'a',revision:1,state:'done',legacyCompleted:true,legacy:{markers:[{done:true}]}},r=C.saveTransition(old,{question:'질문'},{expected:1,id:'a',operationId:'o'});
  assert.equal(r.item.state,'done');assert.deepEqual(r.item.legacy,old.legacy);
});
test('overdue status is separate from completion, no date is last unresolved group',()=>{
  const a={id:'a',state:'done',dueAt:'2020-01-01'},b={id:'b',state:'open',dueAt:'2020-01-01'},c={id:'c',state:'open',dueAt:''};
  assert.equal(C.group(a,'2026-09-17'),'완료');assert.equal(C.group(b,'2026-09-17'),'기한 지남');assert.deepEqual(C.filterItems([a,c,b]).map(x=>x.id),['b','c']);
});
test('bad sources and oversized body blocked, HTML escaped for views',()=>{
  assert.throws(()=>C.saveTransition(null,{question:'q',links:[{url:'javascript:alert(1)'}]},{expected:0,id:'a',operationId:'o'}),/BAD_URL/);
  assert.equal(C.safeURL('data:text/html,test'),'');assert.ok(C.esc('<script>').includes('&lt;'));
});
test('backup format and duplicate IDs validated',()=>{
  assert.throws(()=>C.parseBackup({format:'records-backup/1'}),/BACKUP_FORMAT/);
  assert.throws(()=>C.parseBackup({format:C.FORMAT,items:[{id:'a'},{id:'a'}],reviews:[]}),/DUPLICATE_ID/);
});
