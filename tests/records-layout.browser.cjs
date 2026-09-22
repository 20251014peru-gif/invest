const {chromium}=require('playwright'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const base=process.env.TEST_BASE_URL||'http://localhost:8923',output=path.resolve('test-results/records-layout');fs.mkdirSync(output,{recursive:true});
(async()=>{
  const browser=await chromium.launch({headless:true,...(process.platform==='win32'?{channel:'msedge'}:{})});
  try{
    const p=await browser.newPage({viewport:{width:1536,height:1080}}),errors=[];
    p.on('pageerror',e=>errors.push(e.message));await p.route('**/*',r=>r.request().url().startsWith(base+'/')||r.request().url().startsWith('data:')?r.continue():r.abort());
    await p.goto(base+'/records.html');await p.waitForFunction(()=>window.FU?.ready&&window.RC&&recordsLoaded);
    await p.evaluate(()=>__mockReset({records:{r:{kind:'memo',title:'분기 실적을 보고 남긴 생각',date:'2026-09-22',body:'매출보다 이익률이 개선되는지 먼저 확인한다.',stocks:['가상전자'],userJudgment:'다음 실적까지 관찰',checks:[]}},records_meta:{stocks:{list:[{name:'가상전자',status:'보유',quantity:'10',avgCost:'50000',targetPrice:'65000',customFields:[{label:'관심 이유',value:'수익성 회복을 확인하며 보유'},{label:'반증조건',value:'두 분기 연속 이익률 하락'},{label:'확인 지표',value:'분기 영업이익률 · 재고 회전율'}],thesisLog:[{date:'2026-09-19',text:'처음 검토한 이유'}]}]},checklist_templates:{list:[]}}}));
    await p.evaluate(()=>followupsStart());await p.waitForFunction(()=>FU.ready);
    await p.locator('#btnStockMgr').click();await p.locator('#content [data-stocktab="가상전자"]').first().click();
    const columns=await p.locator('.stockDashboard>section').evaluateAll(es=>es.map(e=>Math.round(e.getBoundingClientRect().top)));assert.equal(new Set(columns).size,1);
    await p.screenshot({path:path.join(output,'01-stock.png'),fullPage:true});
    await p.locator('#stockAddRecord').click();await p.waitForSelector('body.rw-active');
    for(const id of ['stockInput','fDate','fBody'])assert.ok(await p.locator('#'+id).isVisible(),id+' visible without opening additional fields');
    assert.equal(await p.evaluate(()=>curPickedKind()),'stock');assert.equal(await p.locator('#recModal .rw-step').count(),2);assert.ok(!await p.locator('#fUserJudge').isVisible());
    await p.screenshot({path:path.join(output,'02-record-compact.png'),fullPage:true});await p.locator('#moreFields>summary').click();
    await p.locator('#fTitle').fill('반도체 업황 점검');await p.locator('#fBody').fill('고객사의 재고 감소와 주문 회복이 동시에 나타나는지 확인한다.');await p.locator('#fOneLiner').fill('실적 회복의 지속성 확인');await p.locator('#fUserJudge').fill('다음 실적 발표 전까지 관찰한다.');
    const tops=await p.locator('#recModal .rw-step').evaluateAll(es=>es.map(e=>Math.round(e.getBoundingClientRect().top)));assert.equal(new Set(tops).size,1);
    for(const kind of ['idea','chart','news','youtube','memo','stock']){await p.locator('#kindSwitchBtn').click();await p.locator('#kindPick [data-k="'+kind+'"]').click();assert.equal(await p.locator('#fBody').inputValue(),'고객사의 재고 감소와 주문 회복이 동시에 나타나는지 확인한다.');}
    await p.screenshot({path:path.join(output,'02-record.png'),fullPage:true});
    await p.locator('#mSave').click();await p.waitForSelector('body:not(.rw-active)');assert.ok(await p.evaluate(()=>records.some(r=>r.kind==='stock'&&r.title==='반도체 업황 점검'&&r.userJudgment==='다음 실적 발표 전까지 관찰한다.')));assert.equal(await p.evaluate(()=>records.filter(r=>r.kind==='memo').length),1);
    await p.locator('#content [data-stockopen]').click();await p.waitForSelector('#stockDetailModal.on');await p.screenshot({path:path.join(output,'03-stock-editor.png'),fullPage:true});await p.locator('#sdClose').click();await p.waitForSelector('body:not(.rw-active)');
    await p.locator('#stockAddFollowup').click();await p.waitForSelector('#followupModal.on');await p.screenshot({path:path.join(output,'04-followup-compact.png'),fullPage:true});assert.ok(!await p.locator('#fuResult').isVisible());await p.locator('#fuQuestion').fill('다음 분기 영업이익률이 15%를 넘는가?');await p.locator('#fuExpectationPanel>summary').click();await p.locator('#fuExpected').fill('재고가 줄면서 이익률이 개선될 것으로 예상');await p.locator('#fuDue').fill('2026-10-25');await p.locator('#fuResultPanel>summary').click();await p.locator('#fuResult').fill('발표 자료에서 16%를 확인했다.');await p.locator('#fuReviewPanel>summary').click();await p.locator('#fuJudgment').selectOption('keep');await p.locator('#fuNext').fill('다음 분기에도 유지되는지 확인');
    await p.screenshot({path:path.join(output,'04-followup.png'),fullPage:true});await p.locator('#followupModal [data-fu="complete"]').click();await p.waitForSelector('body:not(.rw-active)');
    for(const width of [1024,768,390]){
      await p.setViewportSize({width,height:900});await p.locator('#stockAddRecord').click();await p.waitForSelector('body.rw-active');
      assert.ok(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'record overflow '+width);
      await p.screenshot({path:path.join(output,'record-'+width+'.png'),fullPage:true});await p.locator('#mClose').click();await p.waitForSelector('body:not(.rw-active)');
      await p.locator('#content [data-stockopen]').click();await p.waitForSelector('#stockDetailModal.on');assert.ok(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'stock overflow '+width);await p.locator('#sdClose').click();await p.waitForSelector('body:not(.rw-active)');
      await p.locator('#stockAddFollowup').click();await p.waitForSelector('#followupModal.on');assert.ok(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'followup overflow '+width);await p.locator('#followupModal [data-fu="close"]').first().click();await p.waitForSelector('body:not(.rw-active)');
    }
    await p.setViewportSize({width:1536,height:1080});await p.locator('#stockPrint').click();await p.waitForSelector('body.stock-printing');
    assert.equal(await p.locator('.stockPrintColumns').first().evaluate(e=>getComputedStyle(e).columnCount),'2');await p.screenshot({path:path.join(output,'05-print-2.png'),fullPage:true});
    await p.pdf({path:path.join(output,'print-2.pdf'),preferCSSPageSize:true,printBackground:true});
    await p.locator('#stockPrintColumns').selectOption('3');assert.equal(await p.locator('.stockPrintColumns').first().evaluate(e=>getComputedStyle(e).columnCount),'3');await p.pdf({path:path.join(output,'print-3.pdf'),preferCSSPageSize:true,printBackground:true});
    await p.locator('[data-print-close]').click();
    // Stress pagination with a long note, wide URL and actual attachment; final markers must survive PDF output.
    await p.evaluate(async()=>{await db.collection('records').doc('long').set({kind:'news',title:'긴 기록 출력 시험',date:'2026-09-22',stocks:['가상전자'],body:Array.from({length:90},(_,i)=>'문단 '+(i+1)+' — 매출 성장률과 영업이익률을 함께 확인한다. 수주가 실제 매출로 이어지는지 비교하고, 예상과 다른 결과도 남긴다.').join('\n')+'\nEND_OF_LONG_RECORD',link:'https://example.com/'+('long-path-'.repeat(35)),attachments:[{url:location.origin+'/tests/study-browser/fixture-chart.svg',name:'출력 확인용 차트'}]});});
    await p.locator('#stockPrint').click();await p.waitForSelector('body.stock-printing');await p.waitForFunction(()=>[...document.querySelectorAll('#stockPrintView img')].some(i=>i.complete&&i.naturalWidth>0));await p.pdf({path:path.join(output,'print-long.pdf'),preferCSSPageSize:true,printBackground:true});assert.match(await p.locator('#stockPrintView').textContent(),/END_OF_LONG_RECORD/);
    assert.deepEqual(errors,[]);console.log('PASS compact forms, optional detail disclosure, stock classification separate from memo, kind switching retains text, saving, responsive and print');
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
