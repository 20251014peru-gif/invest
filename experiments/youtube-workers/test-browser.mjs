import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import entry from './worker.mjs';
import {Storage,setup} from './test-support.mjs';
const require=createRequire(import.meta.url);
const {chromium}=require(process.env.TEST_PLAYWRIGHT_MODULE||'playwright');
const root=path.dirname(fileURLToPath(import.meta.url));
const token='test-only-not-a-secret-123456789012345';
let h=setup(),outside=0;
const env={APP_TOKEN:token,JOBS:{idFromName:()=>0,get:()=>h.jobs},ASSETS:{fetch:async(req)=>{
  const name=new URL(req.url).pathname==='/'?'index.html':new URL(req.url).pathname.slice(1);
  if(!['index.html','app.js','style.css'].includes(name))return new Response('',{status:404});
  return new Response(fs.readFileSync(path.join(root,'public',name)),{headers:{'content-type':name.endsWith('.js')?'application/javascript':name.endsWith('.css')?'text/css':'text/html; charset=utf-8'}});
}}};
const browser=await chromium.launch({headless:true,channel:'msedge'});
async function open(){const context=await browser.newContext();await context.route('**/*',async route=>{
  const r=route.request();if(!r.url().startsWith('https://local.test/')){outside++;return route.abort();}
  const response=await entry.fetch(new Request(r.url(),{method:r.method(),headers:r.headers(),...(r.postData()?{body:r.postData()}:{})}),env);
  await route.fulfill({status:response.status,headers:Object.fromEntries(response.headers),body:Buffer.from(await response.arrayBuffer())});
});const page=await context.newPage();await page.goto('https://local.test/');await page.locator('#token').fill(token);return {context,page};}
try{
  let {context,page}=await open();
  assert.equal(await page.locator('#updateNote').isChecked(),false);
  await page.locator('#title').fill('서버 없는 요약 연결 시험');await page.locator('#channel').fill('시험 채널');
  await page.locator('#transcript').fill('로컬 시험용 자막 문장입니다. '.repeat(1200));
  await page.locator('#timeline').fill('00:00 시작\n01:00 다음');
  await page.locator('#submit').click();await page.waitForFunction(()=>document.querySelector('#status').textContent.includes('접수 완료'));
  await page.locator('#submit').click();await page.waitForFunction(()=>document.querySelector('#status').textContent.includes('기존 작업'));
  assert.equal((await h.storage.get('index')).length,1);await context.close();
  await h.jobs.alarm();h=setup({},new Storage(structuredClone(h.storage.map)));
  for(let i=0;i<15;i++)await h.jobs.alarm();
  h=setup({},new Storage(structuredClone(h.storage.map)));
  ({context,page}=await open());await page.locator('#connect').click();await page.getByText('결과·비용 보기').click();
  await page.frameLocator('#result').locator('h2').waitFor();
  assert.equal(await page.locator('#marks li').count(),2);
  assert.equal(await page.locator('#noteWrap').isVisible(),false);
  await page.locator('#output').scrollIntoViewIfNeeded();
  await page.screenshot({path:path.join(root,'preview.png'),fullPage:true});
  assert.equal(outside,0);await context.close();
  console.log('PASS browser: paste, duplicate reuse, page closed, object recreated, summary/costs/marks restored; external requests=0.');
}finally{await browser.close();}
