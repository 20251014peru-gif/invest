const fs=require('fs'),assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{const b=await chromium.launch({headless:true,channel:'msedge'});try{const p=await b.newPage();await p.route('**/*',r=>r.abort());const js=fs.readFileSync('js/records-reading.js','utf8'),css=fs.readFileSync('js/records-reading.css','utf8');
for(const text of ['긴 단일 문단도 가까운 두 칸씩 읽습니다. '.repeat(220),'## 첫 제목\n'+ '첫 구간 원문입니다. '.repeat(90)+'\n## 둘째 제목\n'+ '둘째 구간 원문입니다. '.repeat(90),'01\n첫 목차\n목차 설명\n02\n둘째 목차\n목차 설명\n핵심 1줄 | 요약\n전체 흐름 | '+ '전체 흐름 원문을 보존합니다. '.repeat(160)]){
await p.setContent('<style>'+css+'</style><div id="pageModal"><div id="host"></div></div>');await p.addScriptTag({content:js});await p.evaluate(t=>{host.innerHTML='<div data-readview="full">'+RecordReading.formattedHTML(t)+'</div>';RecordReading.documentColumns(host);RecordReading.documentColumns(host);},text);
for(const width of [1440,1024,390]){await p.setViewportSize({width,height:1000});assert.equal(await p.locator('.pg-topic-document').textContent(),text);
assert.equal(await p.locator('.pg-topic-pairs').first().evaluate(e=>getComputedStyle(e).gridTemplateColumns.split(' ').length),width>900?2:1);
const rows=await p.locator('.pg-topic-pairs').evaluateAll(groups=>groups.map(g=>Array.from(g.querySelectorAll(':scope > .pg-topic-cell')).map(e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,height:r.height,text:e.textContent.length};})));
for(const cells of rows){for(let i=0;i<cells.length;i++){assert(cells[i].text<=481);if(width>900&&i%2===1){assert(Math.abs(cells[i].y-cells[i-1].y)<1);assert(cells[i].x>cells[i-1].x);}if(i>=2)assert(cells[i].y>=cells[i-2].y+cells[i-2].height-1);}}
assert(await p.locator('.pg-topic-document').evaluate(e=>e.scrollWidth<=e.clientWidth+1));}
if(text.startsWith('##')){const topics=await p.locator('.pg-topic-section').allTextContents();assert.equal(topics.length,2);assert(!topics[0].includes('둘째'));assert(!topics[1].includes('첫 구간'));}
}
await p.setViewportSize({width:1440,height:1000});await p.screenshot({path:'test-results/records-topic-pairs.png',fullPage:true});console.log('PASS: exact original, related heading groups, bounded chunks, row-major pairs, mobile order, no overflow, idempotence');}finally{await b.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
