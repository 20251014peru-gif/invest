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
  child = spawn(process.env.TEST_PYTHON || 'python', [path.join(__dirname, 'job_service.py'), '--db', path.join(temp, 'jobs.sqlite'), '--ready-file', ready],
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
  const body={request_key:'http-retry-test',payload:{title:'Retry test',transcript:'x'.repeat(100)}};
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
    const page=await context.newPage(); await page.goto(base);
    await page.locator('#token').fill(token);
    return {context,page};
  }
  let {context,page}=await pageAt(url);
  await page.locator('#title').fill('Close and reopen test');
  await page.locator('#transcript').fill('synthetic caption '.repeat(30));
  await page.locator('#submit').click();
  await page.waitForFunction(()=>document.querySelector('#status').textContent.includes('접수됐습니다'));
  const rows=(await request(url+'api/jobs')).data.jobs;
  const id=rows.find(j=>j.title==='Close and reopen test').id;
  assert.notEqual(rows.find(j=>j.id===id).status,'succeeded');
  await context.close(); // No browser page remains while the server processes.
  for(let i=0;i<100;i++) {
    if((await request(url+'api/jobs/'+id)).data.status==='succeeded')break;
    await pause(100);
  }
  assert.equal((await request(url+'api/jobs/'+id)).data.status,'succeeded');
  await stop(); url=await start(); // Fresh process, same persisted database.
  ({context,page}=await pageAt(url));
  await page.locator('#connect').click();
  await page.locator(`li[data-id="${id}"][data-status="succeeded"]`).waitFor();
  const result=(await request(url+'api/jobs/'+id)).data.result;
  assert.equal(result.ai_calls,0); assert.equal(result.firestore_writes,0);
  assert.equal((await request(url+'api/jobs')).data.jobs.length,2);
  assert.equal(external,0);
  console.log('PASS: HTTP auth/retry/conflict; browser closed before completion; server restarted; same result restored. AI=0 Firestore=0 external browser requests=0.');
  await context.close();
})().catch(e=>{console.error(e);process.exitCode=1;}).finally(async()=>{
  if(browser)await browser.close(); await stop();
  fs.rmSync(temp,{recursive:true,force:true});
});
