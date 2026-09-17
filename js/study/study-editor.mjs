// 공부노트 작성창 — 넓은 서식 편집기 + 검색용 속성 + 참고 자료/가설 연결 + 이 기기 초안 + 충돌 비교.
import {Editor, extensions, cleanHTML, convertMarkflowText, foldKey} from './study-editor-kit.mjs';
import * as C from './study-core.mjs';

const DRAFT_PREFIX = 'records.study.draft.';
const NEW_INDEX = 'records.study.newDrafts';
const $ = (root, sel) => root.querySelector(sel);
const hm = t => new Date(t).toLocaleTimeString('ko-KR', {hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false});
const kb = n => Math.round(n / 1024) + 'KB';

function lsGet(k) { try { return JSON.parse(localStorage.getItem(k) || 'null'); } catch { return null; } }
function lsSet(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); return true; } catch { return false; } }
function lsDel(k) { try { localStorage.removeItem(k); } catch { /* 무시 */ } }
export function listNewDrafts() { return (lsGet(NEW_INDEX) || []).map(id => lsGet(DRAFT_PREFIX + id)).filter(d => d && d.isNew); }
export function hasDraft(id) { return !!lsGet(DRAFT_PREFIX + id); }

let S = null; // 현재 편집 세션(한 번에 하나)

const M = ' data-tier="more"';
// 모바일에서는 자주 쓰는 도구(굵게·글자색·강조·목록·이미지·실행 취소)만 한 줄로 보이고 나머지는 [⋯ 더보기]로 펼친다
const TOOLBAR = `
<button type="button" data-cmd="bold" aria-label="굵게 (Ctrl+B)" title="굵게 (Ctrl+B)"><b>B</b></button>
<button type="button" data-pop="color" aria-label="글자색" title="글자색" aria-haspopup="true"><span class="st-a">A</span>▾</button>
<button type="button" data-pop="highlight" aria-label="배경 강조색" title="배경 강조색" aria-haspopup="true"><span class="st-hlicon">가</span>▾</button>
<button type="button" data-cmd="bulletList" aria-label="글머리표 목록" title="글머리표 목록">•≡</button>
<button type="button" data-cmd="image" aria-label="이미지 추가" title="이미지 추가">🖼</button>
<button type="button" data-cmd="undo" aria-label="실행 취소 (Ctrl+Z)" title="실행 취소 (Ctrl+Z)">↶</button>
<button type="button" data-cmd="more" class="st-morebtn" aria-label="서식 도구 더보기" aria-expanded="false" title="더보기">⋯</button>
<span class="st-sep"${M}></span>
<select data-cmd="block" aria-label="문단 형식" title="문단 형식"${M}><option value="p">본문</option><option value="1">제목 1</option><option value="2">제목 2</option><option value="3">제목 3</option></select>
<button type="button" data-cmd="italic" aria-label="기울임 (Ctrl+I)" title="기울임 (Ctrl+I)"${M}><i>I</i></button>
<button type="button" data-cmd="underline" aria-label="밑줄 (Ctrl+U)" title="밑줄 (Ctrl+U)"${M}><u>U</u></button>
<button type="button" data-cmd="strike" aria-label="취소선" title="취소선"${M}><s>S</s></button>
<button type="button" data-pop="link" aria-label="링크" title="링크 (Ctrl+K)" aria-haspopup="true"${M}>🔗</button>
<span class="st-sep"${M}></span>
<button type="button" data-cmd="orderedList" aria-label="번호 목록" title="번호 목록"${M}>1.</button>
<button type="button" data-cmd="taskList" aria-label="체크 목록" title="체크 목록"${M}>☑</button>
<button type="button" data-cmd="sink" aria-label="들여쓰기(하위 목록)" title="들여쓰기 (Tab)"${M}>⇥</button>
<button type="button" data-cmd="lift" aria-label="내어쓰기" title="내어쓰기 (Shift+Tab)"${M}>⇤</button>
<button type="button" data-cmd="blockquote" aria-label="인용" title="인용"${M}>❝</button>
<button type="button" data-cmd="hr" aria-label="구분선" title="구분선"${M}>―</button>
<button type="button" data-cmd="table" aria-label="표 추가" title="표 추가"${M}>▦</button>
<span class="st-sep"${M}></span>
<button type="button" data-cmd="redo" aria-label="다시 실행 (Ctrl+Shift+Z)" title="다시 실행"${M}>↷</button>
<button type="button" data-cmd="unfoldAll" aria-label="접은 섹션 모두 펼치기" title="접은 섹션 모두 펼치기"${M}>⇕</button>`;

function shell(bridge) {
  let root = document.getElementById('studyModal');
  if (root) return root;
  const V = bridge.VERIFY_STATES || {};
  root = document.createElement('div');
  root.id = 'studyModal';
  root.className = 'study-layer';
  root.setAttribute('role', 'dialog');
  root.setAttribute('aria-modal', 'true');
  root.setAttribute('aria-labelledby', 'stHeadTitle');
  root.innerHTML = `
<div class="st-shell">
  <header class="st-head">
    <b id="stHeadTitle">📚 공부노트</b>
    <span class="st-status" id="stStatus" role="status" aria-live="polite"></span>
    <span class="st-sp"></span>
    <button type="button" class="st-hbtn" id="stTocBtn" aria-pressed="false" title="제목으로 만든 목차">목차</button>
    <button type="button" class="st-hbtn" id="stFullBtn" aria-pressed="false" title="전체 화면">⛶ 전체 화면</button>
    <button type="button" class="st-save" id="stSave">저장</button>
    <button type="button" class="st-hbtn st-x" id="stClose" aria-label="닫기">✕</button>
  </header>
  <div class="st-scroll" id="stScroll">
    <div class="st-form">
      <label class="st-f st-titlef"><span>제목</span><input type="text" id="stTitle" maxlength="300" placeholder="무엇을 공부했나요?"></label>
      <label class="st-f"><span>핵심 정리 <small>나중에 목록에서 읽을 1~3줄</small></span><textarea id="stOneLiner" rows="2" maxlength="600" aria-label="핵심 정리"></textarea></label>
      <div class="st-props">
        <label class="st-f"><span>정리 유형</span><select id="stType">${Object.entries(C.STUDY_TYPES).map(([k, v]) => `<option value="${k}">${v}</option>`).join('')}</select></label>
        <label class="st-f st-grow"><span>주제 <small>쉼표로 구분</small></span><input type="text" id="stTopics" placeholder="예: AI, 반도체, 금리"></label>
        <label class="st-f"><span>정리 상태</span><select id="stStatusSel">${Object.entries(C.STUDY_STATUS).map(([k, v]) => `<option value="${k}">${v}</option>`).join('')}</select></label>
      </div>
    </div>
    <div class="st-toolbar" role="toolbar" aria-label="서식 도구" id="stToolbar">${TOOLBAR}</div>
    <div class="st-pop" id="stPop" hidden></div>
    <div class="st-ctx" id="stCtx" hidden></div>
    <details class="st-notice" id="stPasteNotice"></details>
    <div class="st-edwrap">
      <nav class="st-edtoc" id="stEdToc" aria-label="목차" hidden></nav>
      <div class="st-editor" id="stEditor"></div>
    </div>
    <input type="file" id="stImgFile" accept="image/*" multiple hidden>
    <section class="st-rels">
      <div class="st-relcol"><h4>참고 자료</h4><div id="stRefs"></div><button type="button" class="st-mini" id="stAddRef">＋ 참고 자료 연결</button></div>
      <div class="st-relcol"><h4>관련 투자 가설</h4><div id="stHyps"></div><button type="button" class="st-mini" id="stAddHyp">＋ 가설 연결</button></div>
      <p class="st-hint">참고 자료로 연결해도 ‘뒷받침’ 관계는 자동으로 생기지 않아요.</p>
    </section>
    <label class="st-f"><span>🙋 내 판단</span><textarea id="stJudge" rows="3" placeholder="이 공부로 내린 내 판단"></textarea></label>
    <details class="st-more" id="stMore">
      <summary>추가 속성 (종목·산업·테마·기준일·재검토일·확인사항·출처·AI 해석·검증 상태)</summary>
      <div class="st-f"><span>🏷 종목</span><div class="st-chips" id="stStocks"></div><div class="st-row"><input type="text" id="stStockInput" list="stStockList" placeholder="종목명 입력 후 Enter"><datalist id="stStockList"></datalist><button type="button" class="st-mini" id="stStockAdd">추가</button></div></div>
      <div class="st-props">
        <label class="st-f st-grow"><span>산업 <small>쉼표로 구분</small></span><input type="text" id="stIndustries"></label>
        <label class="st-f st-grow"><span>테마 <small>쉼표로 구분</small></span><input type="text" id="stThemes"></label>
      </div>
      <div class="st-props">
        <label class="st-f"><span>자료 기준일 <small>비우면 미지정</small></span><input type="date" id="stAsOf"></label>
        <label class="st-f"><span>재검토일 <small>비우면 미지정</small></span><input type="date" id="stReview"></label>
        <label class="st-f"><span>검증 상태</span><select id="stVerify"><option value="">(선택 안 함)</option>${(bridge.VERIFY_ORDER || Object.keys(V)).map(k => `<option value="${k}">${C.esc(V[k]?.n || k)}</option>`).join('')}</select></label>
      </div>
      <p class="st-hint">‘정리 완료’는 사실 확인 완료가 아닙니다. 검증 상태는 직접 고를 때만 저장돼요.</p>
      <div class="st-f"><span>📅 다음 확인사항 <small>기록보관실 체크 캘린더와 같은 항목</small></span><div id="stChecks"></div><button type="button" class="st-mini" id="stCheckAdd">＋ 확인일 추가</button></div>
      <div class="st-props">
        <label class="st-f st-grow"><span>출처 이름</span><input type="text" id="stSrcName"></label>
        <label class="st-f st-grow"><span>출처 주소</span><input type="url" id="stSrcUrl" placeholder="https://"></label>
      </div>
      <label class="st-f"><span>🤖 AI 해석 <small>내 판단과 구분</small></span><textarea id="stAi" rows="2"></textarea></label>
      <div class="st-f"><span>원본 정보</span><div class="st-origin" id="stOrigin"></div></div>
      <div class="st-f"><span>이전 판</span><div id="stHistory"></div></div>
    </details>
  </div>
  <div class="st-dock" id="stDock"></div>
  <div class="st-dialog" id="stDialog" hidden></div>
</div>`;
  document.body.append(root);
  return root;
}

/* ── 폼 ── */
function readForm(root) {
  return {
    title: $(root, '#stTitle').value, oneLiner: $(root, '#stOneLiner').value,
    studyType: $(root, '#stType').value, studyStatus: $(root, '#stStatusSel').value,
    topics: $(root, '#stTopics').value, industries: $(root, '#stIndustries').value, themes: $(root, '#stThemes').value,
    stocks: S.stocks.slice(), asOfDate: $(root, '#stAsOf').value, reviewAt: $(root, '#stReview').value,
    checks: [...root.querySelectorAll('#stChecks .st-check')].map(r => ({date: r.querySelector('[data-c=d]').value, what: r.querySelector('[data-c=w]').value.trim(), action: r.querySelector('[data-c=a]').value.trim()})),
    userJudgment: $(root, '#stJudge').value, aiInterpretation: $(root, '#stAi').value, verifyState: $(root, '#stVerify').value,
    sourceName: $(root, '#stSrcName').value, sourceUrl: $(root, '#stSrcUrl').value
  };
}
function fillForm(root, f) {
  $(root, '#stTitle').value = f.title || '';
  $(root, '#stOneLiner').value = f.oneLiner || '';
  $(root, '#stType').value = C.STUDY_TYPES[f.studyType] ? f.studyType : 'concept';
  $(root, '#stStatusSel').value = C.STUDY_STATUS[f.studyStatus] ? f.studyStatus : 'learning';
  $(root, '#stTopics').value = C.cleanList(f.topics).join(', ');
  $(root, '#stIndustries').value = C.cleanList(f.industries).join(', ');
  $(root, '#stThemes').value = C.cleanList(f.themes).join(', ');
  S.stocks = C.cleanList(f.stocks);
  $(root, '#stAsOf').value = f.asOfDate || '';
  $(root, '#stReview').value = f.reviewAt || '';
  $(root, '#stJudge').value = f.userJudgment || '';
  $(root, '#stAi').value = f.aiInterpretation || '';
  $(root, '#stVerify').value = f.verifyState || '';
  $(root, '#stSrcName').value = f.sourceName ?? f.source?.name ?? f.channel ?? '';
  $(root, '#stSrcUrl').value = f.sourceUrl ?? f.source?.url ?? f.link ?? '';
  $(root, '#stChecks').innerHTML = '';
  (f.checks || []).forEach(c => addCheckRow(root, c));
  const managed = S.bridge.followupsReady?.() && S.bridge.records().some(r => r.id === S.id);
  root.querySelector('#stCheckAdd').hidden = !!managed;
  if (managed) { $(root, '#stChecks').innerHTML = '<p class="st-hint">확인 항목은 기록보관실의 확인·복기에서 관리합니다. 기존 질문은 보존됩니다.</p>'; }
  renderStocks(root);
}
function formFromRecord(r) { return {...r, sourceName: r.source?.name ?? r.channel ?? '', sourceUrl: r.source?.url ?? r.link ?? ''}; }
function addCheckRow(root, c = {}) {
  const row = document.createElement('div');
  row.className = 'st-check';
  row.innerHTML = `<input type="date" data-c="d" aria-label="확인 날짜"><input type="text" data-c="w" placeholder="확인할 것" aria-label="확인할 것"><input type="text" data-c="a" placeholder="그때 할 행동" aria-label="그때 할 행동"><button type="button" class="st-mini" aria-label="확인일 삭제">✕</button>`;
  row.querySelector('[data-c=d]').value = c.date || '';
  row.querySelector('[data-c=w]').value = c.what || '';
  row.querySelector('[data-c=a]').value = c.action || '';
  row.querySelector('button').onclick = () => { row.remove(); changed(); };
  $(root, '#stChecks').append(row);
}
function renderStocks(root) {
  const host = $(root, '#stStocks');
  host.innerHTML = S.stocks.map(s => `<span class="st-chip">${C.esc(s)}<button type="button" data-rm="${C.esc(s)}" aria-label="${C.esc(s)} 빼기">✕</button></span>`).join('') || '<small class="st-muted">연결한 종목 없음</small>';
  host.querySelectorAll('[data-rm]').forEach(b => b.onclick = () => { S.stocks = S.stocks.filter(x => x !== b.dataset.rm); renderStocks(root); changed(); });
}

/* ── 상태 표시 ── */
function status(msg, tone = '') {
  const el = document.getElementById('stStatus');
  if (!el) return;
  el.textContent = msg;
  el.dataset.tone = tone;
}
function refreshStatus() {
  if (!S) return;
  const parts = [];
  if (!navigator.onLine) parts.push('연결 끊김');
  if (S.saving) parts.push('서버에 저장 중…');
  else if (S.lastError) parts.push(S.lastError);
  else if (isDirty()) parts.push(S.lastDraftAt ? '저장 안 됨 · 이 기기에 임시 보관 ' + hm(S.lastDraftAt) : '저장 안 됨');
  else if (S.lastSavedAt) parts.push('서버 저장됨 ' + hm(S.lastSavedAt));
  else if (S.base) parts.push('서버 저장본');
  if (S.uploads.size) parts.push('이미지 보관 중 ' + S.uploads.size + '개');
  status(parts.join(' · '), S.lastError ? 'err' : (isDirty() ? 'dirty' : 'ok'));
  const saveBtn = S.root.querySelector('#stSave');
  if (saveBtn) saveBtn.disabled = S.saving; // 저장 중 중복 클릭 방지(저장 함수 자체도 S.saving 이면 다시 실행하지 않음)
}

/* ── 문서·비교 ── */
function snapshot() {
  const doc = S.editor.getJSON();
  return {form: readForm(S.root), doc, assets: S.assets.slice(), relAdd: S.relAdd.slice(), relRemove: S.relRemove.slice(), origin: S.origin, reason: S.reason};
}
function comparable(snap) {
  const f = snap.form;
  return JSON.stringify([f.title.trim(), f.oneLiner.trim(), f.studyType, f.studyStatus, C.cleanList(f.topics), C.cleanList(f.industries), C.cleanList(f.themes), f.stocks, f.asOfDate, f.reviewAt, f.checks.filter(c => c.date || c.what || c.action), f.userJudgment.trim(), f.aiInterpretation.trim(), f.verifyState, f.sourceName.trim(), f.sourceUrl.trim(), C.docToPlainText(snap.doc), JSON.stringify(snap.doc), snap.relAdd, snap.relRemove]);
}
function isDirty() { return !!S && !!S.editor && comparable(snapshot()) !== S.baseline; }
// 초안에는 업로드 중인 임시 이미지(blob·data 주소)를 남기지 않는다
function draftDoc(doc) {
  const d = JSON.parse(JSON.stringify(doc));
  C.walk(d, n => { if (n.type === 'image' && n.attrs && n.attrs.status === 'uploading') { n.attrs.status = 'missing'; n.attrs.note = '보관이 끝나기 전에 닫힌 이미지 — 다시 첨부해 주세요'; n.attrs.src = null; n.attrs.tempId = null; } });
  return d;
}
function writeDraft() {
  if (!S || !S.editor) return;
  if (!isDirty()) { lsDel(DRAFT_PREFIX + S.id); dropNewIndex(S.id); S.lastDraftAt = 0; refreshStatus(); return; }
  const snap = snapshot();
  const ok = lsSet(DRAFT_PREFIX + S.id, {v: 1, id: S.id, isNew: !S.base, savedAt: Date.now(), expected: S.expected, baseRevision: S.base?.studyRevision || 0, ...snap, doc: draftDoc(snap.doc)});
  if (ok) {
    S.lastDraftAt = Date.now();
    if (!S.base) { const idx = lsGet(NEW_INDEX) || []; if (!idx.includes(S.id)) lsSet(NEW_INDEX, idx.concat(S.id).slice(-20)); }
  } else S.lastError = '이 기기 임시 보관 실패(저장 공간 부족) — 서버 저장을 권장합니다';
  refreshStatus();
}
function dropNewIndex(id) { const idx = lsGet(NEW_INDEX) || []; if (idx.includes(id)) lsSet(NEW_INDEX, idx.filter(x => x !== id)); }
export function discardDraft(id) { lsDel(DRAFT_PREFIX + id); dropNewIndex(id); }
let draftTimer = 0;
function changed() {
  if (!S) return;
  S.lastError = '';
  clearTimeout(draftTimer);
  draftTimer = setTimeout(writeDraft, 800);
  refreshStatus();
}

/* ── 이미지 ── */
function findImage(pred) {
  let hit = null;
  S.editor.state.doc.descendants((n, pos) => { if (!hit && n.type.name === 'image' && pred(n.attrs)) hit = {node: n, pos}; return !hit; });
  return hit;
}
function setImageAttrs(tempId, attrs) {
  if (!S?.editor) return false;
  const hit = findImage(a => a.tempId === tempId);
  if (!hit) return false;
  S.editor.view.dispatch(S.editor.state.tr.setNodeMarkup(hit.pos, null, {...hit.node.attrs, ...attrs}).setMeta('addToHistory', false));
  return true;
}
function tempId() { return 't' + Date.now().toString(36) + Math.random().toString(36).slice(2, 7); }
async function dataUrlToBlob(u) { const r = await fetch(u); return r.blob(); }
function runUpload(tid, getBlob, meta = {}) {
  const session = S;
  const job = (async () => {
    try {
      const blob = await getBlob();
      const asset = await session.store.uploadImage(blob, {name: meta.name || ''});
      if (S !== session) return; // 편집창이 이미 닫힘 — 파일은 보존(삭제하지 않음)
      session.assets.push(asset);
      setImageAttrs(tid, {src: asset.url, assetId: asset.id, status: 'stored', tempId: null, note: null, originalSrc: meta.originalSrc || null});
      if (meta.blobUrl) URL.revokeObjectURL(meta.blobUrl);
    } catch (e) {
      if (S !== session) return;
      const reason = e.message === 'IMAGE_TOO_LARGE' ? '8MB 초과' : e.message === 'NOT_IMAGE' ? '이미지 파일이 아님' : meta.external ? '원본 사이트가 복사를 허용하지 않음' : '업로드 실패';
      setImageAttrs(tid, meta.external ? {status: 'external', src: null, tempId: null, originalSrc: meta.originalSrc, note: reason} : {status: 'missing', src: null, tempId: null, note: reason});
      session.notices.push('이미지 ' + (meta.external ? '보관 안 됨(외부 이미지): ' : '누락: ') + reason);
      showNotices();
    } finally {
      session.uploads.delete(tid);
      if (S === session) { changed(); updateContext(); }
    }
  })();
  session.uploads.set(tid, job);
  refreshStatus();
  return job;
}
function insertFiles(files, pos) {
  const imgs = [...files].filter(f => /^image\//.test(f.type));
  if (!imgs.length) return false;
  const {schema} = S.editor.state;
  let tr = S.editor.state.tr;
  const nodes = imgs.map(f => {
    const tid = tempId(), blobUrl = URL.createObjectURL(f);
    runUpload(tid, async () => f, {name: f.name, blobUrl});
    return schema.nodes.image.create({src: blobUrl, alt: '', status: 'uploading', tempId: tid});
  });
  const at = pos ?? tr.selection.to;
  nodes.slice().reverse().forEach(n => { tr = tr.insert(at, n); });
  S.editor.view.dispatch(tr);
  return true;
}
function pasteImageRule(raw) {
  const src = String(raw || '').trim();
  if (/^data:image\/(png|jpe?g|gif|webp|avif|bmp);base64,/i.test(src)) {
    const tid = tempId();
    S.pendingPaste.push({tid, get: () => dataUrlToBlob(src), meta: {name: '붙여넣은 이미지'}});
    return {'data-status': 'uploading', 'data-temp-id': tid, src};
  }
  if (/^https?:\/\//i.test(src)) {
    const tid = tempId();
    S.pendingPaste.push({tid, get: async () => { const r = await fetch(src, {mode: 'cors', credentials: 'omit'}); if (!r.ok) throw Error('HTTP ' + r.status); return r.blob(); }, meta: {external: true, originalSrc: C.safeHref(src)}});
    return {'data-status': 'uploading', 'data-temp-id': tid, 'data-original-src': C.safeHref(src), src: C.safeImageUrl(src) || null};
  }
  S.notices.push('이미지 누락: ' + (/^[a-z][a-z0-9+.-]*:/i.test(src) ? '임시·로컬 주소(' + src.split(':')[0] + ')' : '주소가 없거나 잘못된') + ' 이미지는 붙여넣기로 가져올 수 없어요 — 파일로 첨부해 주세요');
  return {'data-status': 'missing', 'data-note': '임시 주소 이미지 — 파일로 다시 첨부해 주세요', src: null};
}
function flushPendingPaste() {
  const list = S.pendingPaste.splice(0);
  for (const p of list) if (findImage(a => a.tempId === p.tid)) runUpload(p.tid, p.get, p.meta);
}
/* v7.28.2: 본문 밖 고정된 한 자리(#stPasteNotice)에만 표시 — 붙여넣을 때마다 새 상자를 쌓지 않고,
   이 세션에서 있었던 안내를 접힌 요약 한 줄로 모아두고 필요할 때만 펼쳐본다. 확인 버튼으로 닫을 필요가
   없다(다음 편집에 방해되지 않는 조용한 자리) — 노트를 닫으면 비운다(closeEditor). */
function showNotices() {
  const box = S?.root?.querySelector('#stPasteNotice');
  if (!box) return;
  if (!S.notices.length) { box.removeAttribute('open'); box.innerHTML = ''; return; }
  const uniq = [...new Set(S.notices)];
  box.innerHTML = '<summary>⚠ 붙여넣기 안내 ' + uniq.length + '건 — 사진·본문 누락 또는 링크 제거</summary><ul>' + uniq.map(n => '<li>' + C.esc(n) + '</li>').join('') + '</ul>';
}

/* ── 서식 도구 ── */
// 휴대폰에서 도구 버튼을 누르는 순간 선택이 풀리는 경우, 방금 전 선택 범위로 되돌려 적용한다
const MARK_CMDS = new Set(['bold', 'italic', 'underline', 'strike']);
function restoreRange() {
  const e = S.editor, r = S.lastRange;
  if (e.state.selection.empty && r && r.doc === e.state.doc) e.commands.setTextSelection({from: r.from, to: r.to});
}
function rememberRange() {
  if (!S?.editor) return;
  const sel = S.editor.state.selection;
  if (!sel.empty && !sel.node) S.lastRange = {from: sel.from, to: sel.to, doc: S.editor.state.doc};
  else if (Date.now() - (S.toolDownAt || 0) > 900) S.lastRange = null; // 사용자가 직접 선택을 푼 경우만 잊는다
}
function exec(cmd) {
  if (cmd === 'more') { const tb = S.root.querySelector('#stToolbar'); const on = !tb.classList.contains('show-more'); tb.classList.toggle('show-more', on); tb.querySelector('[data-cmd=more]').setAttribute('aria-expanded', String(on)); return; }
  if (MARK_CMDS.has(cmd)) restoreRange();
  const e = S.editor, ch = e.chain().focus();
  switch (cmd) {
    case 'bold': ch.toggleBold().run(); break;
    case 'italic': ch.toggleItalic().run(); break;
    case 'underline': ch.toggleUnderline().run(); break;
    case 'strike': ch.toggleStrike().run(); break;
    case 'bulletList': ch.toggleBulletList().run(); break;
    case 'orderedList': ch.toggleOrderedList().run(); break;
    case 'taskList': ch.toggleTaskList().run(); break;
    case 'sink': if (!e.chain().focus().sinkListItem('listItem').run()) e.chain().focus().sinkListItem('taskItem').run(); break;
    case 'lift': if (!e.chain().focus().liftListItem('listItem').run()) e.chain().focus().liftListItem('taskItem').run(); break;
    case 'blockquote': ch.toggleBlockquote().run(); break;
    case 'hr': ch.setHorizontalRule().run(); break;
    case 'table': ch.insertTable({rows: 3, cols: 3, withHeaderRow: true}).run(); break;
    case 'image': S.root.querySelector('#stImgFile').click(); break;
    case 'undo': ch.undo().run(); break;
    case 'redo': ch.redo().run(); break;
    case 'unfoldAll': e.view.dispatch(e.state.tr.setMeta(foldKey, {clear: true})); break;
  }
}
function popover(kind, anchor) {
  const pop = S.root.querySelector('#stPop');
  if (!pop.hidden && pop.dataset.kind === kind) { pop.hidden = true; return; }
  pop.dataset.kind = kind;
  const e = S.editor;
  if (kind === 'color' || kind === 'highlight') {
    const list = kind === 'color' ? C.TEXT_COLORS : C.HIGHLIGHT_COLORS;
    pop.innerHTML = '<div class="st-swatches">' + list.map(c => `<button type="button" class="st-sw" data-v="${c.value}" style="${kind === 'color' ? 'color:' + c.value : 'background:' + c.value}" aria-label="${c.label}${kind === 'color' ? ' 글자색' : ''}" title="${c.label}">${kind === 'color' ? 'A' : '가'}</button>`).join('') + '</div><button type="button" class="st-mini" data-v="">색 없음</button>';
    pop.querySelectorAll('[data-v]').forEach(b => b.onclick = () => {
      restoreRange();
      const v = b.dataset.v, ch = e.chain().focus();
      if (kind === 'color') (v ? ch.setColor(v) : ch.unsetColor()).run();
      else (v ? ch.setHighlight({color: v}) : ch.unsetHighlight()).run();
      pop.hidden = true;
    });
  } else if (kind === 'link') {
    const cur = e.getAttributes('link').href || '';
    pop.innerHTML = `<label class="st-f"><span>링크 주소</span><input type="url" id="stLinkUrl" placeholder="https://" value="${C.esc(cur)}"></label><div class="st-row"><button type="button" class="st-mini" id="stLinkOk">적용</button><button type="button" class="st-mini" id="stLinkRm">링크 제거</button></div><small class="st-muted" id="stLinkMsg"></small>`;
    const inp = pop.querySelector('#stLinkUrl');
    const apply = () => {
      restoreRange();
      const h = C.safeHref(inp.value.trim());
      if (!h) { pop.querySelector('#stLinkMsg').textContent = 'http(s) 또는 mailto 주소만 쓸 수 있어요'; return; }
      if (e.state.selection.empty && !e.isActive('link')) e.chain().focus().insertContent({type: 'text', text: h, marks: [{type: 'link', attrs: {href: h}}]}).run();
      else e.chain().focus().extendMarkRange('link').setLink({href: h}).run();
      pop.hidden = true;
    };
    pop.querySelector('#stLinkOk').onclick = apply;
    inp.onkeydown = ev => { if (ev.key === 'Enter') { ev.preventDefault(); apply(); } };
    pop.querySelector('#stLinkRm').onclick = () => { e.chain().focus().extendMarkRange('link').unsetLink().run(); pop.hidden = true; };
    setTimeout(() => inp.focus(), 0);
  }
  pop.hidden = false;
  if (S.root.classList.contains('is-docked')) { pop.style.left = ''; pop.style.top = ''; return; } // 모바일: 도구줄 바로 위에 붙여 표시
  const r = anchor.getBoundingClientRect(), pr = S.root.querySelector('.st-shell').getBoundingClientRect();
  pop.style.left = Math.max(8, Math.min(r.left - pr.left, pr.width - 260)) + 'px';
  pop.style.top = (r.bottom - pr.top + 4) + 'px';
}
function updateToolbar() {
  const e = S.editor, tb = S.root.querySelector('#stToolbar');
  const act = {bold: e.isActive('bold'), italic: e.isActive('italic'), underline: e.isActive('underline'), strike: e.isActive('strike'), bulletList: e.isActive('bulletList'), orderedList: e.isActive('orderedList'), taskList: e.isActive('taskList'), blockquote: e.isActive('blockquote')};
  tb.querySelectorAll('button[data-cmd]').forEach(b => { if (b.dataset.cmd in act) b.setAttribute('aria-pressed', String(act[b.dataset.cmd])); });
  tb.querySelector('[data-cmd=undo]').disabled = !e.can().undo();
  tb.querySelector('[data-cmd=redo]').disabled = !e.can().redo();
  const lvl = [1, 2, 3].find(l => e.isActive('heading', {level: l}));
  tb.querySelector('[data-cmd=block]').value = lvl ? String(lvl) : 'p';
}
function updateContext() {
  if (!S?.editor) return;
  const e = S.editor, ctx = S.root.querySelector('#stCtx');
  const sel = e.state.selection;
  const img = sel.node && sel.node.type.name === 'image' ? sel.node : null;
  if (img) {
    const a = img.attrs;
    ctx.innerHTML = `<b>이미지</b>
      <span class="st-group" role="group" aria-label="이미지 폭">${['25%', '50%', '75%', '100%'].map(w => `<button type="button" data-w="${w}" aria-pressed="${(a.width || '100%') === w}">${w}</button>`).join('')}</span>
      <span class="st-group" role="group" aria-label="이미지 정렬">${[['left', '왼쪽'], ['center', '가운데'], ['right', '오른쪽']].map(([v, l]) => `<button type="button" data-al="${v}" aria-pressed="${(a.align || 'center') === v}">${l}</button>`).join('')}</span>
      <label class="st-inline">대체 설명 <input type="text" id="stAlt" value="${C.esc(a.alt || '')}" placeholder="이미지 설명(화면 읽기용)"></label>
      <button type="button" data-img="replace">파일로 교체</button><button type="button" data-img="del">이미지 삭제</button>
      ${a.status === 'external' ? '<small class="st-warn">외부 이미지 — 아직 보관되지 않음</small>' : a.status === 'missing' ? '<small class="st-warn">누락된 이미지' + (a.note ? ' — ' + C.esc(a.note) : '') + '</small>' : ''}`;
    const pos = sel.from;
    const upd = attrs => e.view.dispatch(e.state.tr.setNodeMarkup(pos, null, {...e.state.doc.nodeAt(pos).attrs, ...attrs}));
    ctx.querySelectorAll('[data-w]').forEach(b => b.onclick = () => upd({width: b.dataset.w === '100%' ? null : b.dataset.w}));
    ctx.querySelectorAll('[data-al]').forEach(b => b.onclick = () => upd({align: b.dataset.al === 'center' ? null : b.dataset.al}));
    ctx.querySelector('#stAlt').onchange = ev => upd({alt: ev.target.value.trim()});
    ctx.querySelector('[data-img=del]').onclick = () => e.chain().focus().deleteSelection().run();
    ctx.querySelector('[data-img=replace]').onclick = () => { S.replacePos = pos; S.root.querySelector('#stImgFile').click(); };
    ctx.hidden = false;
  } else if (e.isActive('table')) {
    ctx.innerHTML = `<b>표</b><button type="button" data-t="addRowBefore">위에 행</button><button type="button" data-t="addRowAfter">아래에 행</button><button type="button" data-t="addColumnBefore">왼쪽에 열</button><button type="button" data-t="addColumnAfter">오른쪽에 열</button><button type="button" data-t="deleteRow">행 삭제</button><button type="button" data-t="deleteColumn">열 삭제</button><button type="button" data-t="toggleHeaderRow">머리행 전환</button><button type="button" data-t="mergeOrSplit">셀 합치기/나누기</button><button type="button" data-t="deleteTable">표 삭제</button>`;
    ctx.querySelectorAll('[data-t]').forEach(b => b.onclick = () => e.chain().focus()[b.dataset.t]().run());
    ctx.hidden = false;
  } else { ctx.hidden = true; ctx.innerHTML = ''; }
}
function renderEdToc() {
  const nav = S.root.querySelector('#stEdToc');
  if (nav.hidden) return;
  const hs = [];
  S.editor.state.doc.forEach((n, pos) => { if (n.type.name === 'heading') hs.push({pos, level: n.attrs.level, text: n.textContent || '(제목 없음)'}); });
  nav.innerHTML = '<b>목차</b>' + (hs.map(h => `<button type="button" class="st-toc-l${h.level}" data-pos="${h.pos}">${C.esc(h.text)}</button>`).join('') || '<small class="st-muted">제목 1~3을 쓰면 목차가 생겨요</small>');
  nav.querySelectorAll('[data-pos]').forEach(b => b.onclick = () => {
    const pos = Number(b.dataset.pos), e = S.editor;
    e.chain().focus().setTextSelection(pos + 1).run();
    const dom = e.view.nodeDOM(pos);
    if (dom?.scrollIntoView) dom.scrollIntoView({block: 'start', behavior: 'smooth'});
  });
}

/* ── 연결 ── */
function relState() {
  const recs = S.bridge.records();
  const view = C.relationView(recs.concat(S.base ? [] : [{id: S.id, relations: []}]), S.id);
  const key = x => x.targetId + '|' + x.type;
  const removed = new Set(S.relRemove.map(key));
  const fwd = view.all.filter(x => x.dir === 'fwd' && !removed.has(key(x)));
  const byId = new Map(recs.map(r => [r.id, r]));
  for (const a of S.relAdd) fwd.push({targetId: a.targetId, type: a.type, target: byId.get(a.targetId) || null, dir: 'fwd', pending: true});
  const isIdea = x => x.target?.kind === 'idea';
  return {refs: fwd.filter(x => x.type === 'references' || !isIdea(x)), hyps: fwd.filter(x => isIdea(x) && x.type !== 'references'), revHyps: view.hypotheses.filter(x => x.dir === 'rev')};
}
function relChip(x, removable) {
  const k = S.bridge.KINDS?.[x.target?.kind] || {i: '📄', n: '기록'};
  const lbl = C.RELATION_TYPES[x.type]?.fwd || '관련';
  const title = x.target ? C.esc(x.target.title || '(제목 없음)') : '<span class="st-warn">삭제됐거나 찾을 수 없는 기록</span>';
  return `<div class="st-rel${x.target ? '' : ' is-missing'}"><span>${k.i}</span> <span class="st-reltitle">${title}</span> <small class="st-muted">${C.esc(lbl)}${x.pending ? ' · 저장 전' : ''}${x.dir === 'rev' ? ' · 가설 쪽에서 연결' : ''}</small>${removable ? `<button type="button" class="st-mini" data-relrm="${C.esc(x.targetId)}" data-reltype="${C.esc(x.type)}" aria-label="연결 해제">✕</button>` : ''}</div>`;
}
function renderRels() {
  const st = relState(), root = S.root;
  root.querySelector('#stRefs').innerHTML = st.refs.map(x => relChip(x, true)).join('') || '<small class="st-muted">연결한 자료 없음</small>';
  root.querySelector('#stHyps').innerHTML = st.hyps.map(x => relChip(x, true)).join('') + st.revHyps.map(x => relChip(x, false)).join('') || '<small class="st-muted">연결한 가설 없음</small>';
  root.querySelectorAll('[data-relrm]').forEach(b => b.onclick = () => {
    const t = {targetId: b.dataset.relrm, type: b.dataset.reltype};
    const i = S.relAdd.findIndex(a => a.targetId === t.targetId && a.type === t.type);
    if (i >= 0) S.relAdd.splice(i, 1); else S.relRemove.push(t);
    renderRels(); changed();
  });
}
function pickRecord(mode) {
  const dlg = S.root.querySelector('#stDialog');
  const ideas = mode === 'hyp';
  dlg.innerHTML = `<div class="st-dbox" role="dialog" aria-label="${ideas ? '투자 가설 연결' : '참고 자료 연결'}"><h3>${ideas ? '관련 투자 가설 연결' : '참고 자료 연결'}</h3>
    ${ideas ? '<label class="st-f"><span>관계</span><select id="stPickType"><option value="related">관련</option><option value="supports">이 노트가 가설을 뒷받침</option><option value="contradicts">이 노트가 가설과 상충</option></select></label>' : ''}
    <input type="search" id="stPickQ" placeholder="제목·종목·주제로 찾기" aria-label="기록 찾기"><div class="st-picklist" id="stPickList"></div>
    <div class="st-row"><button type="button" class="st-mini" id="stPickClose">닫기</button></div></div>`;
  dlg.hidden = false;
  const list = dlg.querySelector('#stPickList');
  const draw = q => {
    q = q.toLowerCase();
    const rows = S.bridge.records().filter(r => r.id !== S.id && (ideas ? r.kind === 'idea' : true)).filter(r => !q || [r.title, r.oneLiner, (r.stocks || []).join(' '), (r.topics || []).join(' '), r.channel].join(' ').toLowerCase().includes(q)).slice(0, 60);
    list.innerHTML = rows.map(r => `<button type="button" class="st-pick" data-id="${C.esc(r.id)}">${(S.bridge.KINDS?.[r.kind] || {i: '📄'}).i} <b>${C.esc(r.title || '(제목 없음)')}</b> <small class="st-muted">${C.esc(r.date || '')}</small></button>`).join('') || '<small class="st-muted">찾는 기록이 없어요</small>';
    list.querySelectorAll('[data-id]').forEach(b => b.onclick = () => {
      const type = ideas ? dlg.querySelector('#stPickType').value : 'references';
      const t = {targetId: b.dataset.id, type};
      const ri = S.relRemove.findIndex(a => a.targetId === t.targetId && a.type === t.type);
      if (ri >= 0) S.relRemove.splice(ri, 1);
      else if (!relState().refs.concat(relState().hyps).some(x => x.targetId === t.targetId && x.type === t.type)) S.relAdd.push(t);
      dlg.hidden = true; renderRels(); changed();
    });
  };
  draw('');
  dlg.querySelector('#stPickQ').oninput = ev => draw(ev.target.value.trim());
  dlg.querySelector('#stPickClose').onclick = () => { dlg.hidden = true; };
  setTimeout(() => dlg.querySelector('#stPickQ').focus(), 0);
}

/* ── 원본·이전 판 ── */
function renderOrigin() {
  const o = S.origin || {};
  const el = S.root.querySelector('#stOrigin');
  if (o.app === 'markflow') {
    el.innerHTML = `MarkFlow ${o.format === 'markflow-md' ? 'Markdown' : 'HTML'} 파일에서 가져옴 · ${C.esc((o.importedAt || '').slice(0, 16).replace('T', ' '))}${o.fileName ? ' · ' + C.esc(o.fileName) : ''}${o.fileHash ? ' · 파일 검증값 ' + C.esc(o.fileHash.slice(0, 10)) : ''}${o.documentId ? ' · 문서 ID ' + C.esc(o.documentId) : ''}${o.version ? ' · ' + C.esc(o.version) + '번째 가져오기' : ''}${C.safeHref(o.url) ? ` · <a href="${C.esc(C.safeHref(o.url))}" target="_blank" rel="noopener noreferrer">원본 주소</a>` : ''}`;
  } else if (o.app === 'backup') el.textContent = '노트 파일에서 복원함 · ' + (o.importedAt || '').slice(0, 16).replace('T', ' ');
  else el.textContent = '기록보관실에서 직접 작성';
}
function renderHistory() {
  const el = S.root.querySelector('#stHistory');
  const hist = (S.base?.studyHistory || []).slice().reverse();
  if (!hist.length) { el.innerHTML = '<small class="st-muted">보관된 이전 판 없음 (30분 간격·가져오기·충돌 해결 때 최대 5개 보관)</small>'; return; }
  const reason = {edit: '수정', 'import-version': 'MarkFlow 새 버전 반영 전', 'conflict-keep-mine': '다른 기기 변경본(충돌 해결 전)', restore: '이전 판 되돌리기 전', backup: '파일 복원 전'};
  el.innerHTML = hist.map((h, i) => `<div class="st-hist"><span>${C.esc(new Date(h.at).toLocaleString('ko-KR', {hour12: false}))} · ${C.esc(reason[h.reason] || h.reason)} · ${C.esc(h.title)}</span><button type="button" class="st-mini" data-h="${i}">이 판 내용 불러오기</button></div>`).join('');
  el.querySelectorAll('[data-h]').forEach(b => b.onclick = () => {
    const h = hist[Number(b.dataset.h)];
    if (!confirm('이 판의 제목·핵심 정리·본문을 편집창에 불러올까요? 저장해야 반영되고, 지금 서버본은 이전 판으로 보관됩니다.')) return;
    S.root.querySelector('#stTitle').value = h.title;
    S.root.querySelector('#stOneLiner').value = h.oneLiner || '';
    S.editor.commands.setContent(h.contentDocJson ? C.parseDoc(h.contentDocJson) : C.textToDoc(h.body));
    for (const a of h.assets || []) if (!S.assets.some(x => x.id === a.id)) S.assets.push(a);
    S.reason = 'restore';
    changed();
  });
}

/* ── 저장 ── */
async function save() {
  if (!S || S.saving) return;
  writeDraft();
  if (S.uploads.size) { S.lastError = '이미지 보관이 끝난 뒤 저장할 수 있어요'; refreshStatus(); return; }
  let patch;
  const snap = snapshot();
  try {
    patch = C.buildStudyPatch({...snap.form, assets: S.assets, origin: S.origin}, snap.doc);
  } catch (e) {
    if (e.message === 'TITLE_REQUIRED') { S.lastError = '제목을 적어 주세요'; refreshStatus(); S.root.querySelector('#stTitle').focus(); return; }
    throw e;
  }
  S.saving = true; S.lastError = ''; refreshStatus();
  S.operationId = S.operationId || ('op_' + Date.now().toString(36) + Math.random().toString(36).slice(2, 8));
  const session = S;
  try {
    const res = await S.store.save({id: S.id, patch, expected: S.expected, reason: S.reason, relations: {add: S.relAdd, remove: S.relRemove}, operationId: S.operationId});
    if (S !== session) return;
    S.base = res.record; S.expected = C.studyFingerprint(res.record);
    S.relAdd = []; S.relRemove = []; S.reason = 'edit'; S.operationId = null;
    S.baseline = comparable(snapshot());
    S.lastSavedAt = Date.now(); S.lastDraftAt = 0;
    discardDraft(S.id);
    patch.stocks.forEach(s => S.bridge.addStockToMaster?.(s));
    S.root.querySelector('#stHeadTitle').textContent = '📚 공부노트 수정';
    renderRels(); renderHistory();
    const ext = C.docStats(snap.doc).imagesExternal;
    if (res.level === 'warn') S.bridge.toast('저장했어요 · 노트 크기 ' + kb(res.bytes) + ' — 1MB 한도에 가까워지고 있어요');
    else S.bridge.toast(ext ? '저장했어요 · 보관되지 않은 외부 이미지 ' + ext + '개가 있어요' : '공부노트를 저장했어요');
    S.bridge.onSaved?.(S.id);
    /* v7.28.3: 서버 저장이 실제로 성공했을 때만(로컬 초안 저장이 아니라) 자동으로 닫는다. 저장 중에 새로
       붙여넣은 사진이 아직 업로드 중이면(드문 경합) 닫지 않고 그대로 열어 둔다 — closeEditor()의 확인
       팝업 없이 조용히 유지. 상세보기 아래에서 열었다면 그 상세보기가, 목록에서 열었다면 목록이 이 편집창
       뒤에 그대로 있으므로 닫기만 하면 되돌아간 것과 같다(상세보기 내용 자체는 bridge.onSaved 쪽에서 새로고침). */
    if (!S.uploads.size) { S.saving = false; await closeEditor(); return; }
  } catch (e) {
    if (S !== session) return;
    if (e.message === 'CONFLICT') { S.lastError = '다른 기기에서 먼저 바뀜 — 비교 후 선택해 주세요'; S.operationId = null; conflictDialog(); }
    else if (e.message === 'SIZE_LIMIT') { S.lastError = '노트가 너무 커서 저장할 수 없어요(약 ' + kb(e.bytes) + ' / 한도 ' + kb(C.SIZE_BLOCK_BYTES) + ') — 내용을 나눠 주세요. 작성 내용은 이 기기에 임시 보관됨'; S.operationId = null; }
    else { S.lastError = '서버 저장 실패' + (navigator.onLine ? '' : '(연결 끊김)') + ' — 작성 내용은 이 기기에 임시 보관됨. 다시 [저장]을 눌러 주세요'; S.bridge.logBug?.('공부노트 저장 실패: ' + e.message); }
  } finally {
    if (S === session) { S.saving = false; refreshStatus(); }
  }
}

function textPreview(title, text) { return `<b>${C.esc(title || '(제목 없음)')}</b><pre class="st-cmp">${C.esc(String(text || '').slice(0, 4000))}</pre>`; }
async function conflictDialog() {
  const dlg = S.root.querySelector('#stDialog');
  let latest = null;
  try { latest = await S.store.read(S.id); } catch (e) { S.lastError = '최신본을 읽지 못했어요: ' + e.message; refreshStatus(); return; }
  const mine = snapshot();
  dlg.innerHTML = `<div class="st-dbox st-wide" role="dialog" aria-label="변경 충돌"><h3>다른 곳에서 이 노트가 바뀌었어요</h3>
    <p>조용히 덮어쓰지 않았습니다. 두 내용을 비교하고 고르세요. 내 작성 내용은 이 기기에 임시 보관돼 있어요.</p>
    <div class="st-cmpgrid"><div><h4>서버 최신본 ${latest ? '(' + C.esc(new Date(latest.updatedAt || 0).toLocaleString('ko-KR', {hour12: false})) + ')' : '(삭제됨)'}</h4>${latest ? textPreview(latest.title, latest.body) : '<p class="st-warn">서버에서 삭제된 노트입니다.</p>'}</div>
    <div><h4>내 작성 내용</h4>${textPreview(mine.form.title, C.docToPlainText(mine.doc))}</div></div>
    <div class="st-row">${latest ? '<button type="button" class="st-mini" data-c="theirs">최신본으로 다시 열기 (내 내용은 초안으로 보관)</button>' : ''}<button type="button" class="st-save" data-c="mine">${latest ? '내 내용으로 저장 (최신본은 이전 판으로 보관)' : '내 내용으로 다시 만들기'}</button><button type="button" class="st-mini" data-c="close">나중에</button></div></div>`;
  dlg.hidden = false;
  dlg.querySelector('[data-c=close]').onclick = () => { dlg.hidden = true; };
  dlg.querySelector('[data-c=mine]').onclick = () => {
    dlg.hidden = true;
    if (latest) { S.base = latest; S.expected = C.studyFingerprint(latest); S.reason = 'conflict-keep-mine'; }
    else { S.base = null; S.expected = null; }
    save();
  };
  const theirs = dlg.querySelector('[data-c=theirs]');
  if (theirs) theirs.onclick = () => {
    const keepKey = DRAFT_PREFIX + S.id + '.conflict.' + Date.now();
    lsSet(keepKey, {...mine, savedAt: Date.now(), note: '충돌로 보관한 내 작성 내용'});
    dlg.hidden = true;
    loadSession(latest, null, null);
    S.bridge.toast('최신본을 열었어요 · 내 작성 내용은 이 기기에 따로 보관했어요');
  };
}

/* ── 세션 ── */
function loadSession(base, draft, prefill) {
  const root = S.root;
  S.base = base || null;
  S.expected = base ? C.studyFingerprint(base) : null;
  S.assets = (base?.assets || []).slice();
  S.relAdd = []; S.relRemove = []; S.reason = 'edit'; S.origin = base?.origin || {app: 'records', format: C.CONTENT_FORMAT};
  S.lastSavedAt = 0; S.lastDraftAt = 0; S.lastError = '';
  fillForm(root, base ? formFromRecord(base) : {});
  S.editor.commands.setContent(base ? C.docForRecord(base) : C.emptyDoc(), {emitUpdate: false});
  S.editor.view.dispatch(S.editor.state.tr.setMeta('addToHistory', false).setMeta(foldKey, {clear: true}));
  S.baseline = comparable(snapshot());
  if (prefill) {
    if (prefill.form) fillForm(root, {...readForm(root), ...prefill.form});
    if (prefill.doc) S.editor.commands.setContent(prefill.doc);
    if (prefill.assets) for (const a of prefill.assets) if (!S.assets.some(x => x.id === a.id)) S.assets.push(a);
    if (prefill.origin) S.origin = prefill.origin;
    if (prefill.reason) S.reason = prefill.reason;
    // v7.28: "모아 정리하기"(records.html) 가 새 공부노트를 만들 때 출처 관계를 미리 채운다.
    // 실제 저장은 사용자가 직접 저장 버튼을 눌러야 일어난다(여기선 S.relAdd 에만 쌓아둔다 — 기존 저장 경로가 그대로 처리).
    if (prefill.relAdd && prefill.relAdd.length) S.relAdd = prefill.relAdd.slice();
  }
  if (draft) {
    fillForm(root, draft.form || {});
    S.editor.commands.setContent(C.parseDoc(draft.doc) || C.emptyDoc());
    S.assets = draft.assets || S.assets;
    S.relAdd = draft.relAdd || []; S.relRemove = draft.relRemove || [];
    S.origin = draft.origin || S.origin;
    S.reason = draft.reason || 'edit';
    S.lastDraftAt = draft.savedAt;
    if (base && draft.expected !== S.expected) { S.expected = C.studyFingerprint(base); S.reason = 'conflict-keep-mine'; }
  }
  root.querySelector('#stHeadTitle').textContent = base ? '📚 공부노트 수정' : '📚 새 공부노트';
  renderRels(); renderOrigin(); renderHistory(); renderEdToc(); updateToolbar(); updateContext();
  root.querySelector('#stStockList').innerHTML = (S.bridge.allStockNames?.() || []).map(n => `<option value="${C.esc(n)}">`).join('');
  refreshStatus();
}

function draftChoice(base, draft) {
  return new Promise(resolve => {
    const dlg = S.root.querySelector('#stDialog');
    const serverChanged = base && draft.expected !== C.studyFingerprint(base);
    dlg.innerHTML = `<div class="st-dbox st-wide" role="dialog" aria-label="임시 보관본"><h3>이 기기에 저장하지 않은 작성 내용이 있어요</h3>
      <p>${C.esc(new Date(draft.savedAt).toLocaleString('ko-KR', {hour12: false}))}에 이 기기에만 임시 보관된 내용입니다(다른 기기에는 없음).${serverChanged ? ' <b class="st-warn">그 뒤 서버의 노트가 다른 곳에서 바뀌었어요.</b>' : ''}</p>
      ${serverChanged ? `<div class="st-cmpgrid"><div><h4>서버 최신본</h4>${textPreview(base.title, base.body)}</div><div><h4>이 기기 초안</h4>${textPreview(draft.form?.title, C.docToPlainText(C.parseDoc(draft.doc) || C.emptyDoc()))}</div></div>` : ''}
      <div class="st-row"><button type="button" class="st-save" data-c="draft">초안으로 이어 쓰기${serverChanged ? ' (저장 시 최신본은 이전 판으로 보관)' : ''}</button><button type="button" class="st-mini" data-c="server">${base ? '서버본 열기' : '새로 쓰기'} (초안 삭제)</button></div></div>`;
    dlg.hidden = false;
    dlg.querySelector('[data-c=draft]').onclick = () => { dlg.hidden = true; resolve('draft'); };
    dlg.querySelector('[data-c=server]').onclick = () => { dlg.hidden = true; resolve('server'); };
  });
}

// 이 기기에 저장 안 된 새 노트가 있으면 이어 쓸지 고르게 한다(자동으로 섞지 않음)
function pickNewDraft(root, drafts) {
  return new Promise(resolve => {
    root.classList.add('on');
    const dlg = root.querySelector('#stDialog');
    dlg.innerHTML = `<div class="st-dbox" role="dialog" aria-label="작성 중이던 새 노트"><h3>이 기기에 저장하지 않은 새 노트가 있어요</h3><p class="st-hint">이 기기에만 임시 보관된 내용이에요(다른 기기에는 없음).</p>
      <div class="st-picklist">${drafts.map((d, i) => `<button type="button" class="st-pick" data-i="${i}"><b>${C.esc(d.form?.title || '(제목 없음)')}</b> <small class="st-muted">${C.esc(new Date(d.savedAt).toLocaleString('ko-KR', {hour12: false}))} · ${C.esc(C.docToPlainText(C.parseDoc(d.doc) || C.emptyDoc()).slice(0, 60))}</small></button>`).join('')}</div>
      <div class="st-row"><button type="button" class="st-save" data-new="1">새로 쓰기</button><small class="st-muted">새로 써도 위 초안은 지우지 않아요</small></div></div>`;
    dlg.hidden = false;
    dlg.querySelectorAll('[data-i]').forEach(b => b.onclick = () => { dlg.hidden = true; resolve(drafts[Number(b.dataset.i)].id); });
    dlg.querySelector('[data-new]').onclick = () => { dlg.hidden = true; resolve(null); };
  });
}

function bindShell(root) {
  if (root.dataset.bound) return;
  root.dataset.bound = '1';
  // 서식 버튼을 눌러도 본문 커서·선택이 그대로 남도록(버튼이 포커스를 가져가지 않게)
  // 터치에서도 선택이 풀리지 않게 pointerdown 단계에서 막는다(click 은 그대로 발생)
  for (const sel of ['#stToolbar', '#stCtx', '#stPop']) for (const type of ['pointerdown', 'mousedown']) root.querySelector(sel).addEventListener(type, ev => {
    if (!ev.target.closest('button')) return;
    if (S) S.toolDownAt = Date.now();
    if (!ev.target.closest('#stLinkOk,#stLinkRm')) ev.preventDefault();
  });
  root.querySelector('#stToolbar').addEventListener('click', ev => {
    const b = ev.target.closest('button'); if (!b || !S) return;
    if (b.dataset.pop) popover(b.dataset.pop, b); else if (b.dataset.cmd) exec(b.dataset.cmd);
  });
  root.querySelector('[data-cmd=block]').addEventListener('change', ev => {
    const v = ev.target.value, ch = S.editor.chain().focus();
    (v === 'p' ? ch.setParagraph() : ch.setHeading({level: Number(v)})).run();
  });
  root.querySelector('#stImgFile').addEventListener('change', ev => {
    const files = ev.target.files;
    if (S.replacePos !== undefined && S.replacePos !== null && files[0]) {
      const pos = S.replacePos; S.replacePos = null;
      const e = S.editor, node = e.state.doc.nodeAt(pos);
      if (node?.type.name === 'image') {
        const tid = tempId(), blobUrl = URL.createObjectURL(files[0]);
        e.view.dispatch(e.state.tr.setNodeMarkup(pos, null, {...node.attrs, src: blobUrl, status: 'uploading', tempId: tid, note: null}));
        runUpload(tid, async () => files[0], {name: files[0].name, blobUrl});
      }
    } else if (files.length) insertFiles(files);
    ev.target.value = '';
  });
  root.querySelector('#stSave').onclick = () => save();
  root.querySelector('#stClose').onclick = () => closeEditor();
  root.querySelector('#stFullBtn').onclick = ev => { const on = !root.classList.contains('is-full'); root.classList.toggle('is-full', on); if (S) S.userFull = on; ev.currentTarget.setAttribute('aria-pressed', String(on)); layout(); };
  root.querySelector('#stTocBtn').onclick = ev => { const nav = root.querySelector('#stEdToc'); nav.hidden = !nav.hidden; ev.currentTarget.setAttribute('aria-pressed', String(!nav.hidden)); renderEdToc(); };
  root.querySelector('#stAddRef').onclick = () => pickRecord('ref');
  root.querySelector('#stAddHyp').onclick = () => pickRecord('hyp');
  root.querySelector('#stCheckAdd').onclick = () => { addCheckRow(root); changed(); };
  const addStock = () => { const inp = root.querySelector('#stStockInput'); const v = inp.value.trim(); if (v && !S.stocks.includes(v)) { S.stocks.push(v); renderStocks(root); changed(); } inp.value = ''; };
  root.querySelector('#stStockAdd').onclick = addStock;
  root.querySelector('#stStockInput').addEventListener('keydown', ev => { if (ev.key === 'Enter') { ev.preventDefault(); addStock(); } });
  root.querySelector('.st-scroll').addEventListener('input', ev => { if (!ev.target.closest('#stEditor')) changed(); });
  root.querySelector('.st-scroll').addEventListener('change', ev => { if (!ev.target.closest('#stEditor')) changed(); });
  root.addEventListener('keydown', ev => {
    if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === 's') { ev.preventDefault(); save(); }
    if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === 'k' && ev.target.closest('#stEditor')) { ev.preventDefault(); popover('link', root.querySelector('[data-pop=link]')); }
    if (ev.key === 'Escape') { const pop = root.querySelector('#stPop'); if (!pop.hidden) { pop.hidden = true; ev.stopPropagation(); } }
  });
  document.addEventListener('mousedown', ev => { const pop = root.querySelector('#stPop'); if (!pop.hidden && !pop.contains(ev.target) && !ev.target.closest('[data-pop]')) pop.hidden = true; });
  window.addEventListener('online', refreshStatus);
  window.addEventListener('offline', refreshStatus);
  window.addEventListener('pagehide', () => { if (S) writeDraft(); });
  window.addEventListener('beforeunload', ev => { if (S && isDirty()) { writeDraft(); ev.preventDefault(); ev.returnValue = ''; } });
  const vv = window.visualViewport;
  vv?.addEventListener('resize', layout);
  vv?.addEventListener('scroll', layout);
  window.addEventListener('resize', layout);
  window.addEventListener('orientationchange', () => setTimeout(layout, 250));
  layout();
}

// 휴대폰: 편집창을 지금 보이는 영역(키보드 제외)에 맞추고, 서식 도구줄은 아래(키보드 바로 위)에 붙인다.
// 회전·키보드 열림/닫힘마다 다시 맞춘다.
const MOBILE_Q = '(max-width: 760px), (max-height: 520px)';
function layout() {
  const root = document.getElementById('studyModal');
  if (!root) return;
  const vv = window.visualViewport;
  const mobile = window.matchMedia(MOBILE_Q).matches;
  root.style.setProperty('--st-vh', (vv ? vv.height : window.innerHeight) + 'px');
  if (!root.classList.contains('on')) return;
  if (!(S && S.userFull !== undefined)) root.classList.toggle('is-full', mobile);
  if (mobile && vv) { root.style.top = vv.offsetTop + 'px'; root.style.height = vv.height + 'px'; root.style.bottom = 'auto'; }
  else { root.style.top = ''; root.style.height = ''; root.style.bottom = ''; }
  if (mobile !== root.classList.contains('is-docked')) {
    root.classList.toggle('is-docked', mobile);
    const dock = root.querySelector('#stDock'), wrap = root.querySelector('.st-edwrap');
    for (const id of ['#stPop', '#stCtx', '#stToolbar']) {
      const el = root.querySelector(id);
      if (mobile) dock.append(el); else wrap.before(el);
    }
    const pop = root.querySelector('#stPop'); pop.style.left = ''; pop.style.top = '';
  }
}

export async function openStudyEditor({bridge, store, id = null, prefill = null, newDraftId = null, offerDrafts = false}) {
  if (S) { await closeEditor(); if (S) return null; }
  const root = shell(bridge);
  bindShell(root);
  let base = null;
  if (id) {
    try { base = await store.read(id); } catch (e) { bridge.toast('노트를 불러오지 못했어요 — 연결을 확인해 주세요'); bridge.logBug?.('공부노트 읽기 실패: ' + e.message); return null; }
    if (!base) { bridge.toast('삭제됐거나 찾을 수 없는 노트예요'); return null; }
    if (!C.isStudy(base)) { bridge.toast('공부노트가 아닌 기록이에요'); return null; }
  }
  if (!id && !prefill && !newDraftId && offerDrafts) {
    const drafts = listNewDrafts().sort((a, b) => b.savedAt - a.savedAt);
    if (drafts.length) newDraftId = await pickNewDraft(root, drafts);
  }
  const noteId = id || newDraftId || store.newId();
  S = {bridge, store, root, id: noteId, stocks: [], assets: [], relAdd: [], relRemove: [], uploads: new Map(), pendingPaste: [], notices: [], saving: false};
  root.classList.add('on');
  root.classList.toggle('is-full', window.matchMedia(MOBILE_Q).matches);
  /* v7.28.3: 이 DOM(#studyModal)은 열고 닫을 때마다 재사용되므로, 지난번 편집창의 스크롤 위치가 그대로
     남아있다 — 상세보기 아래쪽에서 "수정"을 눌러도 항상 제목·저장 버튼이 보이는 맨 위에서 시작하도록
     여기서 한 번 리셋한다(배경 페이지가 아니라 이 모달 자신의 스크롤 영역만). layout()이나 onUpdate 등
     편집 중 반복 실행되는 곳에는 넣지 않는다 — 여기(연 시점)에서만 해야 작성 중 스크롤이 안 튄다. */
  const scrollBox = root.querySelector('#stScroll');
  if (scrollBox) scrollBox.scrollTop = 0;
  layout();
  document.documentElement.classList.add('st-open');
  S.editor = new Editor({
    element: root.querySelector('#stEditor'),
    extensions: extensions(),
    content: C.emptyDoc(),
    editorProps: {
      attributes: {class: 'st-prose', 'aria-label': '공부노트 본문', role: 'textbox', 'aria-multiline': 'true'},
      /* v7.28.2: 안내는 "사진·본문 누락"과 "링크 제거"만 남긴다 — 색상 매핑, 제목 단계 조정, MarkFlow 표기
         변환 같은 사소한 서식 변경은 정상 동작이라 안내하지 않는다(누락 감지 자체는 그대로 report.missing 에 쌓임).
         report.converted 는 MarkFlow 가져오기 미리보기(study-import.mjs)가 계속 쓰므로 그대로 채운다 — 여기서
         "안내로 띄울지"만 바꿨다. */
      transformPastedHTML: html => {
        const report = {converted: [], missing: [], linksRemoved: []};
        const out = cleanHTML(html, {report, onImage: raw => pasteImageRule(raw)});
        report.missing.forEach(m => S.notices.push(m));
        if (report.linksRemoved.length) S.notices.push('링크 연결이 제거됨: ' + [...new Set(report.linksRemoved)].filter(Boolean).slice(0, 5).join(', ') || '허용되지 않은 주소');
        return out;
      },
      handlePaste: (view, event) => {
        const dt = event.clipboardData;
        const html = dt?.getData('text/html');
        const files = dt?.files?.length ? [...dt.files] : [];
        if (!html && files.some(f => /^image\//.test(f.type))) { insertFiles(files); return true; }
        setTimeout(() => {
          if (!S) return;
          convertMarkflowText(S.editor); // 형광펜·동영상 표기 변환 — 사소한 서식 변경이라 안내하지 않음
          flushPendingPaste();
          showNotices();
        }, 0);
        return false;
      },
      handleDrop: (view, event) => {
        const files = event.dataTransfer?.files;
        if (files?.length && [...files].some(f => /^image\//.test(f.type))) {
          const pos = view.posAtCoords({left: event.clientX, top: event.clientY})?.pos;
          event.preventDefault();
          insertFiles(files, pos);
          return true;
        }
        return false;
      }
    },
    onUpdate: () => { changed(); renderEdToc(); },
    onSelectionUpdate: () => { rememberRange(); updateToolbar(); updateContext(); },
    onTransaction: () => { rememberRange(); updateToolbar(); }
  });
  const draft = lsGet(DRAFT_PREFIX + noteId);
  let useDraft = null;
  if (draft && !prefill && !id && newDraftId) useDraft = draft; // 새 노트 초안 목록에서 이미 고름
  else if (draft && !prefill) {
    const pick = await draftChoice(base, draft);
    if (pick === 'draft') useDraft = draft; else discardDraft(noteId);
  }
  loadSession(base, useDraft, prefill);
  if (prefill) changed();
  /* 편집기 로딩·자동 포커스가 끝난 뒤에도 맨 위를 유지한다. TipTap 의 focus('start')는 기본적으로 포커스된
     지점을 보이게 스크롤을 옮기므로 scrollIntoView:false 로 애초에 막고(v7.28.3에서 실측 — 이걸 안 주면
     #stScroll 이 본문 중간까지 다시 밀렸다), 그래도 브라우저가 다음 페인트에서 스크롤을 조정할 수 있어
     rAF 로 한 번 더 맨 위로 되돌린다(둘 다 여는 시점 한정 — 작성 중에는 안 건드림). */
  setTimeout(() => {
    if (base || prefill) S?.editor?.commands.focus('start', {scrollIntoView: false});
    else root.querySelector('#stTitle').focus({preventScroll: true});
    if (scrollBox) scrollBox.scrollTop = 0;
    requestAnimationFrame(() => { if (scrollBox) scrollBox.scrollTop = 0; });
  }, 30);
  return noteId;
}

export async function closeEditor() {
  if (!S) return;
  if (S.saving) { S.bridge.toast('저장 중이에요 — 잠시 후 닫아 주세요'); return; }
  const dirty = isDirty();
  if (dirty) writeDraft();
  if (S.uploads.size && !confirm('이미지 보관이 아직 끝나지 않았어요. 닫으면 그 이미지는 초안에서 누락으로 표시됩니다. 닫을까요?')) return;
  clearTimeout(draftTimer);
  const {root, bridge} = S;
  S.editor.destroy();
  S = null;
  root.classList.remove('on', 'is-full');
  root.style.top = ''; root.style.height = ''; root.style.bottom = '';
  root.querySelector('#stDialog').hidden = true;
  root.querySelector('#stPop').hidden = true;
  const notice = root.querySelector('#stPasteNotice'); if (notice) { notice.removeAttribute('open'); notice.innerHTML = ''; }
  document.documentElement.classList.remove('st-open');
  if (dirty) bridge.toast('저장하지 않은 내용은 이 기기에만 임시 보관했어요(다른 기기에는 보이지 않음)');
  bridge.onClosed?.();
}
export const isOpen = () => !!S;
