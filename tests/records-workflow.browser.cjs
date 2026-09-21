const {chromium}=require('playwright'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const base=process.env.TEST_BASE_URL||'http://localhost:8923';
const output=path.resolve(process.env.TEST_OUTPUT_DIR||'test-results/records-workflow');fs.mkdirSync(output,{recursive:true});
(async()=>{
  const browser=await chromium.launch({headless:true,...(process.platform==='win32'?{channel:'msedge'}:{})});
  try{
    const p=await browser.newPage({viewport:{width:1440,height:1050}}),errors=[];
    p.on('pageerror',e=>errors.push(e.message));await p.route('**/*',r=>r.request().url().startsWith(base+'/')||r.request().url().startsWith('data:')?r.continue():r.abort());
    await p.goto(base+'/records.html');await p.waitForFunction(()=>window.FU?.ready&&window.RC&&recordsLoaded);
    await p.evaluate(()=>__mockReset({records:{r:{kind:'memo',title:'실적 점검 메모',date:'2026-09-20',body:'가상 시험 자료입니다.\n다음 분기 이익률을 확인한다.',stocks:['가상전자'],checks:[{id:'check1',what:'영업이익률 확인',date:'2026-09-22',action:'15% 이상 예상'}],unknownField:{keep:true}}},records_meta:{stocks:{list:[{name:'가상전자',status:'보유',quantity:'10',avgCost:'50000',customFields:[{label:'관심 이유',value:'수익성 회복을 확인하며 보유'},{label:'반증조건',value:'두 분기 연속 이익률 하락'}],thesisLog:[{date:'2026-09-19',text:'처음 검토한 이유'}]},'빈 종목']},checklist_templates:{list:[]}}}));
    await p.evaluate(()=>followupsStart());await p.waitForFunction(()=>FU.items.some(x=>x.question==='영업이익률 확인'));
    const original=await p.evaluate(()=>JSON.stringify(__mockDump().records));
    await p.locator('#btnStockMgr').click();await p.locator('#content [data-stocktab="가상전자"]').first().click();
    assert.match(await p.locator('.stockOverview').textContent(),/수익성 회복/);
    assert.equal(await p.locator('#content details.stockDetails').getAttribute('open'),null);
    assert.equal(await p.locator('#content .stockTask').count(),1);
    await p.screenshot({path:path.join(output,'desktop.png'),fullPage:true});
    await p.locator('#content [data-stockopen]').click();await p.waitForSelector('body.rw-active');
    assert.equal(await p.locator('#recordEditorHost #stockDetailModal.on').count(),1);
    await p.locator('#sdCustomFields .cfVal').first().fill('수정 중인 이유');
    await p.locator('#sdCfLabel').fill('리스크');await p.locator('#sdCfValue').fill('환율');await p.locator('#sdCfAddBtn').click();
    assert.equal(await p.evaluate(()=>stockItemOf('가상전자').customFields.length),2);
    p.once('dialog',d=>d.dismiss());await p.locator('#sdClose').click();assert.equal(await p.locator('#sdCustomFields .cfVal').first().inputValue(),'수정 중인 이유');
    await p.evaluate(()=>{__mockFail='offline';});await p.locator('#sdSaveFields').click();await p.waitForFunction(()=>!_stockSaving);assert.match(await p.locator('#stockSaveStatus').textContent(),/저장되지/);
    assert.equal(await p.locator('#sdCustomFields .cfVal').count(),3);
    await p.evaluate(()=>{__mockFail='';});await p.locator('#sdSaveFields').click();await p.waitForFunction(()=>!_stockSaving&&stockItemOf('가상전자').customFields.length===3);
    if(await p.locator('#stockDetailModal').isVisible())await p.locator('#sdClose').click();
    await p.waitForSelector('body:not(.rw-active)');
    // Stable question identity across stock, calendar, completion and followup child.
    await p.locator('#content .stockTask').click();await p.waitForSelector('#followupModal.on');
    await p.locator('#fuDue').fill('2026-09-25');await p.locator('#followupModal [data-fu="save"]').click();await p.waitForSelector('body:not(.rw-active)');
    await p.evaluate(()=>{curView='cal';calYM='2026-09';render();});
    assert.equal(await p.locator('[data-daypop="2026-09-22"]').count(),0);assert.equal(await p.locator('[data-daypop="2026-09-25"]').count(),1);
    await p.locator('[data-daypop="2026-09-25"]').click();await p.locator('#dayModal [data-open-fu]').click();await p.waitForSelector('#followupModal.on');
    await p.locator('#fuResult').fill('공식 실적 발표에서 16%를 확인');await p.locator('#followupModal [data-fu="complete"]').click();await p.waitForSelector('body:not(.rw-active)');
    assert.equal(await p.locator('[data-daypop="2026-09-25"]').count(),0);assert.equal(await p.evaluate(()=>FU.pending.length),0);
    assert.equal(await p.evaluate(()=>JSON.stringify(__mockDump().records)),original);
    await p.locator('#stockAddFollowup').click();await p.waitForSelector('#fuStocks');assert.equal(await p.locator('#fuStocks').inputValue(),'가상전자');
    await p.locator('#fuQuestion').fill('다음 분기 매출 확인');await p.locator('#fuDue').fill('2026-10-25');await p.locator('#followupModal [data-fu="save"]').click();await p.waitForSelector('body:not(.rw-active)');
    const newId=await p.evaluate(()=>FU.items.find(x=>x.question==='다음 분기 매출 확인').id);
    await p.evaluate(id=>FU.open(id),newId);await p.locator('[data-fu="followup"]').click();await p.waitForFunction(()=>document.getElementById('fuQuestion').value==='');
    assert.equal(await p.locator('#fuStocks').inputValue(),'가상전자');await p.locator('#fuQuestion').fill('후속 질문');await p.locator('#followupModal [data-fu="save"]').click();await p.waitForSelector('body:not(.rw-active)');
    assert.ok(await p.evaluate(id=>FU.items.some(x=>x.parentFollowupId===id&&x.stocks.includes('가상전자')),newId));
    // Realtime rerenders must not destroy a live input. Failed retries and double click create one record.
    await p.evaluate(()=>{curView='list';render();});await p.locator('#stockAddRecord').click();await p.waitForSelector('#recModal.on');
    await p.locator('#fBody').fill('새 투자논지와 근거');await p.evaluate(()=>render());assert.equal(await p.locator('#fBody').inputValue(),'새 투자논지와 근거');
    await p.evaluate(()=>attZoom('http://localhost:8923/__test/files/missing'));assert.ok(await p.locator('#attZoomModal').isVisible());await p.locator('#attZoomClose').click();assert.ok(await p.locator('#recModal').isVisible());
    p.once('dialog',d=>d.dismiss());await p.locator('#mClose').click();assert.equal(await p.locator('#recModal.on').count(),1);
    await p.evaluate(()=>{__mockFail='offline';});await p.locator('#mSave').click();await p.waitForFunction(()=>!_recordSaving);assert.equal(await p.locator('#fBody').inputValue(),'새 투자논지와 근거');
    await p.evaluate(()=>{__mockFail='';document.getElementById('mSave').click();document.getElementById('mSave').click();});await p.waitForSelector('body:not(.rw-active)');
    assert.equal(await p.evaluate(()=>records.filter(x=>x.body==='새 투자논지와 근거').length),1);
    // An edit merges unrelated concurrent fields; conflicting body changes stay on screen.
    await p.evaluate(()=>openEdit('r'));await p.waitForSelector('#recModal.on');await p.locator('#fBody').fill('내가 수정한 본문');
    await p.evaluate(async()=>{await db.collection('records').doc('r').update({unknownField:{remote:true}});});await p.locator('#mSave').click();await p.waitForSelector('body:not(.rw-active)');
    assert.deepEqual(await p.evaluate(()=>__mockDump().records.r.unknownField),{remote:true});
    await p.evaluate(()=>openEdit('r'));await p.waitForSelector('#recModal.on');await p.locator('#fBody').fill('충돌 중 내 입력');
    await p.evaluate(async()=>{await db.collection('records').doc('r').update({body:'다른 기기의 본문'});});await p.locator('#mSave').click();await p.waitForFunction(()=>!_recordSaving);
    assert.equal(await p.locator('#fBody').inputValue(),'충돌 중 내 입력');assert.equal(await p.evaluate(()=>__mockDump().records.r.body),'다른 기기의 본문');
    p.once('dialog',d=>d.accept());await p.locator('#mClose').click();await p.waitForSelector('body:not(.rw-active)');
    // Reader -> editor -> reader returns to the source without stacking dialogs.
    await p.evaluate(()=>openPage('r'));await p.locator('#pgEdit').click();await p.waitForSelector('body.rw-active');assert.ok(!await p.locator('#pageModal').isVisible());await p.locator('#mClose').click();await p.waitForSelector('body:not(.rw-active)');assert.ok(await p.locator('#pageModal').isVisible());await p.locator('#pgClose').click();
    await p.setViewportSize({width:390,height:844});await p.evaluate(()=>{curView='list';render();});await p.screenshot({path:path.join(output,'mobile.png'),fullPage:true});
    assert.ok(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
    await p.locator('#stockAddFollowup').click();await p.waitForSelector('#followupModal.on');assert.ok(await p.locator('.fu-modal').evaluate(e=>e.scrollWidth<=e.clientWidth+1));await p.screenshot({path:path.join(output,'mobile-editor.png'),fullPage:true});await p.locator('#followupModal [data-fu="close"]').first().click();await p.waitForSelector('body:not(.rw-active)');
    await p.evaluate(id=>localStorage.setItem('fu_draft_'+id,JSON.stringify({revision:FU.items.find(x=>x.id===id).revision,patch:{question:'이전 버전의 초안',stocks:['가상전자']}})),newId);
    await p.evaluate(id=>FU.open(id),newId);await p.locator('[data-fu="draft"]').click();assert.equal(await p.locator('#fuQuestion').inputValue(),'이전 버전의 초안');p.once('dialog',d=>d.accept());await p.locator('#followupModal [data-fu="close"]').first().click();await p.waitForSelector('body:not(.rw-active)');
    await p.locator('#stockPrint').click();await p.waitForSelector('body.stock-printing');assert.match(await p.locator('#stockPrintView').textContent(),/공식 실적 발표/);assert.equal(await p.locator('#stockPrintView textarea').count(),0);
    await p.emulateMedia({media:'print'});assert.ok(!await p.locator('.stockPrintActions').isVisible());await p.screenshot({path:path.join(output,'print.png'),fullPage:true});await p.emulateMedia({media:'screen'});await p.locator('[data-print-close]').click();
    assert.deepEqual(errors,[]);
    console.log('PASS unified stock workflow: staged fields, dirty guard, offline retry, canonical calendar, completion, stock tags, children, input preservation, duplicate prevention, concurrent edits, reader return, mobile, print');
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
