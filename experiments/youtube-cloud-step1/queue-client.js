/* Enabled only by the local job service, never by the original Flask page. */
(() => {
  let pending = null, busy = false, polling = false;
  const labels = {queued:'접수 완료',running:'요약 처리 중',succeeded:'완료',failed:'실패',uncertain:'중단 · 확인 필요'};
  const el = id => document.getElementById(id);
  const status = text => { el('queueStatus').textContent = text; };
  async function api(path, body) {
    const r = await fetch(path, {method: body ? 'POST' : 'GET', headers:{
      Authorization:'Bearer '+el('queueToken').value, 'Content-Type':'application/json'
    }, ...(body ? {body:JSON.stringify(body)} : {})});
    const data = await r.json();
    if(!r.ok) throw Error(data.error || '작업 서버 연결 실패');
    return data;
  }
  async function refresh() {
    if(polling || !el('queueToken').value) return;
    polling = true;
    try {
      const {jobs} = await api('/api/jobs');
      el('queueList').replaceChildren();
      for(const job of jobs) {
        const row = document.createElement('li'); row.dataset.id=job.id; row.dataset.status=job.status;
        const title = document.createElement('span'); title.textContent=job.title+' — '+labels[job.status]; row.append(title);
        if(job.result) {
          const button=document.createElement('button'); button.className='btn sub'; button.textContent='결과 열기';
          button.onclick=()=> {
            const result=job.result;
            el('queueResultTitle').textContent=job.title+' · 합성 AI 응답으로 검증한 결과';
            const frame=el('queueResult');
            frame.srcdoc='<meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'"><style>body{font:16px/1.7 sans-serif;padding:16px}</style>'+ (result.summary ? result.summary.html : '<p>결과 없음</p>');
            el('queueMarks').textContent=JSON.stringify(result.summary?.marks || []);
            el('queueOutput').hidden=false;
          };
          row.append(button);
        }
        if(job.error) { const error=document.createElement('p'); error.textContent=job.error; row.append(error); }
        el('queueList').append(row);
      }
    } catch(e) { status(e.message); }
    finally { polling=false; }
  }
  window.YTJobs = {submit: async (payload, overlay) => {
    if(busy) return;
    if(!el('queueToken').value) { status('먼저 시험용 접근 코드를 입력하세요.'); return; }
    if(pending && JSON.stringify(pending.payload)!==JSON.stringify(payload)) {
      status('이전 접수 여부가 불명확합니다. 같은 내용으로 접수를 확인하거나 작업 목록을 확인하세요.'); return;
    }
    pending=pending || {request_key:crypto.randomUUID(),payload};
    busy=true; const button=overlay.querySelector('button.go'); button.disabled=true;
    try {
      const job=await api('/api/jobs',pending); pending=null; overlay.classList.remove('on');
      status('접수 완료. 창을 닫아도 서버가 처리합니다. 작업 '+job.id); await refresh();
    } catch(e) { status(e.message+' 같은 내용으로 다시 누르면 중복 없이 접수를 확인합니다.'); }
    finally { busy=false; button.disabled=false; }
  }};
  document.addEventListener('DOMContentLoaded', () => {
    const section=document.createElement('section'); section.className='card';
    section.innerHTML='<h2>작업 연결 시험</h2><p>기존 자막·요약 처리 연결 · 실제 AI 호출 없음 · 결과는 로컬 보관</p><label>시험용 접근 코드<input id="queueToken" type="password" autocomplete="off"></label><button id="queueRefresh" class="btn sub">작업 불러오기</button><p id="queueStatus" role="status"></p><ul id="queueList"></ul><div id="queueOutput" hidden><h3 id="queueResultTitle"></h3><iframe id="queueResult" sandbox="" style="width:100%;height:480px;border:1px solid #ddd"></iframe><details><summary>보존한 책갈피</summary><pre id="queueMarks" style="white-space:pre-wrap"></pre></details></div>';
    document.querySelector('.wrap').prepend(section);
    el('queueRefresh').onclick=refresh;
    // Other legacy controls are not connected to durable storage in this test.
    document.querySelectorAll('.tabs,#goBtn,#dataLink').forEach(x=>x.style.display='none');
    el('url').disabled=true;
    const badge=document.querySelector('header .sync'); if(badge) badge.textContent='로컬 연결 시험';
    setInterval(refresh,700);
  });
})();
