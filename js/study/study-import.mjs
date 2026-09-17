// MarkFlow 문서 가져오기(HTML·Markdown) + 공부노트 파일 내보내기/복원.
// 가져오기는 편집창에 채워 여는 것까지만 한다 — 사용자가 [저장]을 눌러야 보관실에 들어간다(자동 저장·원본 삭제 없음).
import {cleanHTML, htmlToDoc} from './study-editor-kit.mjs';
import {marked} from './vendor/study-editor-vendor.mjs';
import * as C from './study-core.mjs';

const $ = (r, s) => r.querySelector(s);
let IMP = null;

function layer() {
  let root = document.getElementById('studyImport');
  if (root) return root;
  root = document.createElement('div');
  root.id = 'studyImport';
  root.className = 'study-layer st-importlayer';
  root.setAttribute('role', 'dialog');
  root.setAttribute('aria-modal', 'true');
  root.setAttribute('aria-labelledby', 'stImpTitle');
  root.innerHTML = `<div class="st-shell st-impshell">
    <header class="st-head"><b id="stImpTitle">📥 MarkFlow 문서 가져오기</b><span class="st-sp"></span><button type="button" class="st-hbtn st-x" data-imp="close" aria-label="닫기">✕</button></header>
    <div class="st-scroll"><div class="st-impbody" id="stImpBody"></div></div></div>`;
  document.body.append(root);
  $(root, '[data-imp=close]').onclick = () => closeImport();
  root.addEventListener('keydown', ev => { if (ev.key === 'Escape') closeImport(); });
  return root;
}
function closeImport() { const r = document.getElementById('studyImport'); if (r) r.classList.remove('on'); IMP = null; }

function step1(root) {
  $(root, '#stImpBody').innerHTML = `
    <p>MarkFlow의 <b>내보내기 → HTML (.html)</b> 또는 <b>Markdown (.md)</b> 파일을 고르세요. 편집창에 채워서 열어 드리고, <b>저장을 눌러야</b> 보관실에 들어갑니다.</p>
    <ul class="st-hint">
      <li>HTML 파일이 제목·굵게·목록·표·링크·이미지·형광펜을 가장 잘 보존합니다.</li>
      <li>Markdown 파일에는 글자색·밑줄 같은 정보가 없어 <b>완전 보존되지 않습니다</b>.</li>
      <li>MarkFlow 원본은 이 화면에서 지우거나 바꾸지 않습니다. 가져와 저장한 것을 확인한 뒤에 정리하세요.</li>
    </ul>
    <label class="st-f"><span>파일</span><input type="file" id="stImpFile" accept=".html,.htm,.md,.markdown,.txt,text/html,text/markdown,text/plain"></label>
    <div class="st-props">
      <label class="st-f st-grow"><span>MarkFlow 문서 ID <small>선택 — 알면 같은 문서 재가져오기를 정확히 찾아요</small></span><input type="text" id="stImpDocId" maxlength="80"></label>
      <label class="st-f st-grow"><span>원본 주소 <small>선택</small></span><input type="url" id="stImpUrl" placeholder="https://"></label>
    </div>
    <p class="st-err" id="stImpErr" role="alert"></p>`;
  $(root, '#stImpFile').onchange = ev => { const f = ev.target.files[0]; if (f) analyze(root, f).catch(e => { $(root, '#stImpErr').textContent = '파일을 읽지 못했어요: ' + e.message; }); };
}

function sourceCounts(html) {
  const d = new DOMParser().parseFromString(html, 'text/html');
  const q = s => d.body.querySelectorAll(s).length;
  return {headings: q('h1,h2,h3,h4,h5,h6'), tables: q('table'), images: q('img'), links: q('a[href]'), lists: q('ul:not([data-type=taskList]),ol'), quotes: q('blockquote'), highlights: q('span.mf-hl,mark')};
}

async function analyze(root, file) {
  const text = await file.text();
  const name = file.name || '';
  const isMd = /\.(md|markdown|txt)$/i.test(name) || !/<(html|body|p|h[1-6]|div|ul|table)[\s>]/i.test(text);
  const report = {converted: [], missing: []};
  const fileHash = await C.sha256Hex(text);
  let html = isMd ? marked.parse(C.preprocessMarkflowMarkdown(text, report), {gfm: true, breaks: false}) : text;
  const src = sourceCounts(html);
  const clean = cleanHTML(html, {report, onImage: raw => {
    if (/^data:image\/(png|jpe?g|gif|webp|avif|bmp);base64,/i.test(raw)) return {'data-status': 'pending', src: raw};
    if (/^https?:\/\//i.test(raw)) return {'data-status': 'pending', 'data-original-src': C.safeHref(raw), src: C.safeImageUrl(raw) || raw};
    report.missing.push('이미지 주소를 쓸 수 없음(' + (/^[a-z][a-z0-9+.-]*:/i.test(raw) ? String(raw).split(':')[0] : '주소 없음·잘못된 주소') + ')');
    return {'data-status': 'missing', 'data-note': '가져올 수 없는 이미지 주소', src: null};
  }});
  const doc = htmlToDoc(clean);
  const stats = C.docStats(doc);
  const firstBlock = () => [...new DOMParser().parseFromString(text, 'text/html').body.querySelectorAll('h1,h2,h3,h4,h5,h6,p,li,td')].map(n => n.textContent.trim()).find(Boolean) || '';
  const title = C.markflowTitle(isMd ? text : firstBlock()) || name.replace(/\.[^.]+$/, '');
  const docId = $(root, '#stImpDocId').value.trim();
  const url = C.safeHref($(root, '#stImpUrl').value.trim());
  const cands = C.reimportCandidates(IMP.bridge.records(), {fileHash, documentId: docId});
  IMP.parsed = {doc, fileHash, name, isMd, title, docId, url, report, stats, src};
  preview(root, cands);
}

function preview(root, cands) {
  const p = IMP.parsed, s = p.stats, src = p.src;
  const lost = [];
  if (s.headings < src.headings) lost.push('제목 ' + (src.headings - s.headings) + '개');
  if (s.tables < src.tables) lost.push('표 ' + (src.tables - s.tables) + '개');
  if (s.images < src.images) lost.push('이미지 ' + (src.images - s.images) + '개');
  const kept = [['제목', s.headings], ['문단', s.paragraphs], ['목록', s.lists], ['체크 목록', s.tasks], ['표', s.tables], ['인용', s.quotes], ['링크', s.links], ['굵게', s.bold], ['기울임', s.italic], ['밑줄', s.underline], ['취소선', s.strike], ['글자색', s.colors], ['강조색', s.highlights], ['이미지(보관 예정)', s.images - s.imagesMissing - s.imagesExternal]].filter(x => x[1]).map(x => x[0] + ' ' + x[1]).join(' · ');
  const count = arr => { const m = new Map(); arr.forEach(x => m.set(x, (m.get(x) || 0) + 1)); return [...m].map(([k, n]) => C.esc(k) + (n > 1 ? ' ×' + n : '')); };
  const missing = [...p.report.missing, ...(s.imagesMissing ? ['이미지 ' + s.imagesMissing + '개(주소 없음)'] : []), ...lost.map(x => '원본보다 적게 변환: ' + x)];
  $(root, '#stImpBody').innerHTML = `
    <div class="st-props"><label class="st-f st-grow"><span>제목</span><input type="text" id="stImpTitleIn" value="${C.esc(p.title)}" maxlength="300"></label></div>
    <p class="st-hint">${C.esc(p.name)} · ${p.isMd ? 'Markdown' : 'HTML'} · 파일 검증값 ${C.esc(p.fileHash.slice(0, 10))}${p.docId ? ' · 문서 ID ' + C.esc(p.docId) : ' · 문서 ID 없음(파일에서 가져옴으로 기록)'}</p>
    ${p.isMd ? '<p class="st-warn">Markdown 파일이라 글자색·밑줄·이미지 크기 일부 서식은 원래 담겨 있지 않아 보존되지 않을 수 있어요.</p>' : ''}
    <div class="st-impreport">
      <div><h4>✅ 보존된 요소</h4><p>${C.esc(kept) || '없음'}</p></div>
      <div><h4>🔁 변환된 요소</h4>${p.report.converted.length ? '<ul>' + count(p.report.converted).map(x => '<li>' + x + '</li>').join('') + '</ul>' : '<p>없음</p>'}</div>
      <div><h4>⚠ 가져오지 못한 요소</h4>${missing.length ? '<ul>' + count(missing).map(x => '<li>' + x + '</li>').join('') + '</ul>' : '<p>없음</p>'}<small class="st-muted">외부 주소 이미지는 가져올 때 보관을 시도하고, 원본 사이트가 막으면 ‘보관 안 됨’으로 표시해요.</small></div>
    </div>
    ${cands.length ? `<div class="st-dup"><h4>이미 가져온 적 있는 문서예요</h4>${cands.map((c, i) => `<label class="st-radio"><input type="radio" name="stImpMode" value="ver:${C.esc(c.record.id)}" ${i === 0 ? 'checked' : ''}> <b>${C.esc(c.record.title)}</b>의 새 버전으로 반영 <small class="st-muted">(${c.sameFile ? '같은 파일 내용' : ''}${c.sameFile && c.sameDocument ? ' · ' : ''}${c.sameDocument ? '같은 문서 ID' : ''} · 지금 내용은 이전 판으로 보관)</small></label>`).join('')}<label class="st-radio"><input type="radio" name="stImpMode" value="new"> 별도 노트로 만들기</label>${cands.some(c => c.sameFile) ? '<p class="st-warn">같은 파일 내용을 이미 가져왔어요. 필요 없으면 닫으세요.</p>' : ''}</div>` : ''}
    <div class="st-row"><button type="button" class="st-save" id="stImpGo">편집창에서 열기</button><button type="button" class="st-mini" id="stImpBack">다른 파일 고르기</button><span id="stImpProg" class="st-muted" role="status" aria-live="polite"></span></div>
    <h4>미리보기</h4><article class="st-prose st-read st-imppreview">${C.renderDocHTML(p.doc, {idPrefix: 'ip'})}</article>`;
  $(root, '#stImpBack').onclick = () => step1(root);
  $(root, '#stImpGo').onclick = () => go(root).catch(e => { $(root, '#stImpProg').textContent = '실패: ' + e.message; $(root, '#stImpGo').disabled = false; });
}

async function storeImages(doc, store, onProgress) {
  const jobs = [];
  const assets = [];
  C.walk(doc, n => { if (n.type === 'image' && n.attrs?.status === 'pending') jobs.push(n.attrs); });
  let done = 0, stored = 0, external = 0, failed = 0;
  for (const a of jobs) {
    const src = a.src || '';
    const isData = src.startsWith('data:');
    try {
      const blob = isData ? await (await fetch(src)).blob() : await fetch(src, {mode: 'cors', credentials: 'omit'}).then(r => { if (!r.ok) throw Error('HTTP ' + r.status); return r.blob(); });
      const asset = await store.uploadImage(blob, {name: a.alt || 'MarkFlow 이미지'});
      assets.push(asset);
      Object.assign(a, {src: asset.url, assetId: asset.id, status: 'stored', note: null});
      stored++;
    } catch (e) {
      if (isData) { Object.assign(a, {src: null, status: 'missing', note: '보관 실패: ' + (e.message === 'IMAGE_TOO_LARGE' ? '8MB 초과' : e.message)}); failed++; }
      else { Object.assign(a, {originalSrc: C.safeHref(a.originalSrc || src) || null, src: null, status: 'external', note: '원본 사이트가 복사를 허용하지 않음'}); external++; }
    }
    onProgress(++done, jobs.length);
  }
  return {assets, stored, external, failed, total: jobs.length};
}

async function go(root) {
  const p = IMP.parsed;
  $(root, '#stImpGo').disabled = true;
  const mode = root.querySelector('input[name=stImpMode]:checked')?.value || 'new';
  const doc = JSON.parse(JSON.stringify(p.doc));
  const prog = $(root, '#stImpProg');
  const res = await storeImages(doc, IMP.store, (d, t) => { prog.textContent = '이미지 보관 중 ' + d + '/' + t; });
  const targetId = mode.startsWith('ver:') ? mode.slice(4) : null;
  const prev = targetId ? IMP.bridge.records().find(r => r.id === targetId) : null;
  const origin = {app: 'markflow', format: p.isMd ? 'markflow-md' : 'markflow-html', documentId: p.docId || '', url: p.url || '', fileName: p.name, fileHash: p.fileHash, importedAt: new Date().toISOString(), version: (prev?.origin?.version || 0) + 1};
  const title = $(root, '#stImpTitleIn').value.trim() || p.title || '가져온 노트';
  const {bridge, openEditor} = IMP;
  closeImport();
  if (res.external || res.failed) bridge.toast('이미지 ' + res.total + '개 중 보관 ' + res.stored + ' · 외부(보관 안 됨) ' + res.external + ' · 실패 ' + res.failed);
  await openEditor(targetId, {prefill: {doc, assets: res.assets, origin, reason: targetId ? 'import-version' : 'edit', form: targetId ? {title} : {title, studyType: 'source_study', sourceName: 'MarkFlow', sourceUrl: p.url || ''}}});
  bridge.toast('가져온 내용을 편집창에 열었어요 — [저장]을 눌러야 보관실에 들어갑니다');
}

export function openImport({bridge, store, openEditor}) {
  const root = layer();
  IMP = {bridge, store, openEditor};
  $(root, '#stImpTitle').textContent = '📥 MarkFlow 문서 가져오기';
  step1(root);
  root.classList.add('on');
  setTimeout(() => $(root, '#stImpFile')?.focus(), 30);
}

/* ── 공부노트 파일(백업) ── */
function download(name, text) {
  const blob = new Blob([text], {type: 'application/json'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = name;
  document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 4000);
}
// CORS 없이도 확인되도록 img 로드로 판별(8초 제한)
function imageReachable(url) {
  if (!C.safeImageUrl(url)) return Promise.resolve(false);
  return new Promise(res => { const i = new Image(); const t = setTimeout(() => res(false), 8000); i.onload = () => { clearTimeout(t); res(i.naturalWidth > 0); }; i.onerror = () => { clearTimeout(t); res(false); }; i.src = url; });
}
const blobToDataUrl = b => new Promise((res, rej) => { const fr = new FileReader(); fr.onload = () => res(fr.result); fr.onerror = rej; fr.readAsDataURL(b); });

export async function exportNote({bridge, store, id}) {
  const r = await store.read(id);
  if (!r || !C.isStudy(r)) throw new Error('NOT_STUDY');
  const images = {}, notIncluded = [];
  for (const a of r.assets || []) {
    try { const b = await fetch(a.url, {mode: 'cors'}).then(x => { if (!x.ok) throw Error('HTTP ' + x.status); return x.blob(); }); images[a.id] = await blobToDataUrl(b); } catch { notIncluded.push(a.id); }
  }
  const backup = C.buildBackup(r, images);
  if (notIncluded.length) backup.imagesNotIncluded = notIncluded;
  const safe = String(r.title || 'note').replace(/[\\/:*?"<>|]+/g, '_').slice(0, 40);
  download('공부노트-' + safe + '-' + new Date().toISOString().slice(0, 10) + '.json', JSON.stringify(backup, null, 1));
  bridge.toast(notIncluded.length ? '내보냈어요 · 이미지 ' + notIncluded.length + '개는 파일에 넣지 못해 저장 경로만 기록했어요' : '노트 파일로 내보냈어요(서식 문서·본문·이미지 포함)');
}

export function openRestore({bridge, store, openEditor}) {
  const root = layer();
  IMP = {bridge, store, openEditor};
  $(root, '#stImpTitle').textContent = '♻ 공부노트 파일 복원';
  $(root, '#stImpBody').innerHTML = `<p>‘노트 파일로 내보내기’로 받은 .json 파일을 고르세요. 편집창에 채워 열고, 저장해야 반영됩니다.</p><label class="st-f"><span>파일</span><input type="file" id="stResFile" accept=".json,application/json"></label><p class="st-err" id="stResErr" role="alert"></p><div id="stResOut"></div>`;
  root.classList.add('on');
  $(root, '#stResFile').onchange = async ev => {
    const f = ev.target.files[0]; if (!f) return;
    let b;
    try { b = C.parseBackup(await f.text()); } catch { $(root, '#stResErr').textContent = '공부노트 파일 형식이 아니에요'; return; }
    const exists = bridge.records().find(r => r.id === b.recordId);
    const doc = C.parseDoc(b.record.contentDocJson) || C.textToDoc(b.record.body);
    $(root, '#stResOut').innerHTML = `<p><b>${C.esc(b.record.title)}</b> · 내보낸 시각 ${C.esc(b.exportedAt.slice(0, 16).replace('T', ' '))} · 이미지 파일 ${Object.keys(b.images || {}).length}개 포함${(b.imagesNotIncluded || []).length ? ' · 경로만 ' + b.imagesNotIncluded.length + '개' : ''}</p>
      ${exists ? `<label class="st-radio"><input type="radio" name="stResMode" value="same" checked> 기존 노트 “${C.esc(exists.title)}”에 새 판으로 복원 (지금 내용은 이전 판으로 보관)</label>` : ''}
      <label class="st-radio"><input type="radio" name="stResMode" value="new" ${exists ? '' : 'checked'}> 새 노트로 복원</label>
      <div class="st-row"><button type="button" class="st-save" id="stResGo">편집창에서 열기</button><span id="stResProg" class="st-muted" role="status"></span></div>
      <article class="st-prose st-read st-imppreview">${C.renderDocHTML(doc, {assets: Object.fromEntries((b.record.assets || []).map(a => [a.id, a])), idPrefix: 'rs'})}</article>`;
    $(root, '#stResGo').onclick = async () => {
      $(root, '#stResGo').disabled = true;
      const same = root.querySelector('input[name=stResMode]:checked')?.value === 'same';
      const assets = [];
      let reuploaded = 0, linked = 0, lost = 0;
      const prog = $(root, '#stResProg');
      for (const a of b.record.assets || []) {
        if (b.images?.[a.id]) {
          try { const blob = await (await fetch(b.images[a.id])).blob(); const na = await store.uploadImage(blob, {name: a.name}); C.walk(doc, n => { if (n.type === 'image' && n.attrs?.assetId === a.id) Object.assign(n.attrs, {assetId: na.id, src: na.url, status: 'stored'}); }); assets.push(na); reuploaded++; continue; } catch { /* 아래에서 원본 주소 확인 */ }
        }
        // 파일에 이미지가 없으면 원본 주소가 지금 열리는지 확인 — 열리지 않으면 ‘보관됨’으로 두지 않고 누락 표시
        if (prog) prog.textContent = '원본 이미지 확인 중…';
        if (await imageReachable(a.url)) { assets.push(a); linked++; continue; }
        C.walk(doc, n => { if (n.type === 'image' && n.attrs?.assetId === a.id) Object.assign(n.attrs, {status: 'missing', src: null, note: '백업 파일에 이미지가 없고 원본 이미지에도 접근할 수 없음'}); });
        lost++;
      }
      const rec = b.record;
      closeImport();
      await openEditor(same ? exists.id : null, {prefill: {doc, assets, reason: same ? 'backup' : 'edit', origin: {...(rec.origin || {}), restoredFrom: 'backup', restoredAt: new Date().toISOString()}, form: {...rec, sourceName: rec.source?.name || '', sourceUrl: rec.source?.url || ''}}});
      bridge.toast('복원 내용을 편집창에 열었어요 — [저장]을 눌러야 반영됩니다' + ((b.record.assets || []).length ? ` · 이미지: 파일에서 다시 보관 ${reuploaded} · 원본 주소 연결 ${linked} · 복원 불가 ${lost}` : ''));
    };
  };
}
