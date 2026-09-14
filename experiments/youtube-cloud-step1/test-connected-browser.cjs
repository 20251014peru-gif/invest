const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawn} = require('node:child_process');
const {chromium} = require(process.env.TEST_PLAYWRIGHT_MODULE || 'playwright');
const token = 'synthetic-test-token-no-real-secret-1234';
const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'youtube-job-test-'));
let child, browser, external = 0;
const pause = ms => new Promise(r => setTimeout(r, ms));
async function start() {
  const ready = path.join(temp, 'ready.json');
  if (fs.existsSync(ready)) fs.unlinkSync(ready);
  child = spawn(process.env.TEST_PYTHON || 'python', [path.join(__dirname, 'job_service.py'), '--db', path.join(temp, 'jobs.sqlite'), '--ready-file', ready, '--processor', 'pipeline'],
    {env:{...process.env,YT_JOB_TEST_TOKEN:token},windowsHide:true,stdio:['ignore','pipe','pipe']});
  let errors=''; child.stderr.on('data',d=>errors+=d);
  for(let i=0;i<100;i++) {
    if(fs.existsSync(ready))return JSON.parse(fs.readFileSync(ready)).url;
    if(child.exitCode!==null)throw Error('Service failed: '+errors);
    await pause(100);
  }
  throw Error('Service readiness timeout: '+errors);
}
async function stop() {
  if(!child || child.exitCode!==null)return;
  const done=new Promise(r=>child.once('exit',r)); child.kill(); await done;
}
async function request(url,method='GET',body,auth=token) {
  const r=await fetch(url,{method,headers:{Authorization:'Bearer '+auth,'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined});
  return {status:r.status,data:await r.json()};
}
(async()=>{
  let url=await start();
  assert.equal((await request(url+'api/jobs','GET',undefined,'wrong')).status,401);
  assert.equal((await request(url+'api/jobs','GET',undefined,'é')).status,401);
  const body={request_key:'http-retry-test',payload:{title:'Retry test',transcript:'x'.repeat(400)}};
  const first=await request(url+'api/jobs','POST',body);
  assert.equal(first.status,202);
  const retry=await request(url+'api/jobs','POST',body);
  assert.equal(retry.status,200); assert.equal(retry.data.id,first.data.id);
  assert.equal((await request(url+'api/jobs','POST',{...body,payload:{...body.payload,title:'changed'}})).status,409);
  browser=await chromium.launch({headless:true,channel:'msedge'});
  async function pageAt(base) {
    const context=await browser.newContext();
    await context.route('**/*',route=>{
      if(route.request().url().startsWith(base))return route.continue();
      external++; return route.abort();
    });
    const page=await context.newPage(); await page.goto(base+'youtube.html');
    await page.locator('#queueToken').fill(token);
    return {context,page};
  }
  let {context,page}=await pageAt(url);
  await page.locator('#ytPasteBtn').click();
  await page.waitForFunction(()=>document.activeElement?.id==='ytpTitle');
  await page.locator('#ytpTitle').fill('Close and reopen test');
  await page.locator('#ytpCh').fill('Synthetic channel');
  await page.locator('#ytpDate').fill('2026-09-13');
  await page.locator('#ytpUrl').fill('https://www.youtube.com/watch?v=HHAg3sJ5tU4');
  await page.locator('#ytpText').fill('synthetic caption '.repeat(1500));
  await page.locator('#ytpTL').fill('00:00 Intro\n01:00 Second');
  await page.locator('#ytpTLCh').uncheck();
  await page.locator('#ytPasteBox button.go').click();
  await page.waitForFunction(()=>document.querySelector('#queueStatus').textContent.includes('접수 완료'));
  const rows=(await request(url+'api/jobs')).data.jobs;
  const id=rows.find(j=>j.title==='Close and reopen test').id;
  assert.notEqual(rows.find(j=>j.id===id).status,'succeeded');
  await context.close(); // No browser page remains while the server processes.
  for(let i=0;i<600;i++) {
    if((await request(url+'api/jobs/'+id)).data.status==='succeeded')break;
    await pause(100);
  }
  assert.equal((await request(url+'api/jobs/'+id)).data.status,'succeeded');
  await stop(); url=await start(); // Fresh process, same persisted database.
  ({context,page}=await pageAt(url));
  await page.locator('#queueRefresh').click();
  await page.locator(`li[data-id="${id}"][data-status="succeeded"]`).waitFor();
  const result=(await request(url+'api/jobs/'+id)).data.result;
  assert.equal(result.mode,'synthetic-pipeline');
  assert.equal(result.summary.제목,'Close and reopen test');
  assert.equal(result.summary.채널,'Synthetic channel');
  assert.equal(result.summary.게시일,'2026-09-13');
  assert.equal(result.summary.vid,'HHAg3sJ5tU4');
  assert.deepEqual(result.summary.marks.map(m=>m.t),[0,60]);
  assert(result.stages.filter(s=>s.stage==='chunk').length>=2);
  assert(result.stages.some(s=>s.stage==='profile'));
  assert(result.stages.some(s=>s.stage==='summary'));
  assert.equal(result.meta_requests,0);
  await page.locator(`li[data-id="${id}"] button`).click();
  await page.frameLocator('#queueResult').locator('h2').waitFor();
  await page.screenshot({path:path.join(__dirname,'connected-preview.png'),fullPage:false});
  assert.equal(result.ai_calls,0); assert.equal(result.firestore_writes,0);
  assert.equal((await request(url+'api/jobs')).data.jobs.length,2);
  assert.equal(external,0);
  console.log('PASS: existing paste UI -> durable queue -> original profile/chunk/summary/bookmarks -> restart -> result viewer. AI=0 Firestore=0 external browser requests=0.');
  await context.close();
})().catch(e=>{console.error(e);process.exitCode=1;}).finally(async()=>{
  if(browser)await browser.close(); await stop();
  fs.rmSync(temp,{recursive:true,force:true});
});
