/* Transitional server-side harness: original UI pipeline, synthetic I/O only. */
const fs=require('node:fs');
const path=require('node:path');
const {chromium}=require(process.env.TEST_PLAYWRIGHT_MODULE || 'playwright');
const root=__dirname;
async function run(payload) {
  const browser=await chromium.launch({headless:true,channel:'msedge'});
  const calls=[];
  let metaRequests=0;
  try {
    const context=await browser.newContext({serviceWorkers:'block'});
    await context.addInitScript({path:path.join(root,'offline-fixture.js')});
    await context.route('**/*',async route=> {
      const req=route.request(),u=new URL(req.url());
      if(u.origin==='http://pipeline.test.invalid') {
        const name=u.pathname==='/'?'youtube.html':u.pathname.slice(1);
        if(['youtube.html','connection-config.js','connection.js'].includes(name))
          return route.fulfill({contentType:name.endsWith('.js')?'application/javascript':'text/html',body:fs.readFileSync(path.join(root,name),'utf8')});
      }
      if(u.pathname==='/api/claude') {
        const body=req.postDataJSON();
        const stage=body.max_tokens===2000?'profile':body.max_tokens===4000?'chunk':body.max_tokens===12000?'summary':'auxiliary';
        calls.push({stage,input_chars:body.user.length});
        let text;
        if(stage==='profile') text=JSON.stringify({분야:'합성 시험',출력섹션:['핵심내용']});
        else if(stage==='chunk') text='합성 구간 정리: '+body.user.slice(0,100);
        else text='<h2>핵심내용</h2><p>합성 시험 요약입니다. 실제 AI가 작성한 내용이 아닙니다.</p><!--FRAMING:{"fact":100}--><!--SECTOR:시험-->';
        return route.fulfill({json:{text}});
      }
      if(u.pathname==='/api/meta') { metaRequests++; return route.fulfill({status:500,json:{error:'Paste bypass failed'}}); }
      if(u.pathname==='/api/health') return route.fulfill({json:{ok:true,api_key:true,version:'v38-c1-0914',cost:{total_usd:0,limit_usd:0}}});
      if(u.pathname==='/api/fixes') return route.fulfill({json:{fixes:{}}});
      if(u.pathname==='/api/capture') return route.fulfill({json:{results:[]}});
      if(req.resourceType()==='script')return route.fulfill({contentType:'application/javascript',body:''});
      return route.abort(); // No request ever reaches an external endpoint.
    });
    const page=await context.newPage();
    page.on('dialog',d=>d.dismiss());
    await page.goto('http://pipeline.test.invalid/');
    // Notes are a separate multi-video feature, outside this job's scope.
    await page.evaluate(()=> { window.rebuildNote=async()=>{}; });
    await page.locator('#ytPasteBtn').click();
    await page.waitForFunction(()=>document.activeElement?.id==='ytpTitle');
    await page.locator('#ytpTitle').fill(payload.title);
    await page.locator('#ytpCh').fill(payload.channel || '시험채널');
    await page.locator('#ytpUrl').fill(payload.url || '');
    await page.locator('#ytpDate').fill(payload.publishDate || '');
    await page.locator('#ytpText').fill(payload.transcript);
    await page.locator('#ytpTL').fill(payload.timeline || '');
    await page.locator('#ytpTLCh').setChecked(!!payload.chaptersOnly);
    await page.locator('#ytPasteBox button.go').click();
    await page.waitForFunction(()=>window.__localWrites.some(x=>x.name==='youtube_summaries' && x.value.html),null,{timeout:60000});
    const summary=await page.evaluate(()=>window.__localWrites.find(x=>x.name==='youtube_summaries' && x.value.html).value);
    if(metaRequests || !calls.some(c=>c.stage==='summary'))throw Error('Pipeline validation failed');
    return {mode:'synthetic-pipeline',text:'기존 요약 처리 연결 시험 완료',summary,
      input_chars:payload.transcript.length,stages:calls,ai_calls:0,firestore_writes:0,meta_requests:metaRequests};
  } finally { await browser.close(); }
}
if(require.main===module) {
  let raw=''; process.stdin.setEncoding('utf8'); process.stdin.on('data',x=>raw+=x);
  process.stdin.on('end',()=>run(JSON.parse(raw)).then(x=>process.stdout.write(JSON.stringify(x)))
    .catch(()=>{process.stderr.write('Synthetic pipeline failed');process.exitCode=1;}));
}
module.exports={run};
