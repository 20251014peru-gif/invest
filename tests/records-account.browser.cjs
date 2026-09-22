const {chromium}=require('playwright'),assert=require('node:assert/strict');
const base=process.env.TEST_BASE_URL||'http://localhost:8923';
(async()=>{
  const browser=await chromium.launch({headless:true,...(process.platform==='win32'?{channel:'msedge'}:{})});
  try{
    const p=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
    p.on('pageerror',e=>errors.push(e.message));
    await p.route('**/*',r=>r.request().url().startsWith(base+'/')||r.request().url().startsWith('data:')?r.continue():r.abort());
    await p.goto(base+'/records.html');await p.waitForFunction(()=>window.FU?.ready&&recordsLoaded);
    await p.locator('#authBtn').click();await p.locator('#authPanel').waitFor({state:'visible'});
    assert.match(await p.locator('#authAccount').textContent(),/test@example.com/);
    assert.equal(await p.evaluate(()=>__mockAuthStats.popups),0);
    await p.locator('#authCheck').click();await p.waitForFunction(()=>document.querySelector('#authStatus').textContent.includes('접근할 수'));
    await p.locator('#authChoose').click();await p.waitForFunction(()=>!document.querySelector('#authChoose').disabled);
    assert.equal(await p.evaluate(()=>__mockAuthStats.popups),1);assert.equal(await p.evaluate(()=>__mockAuthStats.signOuts),0);
    for(const [code,message] of [['auth/popup-blocked','차단됐습니다'],['auth/popup-closed-by-user','닫혔습니다'],['auth/unauthorized-domain','허용 주소']]){
      await p.evaluate(c=>__mockAuthFailure=c,code);await p.locator('#authChoose').click();
      await p.waitForFunction(text=>document.querySelector('#authStatus').textContent.includes(text),message);
      assert.ok(await p.locator('#authChoose').isEnabled());assert.equal(await p.evaluate(()=>firebase.auth().currentUser.uid),'test-user');
    }
    await p.evaluate(()=>{__mockAuthFailure=null;__mockFail='offline';});await p.locator('#authCheck').click();
    await p.waitForFunction(()=>document.querySelector('#authStatus').textContent.includes('서버 연결 실패'));await p.evaluate(()=>__mockFail=null);
    await p.locator('#btnAdd').click();await p.locator('#fBody').fill('작성 중인 글을 보존한다.');
    const before=await p.evaluate(()=>__mockAuthStats.popups);await p.locator('#authChoose').click();
    assert.match(await p.locator('#authStatus').textContent(),/작성 중인 내용/);assert.equal(await p.evaluate(()=>__mockAuthStats.popups),before);
    assert.equal(await p.locator('#fBody').inputValue(),'작성 중인 글을 보존한다.');
    // Cancelling the shared navigation must keep the same form and values.
    p.once('dialog',d=>d.dismiss());await p.locator('[data-editor="followupModal"]').click();
    assert.ok(await p.locator('#recModal').isVisible());assert.equal(await p.locator('#fBody').inputValue(),'작성 중인 글을 보존한다.');
    await p.locator('#fBody').fill('');await p.locator('[data-editor="followupModal"]').click();await p.locator('#fuQuestion').waitFor({state:'visible'});
    assert.equal(await p.locator('#recordEditorHost .rw-panel.on').count(),1);
    await p.locator('#followupModal [data-fu="close"]').first().click();
    await p.evaluate(()=>firebase.auth().signOut());await p.locator('#authBtn').click();
    await p.waitForFunction(()=>document.querySelector('#authStatus').textContent.includes('접근할 수'));
    assert.equal(await p.evaluate(()=>firebase.auth().currentUser.uid),'test-user');
    assert.deepEqual(errors,[]);console.log('PASS account panel, connection check, popup login, recoverable errors, session retention and shared-editor dirty guard');
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
