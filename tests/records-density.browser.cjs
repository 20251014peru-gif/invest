// Run tests/study-browser/server.cjs 8923 first. No production requests.
const {chromium}=require('playwright'),assert=require('node:assert/strict');
(async()=>{const b=await chromium.launch({headless:true,channel:'msedge'});try{
const p=await b.newPage({viewport:{width:1440,height:1000}}),errors=[];p.on('pageerror',e=>errors.push(e.message));
await p.route('**/*',r=>r.request().url().startsWith('http://localhost:8923')?r.continue():r.abort());
await p.goto('http://localhost:8923/records.html');await p.waitForFunction(()=>window.recordsLoaded&&window.FU?.ready);
const body='01\n30초 판단\n기존 판단을 유지하며 다음 발표를 기다립니다.\n02\n직전 영상 대비\n직전 의견은 유지하되 관찰 대상이 달라졌습니다.\n03\n신호 요약\n구체적인 설명을 원문대로 표시합니다.\n04\n선행 지표 현황\n제시된 수치 없음\n핵심 1줄 | 본문 시작\n■ 직전 영상 대비 ▸\n변화를 원문과 비교합니다.\n■ 선행 지표 현황 ▸\n미확인 값을 채우지 않습니다.\n■ 달님 시사점 ▸\n'+Array.from({length:8},(_,i)=>'문단 '+i+' · 이후 확인할 내용을 보존합니다.').join('\n\n');
const fixture={records:{yt:{kind:'youtube',title:'긴 제목과 핵심내용을 비교하는 시험용 영상',date:'2026-09-27',channel:'시험 채널',body,star:5}},records_meta:{stocks:{list:[]},checklist_templates:{list:[]}}};
await p.evaluate(x=>__mockReset(x),fixture);await p.waitForFunction(()=>records.length===1);const before=await p.evaluate(()=>JSON.stringify(__mockDump().records));
await p.evaluate(()=>{curKind='youtube';curView='table';render();});
const compact=(await p.locator('.yt-list tbody tr').boundingBox()).height;
const baseline=await p.addStyleTag({content:'.yt-list td{padding:22px 16px;line-height:1.65}.yt-section+.yt-section{margin-top:14px}.yt-section-label{display:block;margin:0 0 4px}.yt-section p{display:block}'});
const previous=(await p.locator('.yt-list tbody tr').boundingBox()).height;await baseline.evaluate(e=>e.remove());
assert(compact<previous*.85,JSON.stringify({compact,previous}));
await p.locator('.yt-title').click();
assert.equal(await p.locator('.pg-outline').evaluate(e=>getComputedStyle(e).gridTemplateColumns.split(' ').length),2);
assert.equal(await p.locator('.pg-implications>.pg-readable').first().evaluate(e=>getComputedStyle(e).columnCount),'2');
await p.locator('[data-readtab="full"]').click();assert.equal(await p.locator('[data-readview="full"]').textContent(),body);
for(const width of [1440,1024,390]){await p.setViewportSize({width,height:1000});const n=width>900?2:1;
assert.equal(await p.locator('.pg-topic-pairs').first().evaluate(e=>getComputedStyle(e).gridTemplateColumns.split(' ').length),n);
assert.equal(await p.locator('.pg-implications>.pg-readable').first().evaluate(e=>getComputedStyle(e).columnCount),String(n));
assert(await p.locator('#pageModal .modal').evaluate(e=>e.scrollWidth<=e.clientWidth+1));}
assert.equal(await p.locator('[data-readview="full"]').textContent(),body);
assert.equal(await p.evaluate(()=>JSON.stringify(__mockDump().records)),before);assert.deepEqual(errors,[]);
console.log(JSON.stringify({pass:true,compactHeight:compact,previousHeight:previous,reduction:Math.round((1-compact/previous)*100)+'%',checks:['both reading tabs 2 columns','1024 desktop 2 columns','390 mobile 1 column','original text preserved','records unchanged','no overflow/errors']}));
}finally{await b.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
