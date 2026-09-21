const {test}=require('node:test');
const assert=require('node:assert/strict');
const S=require('../js/records-stocks.js');
test('thesis-only stock is visible without modifying or duplicating original data',()=>{
  const item={name:'A',thesisLog:[{date:'2026-09-21',text:'earlier'},{date:'2026-09-21',text:'later'},{date:'2026-09-20',text:'old'}]};
  const original=JSON.stringify(item), recs=[];
  const s=S.summary('A',item,recs);
  assert.equal(s.hasContent,true);assert.equal(s.total,3);assert.equal(s.linked,0);
  assert.deepEqual(s.entries.map(x=>x.body),['later','earlier','old']);
  assert.deepEqual(S.summary('A',item,recs),s);assert.equal(JSON.stringify(item),original);assert.deepEqual(recs,[]);
});
test('mixed records and logs sort by date then precise timestamp; unrelated stays out',()=>{
  const entries=S.entries('A',{thesisLog:[{date:'2026-09-20',text:'log',at:100}]},[
    {id:'r1',stocks:['A'],date:'2026-09-21',createdAt:1},
    {id:'r2',stocks:['A','B'],date:'2026-09-20',createdAt:200},
    {id:'unrelated',stocks:['B'],date:'2026-09-22'}]);
  assert.deepEqual(entries.map(x=>x.id),['r1','r2','stock-log:A:0']);
});
test('directory defaults to substantive content, searches history and puts empty stocks last',()=>{
  const items={a:{name:'a',quantity:0},b:{name:'b',thesisLog:[{date:'2026-09-21',text:'searchable'}]},z:'z'};
  const dir=(q,only)=>S.directory(['z','a','b'],n=>items[n],[],q,only);
  assert.deepEqual(dir('',true).map(s=>s.name),['b','a']);
  assert.deepEqual(dir('',false).map(s=>s.name),['b','a','z']);
  assert.deepEqual(dir('searchable',true).map(s=>s.name),['b']);
  assert.equal(S.summary('a',items.a,[]).total,0);assert.equal(S.fields(items.a)[0].value,'0');
});
test('blank history and custom labels do not count as content; raw markup remains data',()=>{
  assert.equal(S.summary('A',{thesisLog:[{text:'  '}],customFields:[{label:'메모',value:''}]},[]).hasContent,false);
  assert.equal(S.entries('A',{thesisLog:[{text:'<script>x</script>'}]},[])[0].body,'<script>x</script>');
});
test('KST dates correct before 09:00 and across midnight irrespective of local timezone',()=>{
  assert.equal(S.kstDate(Date.parse('2026-09-20T15:01:00Z')),'2026-09-21');
  assert.equal(S.kstDate(Date.parse('2026-09-20T14:59:00Z')),'2026-09-20');
});
test('field merge preserves other devices appends and refuses same-field overwrite',()=>{
  const original={targetPrice:'100',quantity:'1'};
  const base={targetPrice:'100',quantity:'2',thesisLog:[{text:'other device'}]};
  S.mergeFields(base,original,{targetPrice:'110'});
  assert.equal(base.quantity,'2');assert.equal(base.thesisLog.length,1);assert.equal(base.targetPrice,'110');
  assert.throws(()=>S.mergeFields(base,original,{quantity:'3'}),/다른 기기/);
});
