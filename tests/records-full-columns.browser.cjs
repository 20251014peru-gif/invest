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
const top='■ 30초 판단 ▸\n항목 | 내용\n핵심 1줄 | 핵심 설명을 그대로 보존합니다.\n전체 흐름 | 전체 흐름 설명을 그대로 보존합니다.\n볼 가치 | 별점과 이유\n액션 | 관망\n핵심 목차\n전체 펼치기\n01\n30초 판단\n판단 설명\n02\n직전 영상 대비\n변화 설명\n핵심 1줄 | 상세 시작\n■ 근거 ▸\n'+'상세 근거를 문장 단위로 보존합니다. '.repeat(100);
await p.setContent('<style>:root{--line:#e8e2d4;--text:#34362f}#pageModal{background:white!important;font-family:Arial}</style><style>'+css+'</style><div id="pageModal"><div id="host"></div></div>');await p.addScriptTag({content:js});await p.evaluate(t=>{host.innerHTML='<div data-readview="full">'+RecordReading.formattedHTML(t)+'</div>';RecordReading.documentColumns(host);},top);
for(const width of [1440,1024,390]){await p.setViewportSize({width,height:1000});assert.equal(await p.locator('.pg-topic-document').textContent(),top);
const cards=await p.locator('.pg-summary-pairs').first().locator(':scope > .pg-labelled').evaluateAll(es=>es.map(e=>({x:e.getBoundingClientRect().x,y:e.getBoundingClientRect().y,text:e.textContent})));
assert.equal(cards.length,4);assert(!cards[3].text.includes('목차'));
const toc=await p.locator('.pg-source-section').evaluateAll(es=>es.map(e=>({x:e.getBoundingClientRect().x,y:e.getBoundingClientRect().y})));
if(width>900){assert.equal(cards[0].y,cards[1].y);assert.equal(cards[2].y,cards[3].y);assert(cards[1].x>cards[0].x);assert.equal(toc[0].y,toc[1].y);assert(toc[1].x>toc[0].x);}else{assert(cards[1].y>cards[0].y);assert(toc[1].y>toc[0].y);}}
const nested='■ 30초 판단 ▸\n핵심 1줄 | 핵심\n전체 흐름 | 흐름\n볼 가치 | 중요\n액션 | 관망\n'+Array.from({length:9},(_,i)=>String(i+1).padStart(2,'0')+'\n'+(i===8?'달님 시사점':'목차 '+(i+1))+'\n'+(i===8?'긴 시사점 원문을 그대로 보존합니다. '.repeat(120):'짧은 설명')).join('\n')+'\n■ 추가 근거 ▸\n'+'후속 근거를 빠뜨리지 않습니다. '.repeat(100);
await p.evaluate(t=>{host.innerHTML='<div data-readview="full">'+RecordReading.formattedHTML(t)+'</div>';RecordReading.documentColumns(host);RecordReading.documentColumns(host);},nested);
for(const width of [1440,1024,390]){await p.setViewportSize({width,height:1000});assert.equal(await p.locator('[data-readview="full"]').textContent(),nested);
const positions=await p.locator('.pg-summary-pairs').first().locator(':scope > .pg-labelled').evaluateAll(es=>es.map(e=>({x:e.getBoundingClientRect().x,y:e.getBoundingClientRect().y})));
const toc=await p.locator('.pg-source-section').evaluateAll(es=>es.map(e=>({x:e.getBoundingClientRect().x,y:e.getBoundingClientRect().y})));
const detail=await p.locator('.pg-source-detail .pg-topic-pairs').first().locator(':scope > .pg-topic-cell').evaluateAll(es=>es.map(e=>({x:e.getBoundingClientRect().x,y:e.getBoundingClientRect().y,h:e.getBoundingClientRect().height})));
assert(detail.length>2);assert.equal(await p.locator('.pg-source-detail .pg-topic-section').count(),2);
if(width>900){assert.equal(positions[0].y,positions[1].y);assert(positions[1].x>positions[0].x);assert.equal(toc[0].y,toc[1].y);assert(toc[1].x>toc[0].x);assert.equal(detail[0].y,detail[1].y);assert(detail[1].x>detail[0].x);assert(detail[2].y>=detail[0].y+detail[0].h-1);}else{assert(detail[1].y>detail[0].y);}
assert(await p.locator('[data-readview="full"]').evaluate(e=>e.scrollWidth<=e.clientWidth+1));}
const styled='■ 직전 영상 대비 ▸\n이전 영상에서는 발표를 기다리며 관망하자는 의견이었습니다. 이번 영상에서도 방향은 같지만 설명의 중심 주제가 달라졌습니다.\n\n🟢\n직전 영상에서 제시한 확인 항목은 이번 영상에서 검증되지 않았습니다. 다음 기록에서는 그 결과를 확인할 필요가 있습니다.\n한마디로:\n\n방향은 유지되지만 근거와 확인 과정의 변화는 구분해서 읽어야 합니다.\n■ 신호 요약 ▸\n기존에 알려진 내용과 이번에 새로 제시된 내용을 구분합니다.\n🟢\n추가 확인이 필요한 내용은 원문 출처에서 확인합니다.\n🟡\n한마디로:\n표시와 설명을 함께 읽되 원문의 판단을 그대로 보존합니다.';
await p.evaluate(t=>{host.innerHTML='<div data-readview="full">'+RecordReading.formattedHTML(t)+'</div>';RecordReading.documentColumns(host);},styled);
assert.equal(await p.locator('[data-readview="full"]').textContent(),styled);assert.equal(await p.locator('.pg-takeaway').count(),2);assert.equal(await p.locator('.pg-inline-status').count(),3);
assert(await p.locator('.pg-topic-cell').evaluateAll(es=>es.every(e=>!/^([🟢🟡]|한마디로:)$/.test(e.textContent.trim()))));
for(const width of [1440,390]){await p.setViewportSize({width,height:1000});assert.equal(await p.locator('.pg-topic-pairs').first().evaluate(e=>getComputedStyle(e).gridTemplateColumns.split(' ').length),width>900?2:1);assert(await p.locator('[data-readview="full"]').evaluate(e=>e.scrollWidth<=e.clientWidth+1));}
await p.setViewportSize({width:1440,height:1000});await p.screenshot({path:'test-results/records-topic-pairs.png',fullPage:true});console.log('PASS: exact original, related heading groups, bounded chunks, row-major pairs, mobile order, no overflow, idempotence');}finally{await b.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
