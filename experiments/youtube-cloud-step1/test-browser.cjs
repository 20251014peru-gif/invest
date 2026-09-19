const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
const {chromium}=require(process.env.TEST_PLAYWRIGHT_MODULE || 'playwright');
const root=__dirname;

function fakeFirebase(){
  const data=new Map();
  window.__fakeWrites=[];
  const profile={출력섹션:['핵심내용'],분야:'테스트'};
  data.set('youtube_channels/테스트채널',profile);
  data.set('youtube_summaries/s_existing',{id:'s_existing',vid:'OTHERVIDEO1',채널:'테스트채널',제목:'기존 합성 자료',일시:'2026-09-14',게시일:'2026-09-14',ts:Date.now(),html:'<p>기존 자료</p>',marks:[{t:12,label:'기존 책갈피',cap:'/captures/OTHERVIDEO1/t_12.jpg'}],memo:'기존 메모'});
  function docSnap(id,v){return {id,exists:v!==undefined,data:()=>v};}
  function collection(name,filters=[]){
    return {
      where:(...f)=>collection(name,[...filters,f]),
      orderBy:()=>collection(name,filters),limit:()=>collection(name,filters),
      get:async()=>{
        const docs=[...data].filter(([k,v])=>k.startsWith(name+'/')&&filters.every(([field,op,value])=>op!=='=='||v[field]===value)).map(([k,v])=>docSnap(k.slice(name.length+1),v));
        return {docs,empty:!docs.length,size:docs.length,forEach:fn=>docs.forEach(fn)};
      },
      doc:id=>({
        get:async()=>docSnap(id,data.get(name+'/'+id)),
        set:async(v,opts)=>{data.set(name+'/'+id,opts&&opts.merge?{...data.get(name+'/'+id),...v}:v);window.__fakeWrites.push({name,id,value:v});},
        update:async v=>{data.set(name+'/'+id,{...data.get(name+'/'+id),...v});window.__fakeWrites.push({name,id,value:v});},
        delete:async()=>data.delete(name+'/'+id)
      })
    };
  }
  const firestore=()=>({collection});
  firestore.FieldValue={increment:n=>n,arrayUnion:(...x)=>x};
  window.firebase={initializeApp:()=>{},firestore,auth:()=>({signInAnonymously:async()=>({user:{uid:'FAKE'}}),onAuthStateChanged:fn=>setTimeout(()=>fn({uid:'FAKE'}),0)})};
}

(async()=>{
  const browser=await chromium.launch({headless:true,channel:'msedge'});
  try{
    for(const split of [false,true]){
      const context=await browser.newContext({serviceWorkers:'block'});
      const api=split?'https://api.test.invalid':'http://localhost:5101';
      const media=split?'https://media.test.invalid':api;
      const site=split?'https://pages.test.invalid/invest/youtube/':'http://localhost:5101/';
      const requests=[],errors=[];
      await context.addInitScript(fakeFirebase);
      await context.route('**/*',async route=>{
        const req=route.request(),u=new URL(req.url());
        requests.push({url:req.url(),method:req.method(),body:req.postData()});
        if(u.pathname.endsWith('connection-config.js'))return route.fulfill({contentType:'application/javascript',body:`window.YT_CONNECTION_CONFIG=${JSON.stringify({apiBase:api,captureBase:media})};`});
        if(u.pathname.endsWith('/api/health'))return route.fulfill({json:{ok:true,api_key:true,version:'v38-c1-0914',cost:{total_usd:0,limit_usd:1}}});
        if(u.pathname.endsWith('/api/claude'))return route.fulfill({json:{text:'<h2>핵심내용</h2><p>합성 시험 요약입니다.</p>'}});
        if(u.pathname.endsWith('/api/capture'))return route.fulfill({json:{results:[]}});
        if(u.pathname.endsWith('/api/fixes'))return route.fulfill({json:{fixes:{}}});
        if(u.pathname.endsWith('/api/ticker'))return route.fulfill({json:{error:'SYNTHETIC'}});
        if(u.pathname.endsWith('/api/meta'))return route.fulfill({status:500,json:{error:'Paste must bypass meta'}});
        if(u.host==='pages.test.invalid'||u.host==='localhost:5101'){
          const name=u.pathname.endsWith('/')?'youtube.html':u.pathname==='/data'?'data.html':u.pathname.split('/').pop();
          if(['youtube.html','data.html','connection.js'].includes(name))return route.fulfill({contentType:name.endsWith('.js')?'application/javascript':'text/html',body:fs.readFileSync(path.join(root,name),'utf8')});
        }
        // No real network. SDK scripts, images, iframes are replaced/blocked.
        if(req.resourceType()==='script')return route.fulfill({contentType:'application/javascript',body:''});
        return route.abort();
      });
      const page=await context.newPage();
      page.on('pageerror',e=>errors.push(e.message));
      page.on('dialog',d=>d.dismiss());
      await page.goto(site+(split?'youtube.html':''));
      await page.locator('#ytPasteBtn').click();
      await page.locator('#ytpTitle').fill('합성 시험 영상');
      await page.locator('#ytpCh').fill('테스트채널');
      await page.locator('#ytpUrl').fill('https://www.youtube.com/watch?v=HHAg3sJ5tU4');
      await page.locator('#ytpText').fill('이 문장은 가짜 시험 자막이며 실제 투자 분석이 아닙니다. '.repeat(130));
      await page.locator('#ytPasteBox button.go').click();
      await page.waitForFunction(()=>window.__fakeWrites.some(x=>x.name==='youtube_summaries'&&x.value.제목==='합성 시험 영상'));
      const writes=await page.evaluate(()=>window.__fakeWrites);
      assert(writes.some(x=>x.value.html&&x.value.html.includes('합성 시험 요약')));
      assert.equal(requests.filter(x=>x.url.includes('/api/meta')).length,0,'paste bypass');
      const calls=requests.filter(x=>x.url.includes('/api/claude'));
      assert(calls.length>0);assert(calls.every(x=>x.url===api+'/api/claude'));
      assert(calls.some(x=>JSON.parse(x.body).user.includes('가짜 시험 자막')));
      assert.equal(await page.locator('#dataLink').getAttribute('href'),split?site+'data.html':site+'data');
      if(split){
        assert(!requests.some(x=>x.url.includes('localhost:5055')));
        await page.screenshot({path:path.join(root,'synthetic-preview.png'),fullPage:false});
      }
      assert.deepEqual(errors,[],'page errors');
      console.log('PASS browser:',split?'separate HTTPS frontend/API/media':'local Flask address','paste -> fake AI -> fake Firestore');
      const figure=await page.evaluate(()=>captureFigureHtml('/captures/v/t_12.jpg','시험',12));
      assert(figure.includes(media+'/captures/v/t_12.jpg'));
      await page.goto(split?site+'data.html':site+'data');
      await page.waitForFunction(()=>document.querySelector('img[src*="/captures/OTHERVIDEO1/"]'));
      const img=await page.locator('img[src*="/captures/OTHERVIDEO1/"]').first().getAttribute('src');
      assert.equal(img,media+'/captures/OTHERVIDEO1/t_12.jpg');
      const target=await page.locator('a:has-text("요약 열기")').first().getAttribute('href');
      assert.equal(target,site+(split?'youtube.html':'')+'?open=s_existing');
      assert.deepEqual(errors,[],'data page errors');
      console.log('PASS browser: existing record, capture URL and return-to-summary link');
      await context.close();
    }
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
