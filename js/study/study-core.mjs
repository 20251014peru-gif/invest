// 공부노트 핵심 규칙 — DOM 없이 동작(노드 테스트 대상). 저장 계약·안전한 읽기 렌더·일반 텍스트 투영·충돌/크기 검사.
// 본문 기준본: contentDocJson(TipTap/ProseMirror JSON 문자열). body 는 검색·미리보기·구버전 화면용 일반 텍스트 투영.
// JSON 을 문자열로 두는 이유: Firestore 는 맵/배열 중첩 깊이 20 제한이 있어 중첩 목록·표가 저장 거부될 수 있다.

export const CONTENT_FORMAT = 'tiptap-json';
export const CONTENT_VERSION = 1;
export const STUDY_KIND = 'study';

export const STUDY_TYPES = {concept: '개념 정리', topic_analysis: '주제 분석', source_study: '자료 공부', comparison: '비교 정리'};
export const STUDY_STATUS = {learning: '공부 중', organized: '정리 완료', needs_review: '재검토 필요'};

// 제한 팔레트 — 강조색은 MarkFlow 형광펜 5색과 같은 값(가져오기 시 그대로 대응)
export const TEXT_COLORS = [
  {id: 'red', label: '빨강', value: '#c0392b'},
  {id: 'orange', label: '주황', value: '#b8610a'},
  {id: 'green', label: '초록', value: '#2f7d5c'},
  {id: 'blue', label: '파랑', value: '#1f5fa8'},
  {id: 'purple', label: '보라', value: '#6b46a8'},
  {id: 'gray', label: '회색', value: '#6b7280'}
];
export const HIGHLIGHT_COLORS = [
  {id: 'yellow', label: '노랑 강조', value: '#fff2a8'},
  {id: 'green', label: '초록 강조', value: '#bff0cb'},
  {id: 'blue', label: '파랑 강조', value: '#bfe0ff'},
  {id: 'pink', label: '분홍 강조', value: '#ffc9e2'},
  {id: 'orange', label: '주황 강조', value: '#ffdcaf'}
];
export const MARKFLOW_HL = {1: '#fff2a8', 2: '#bff0cb', 3: '#bfe0ff', 4: '#ffc9e2', 5: '#ffdcaf'};

// Firestore 문서 한도 1 MiB. 필드명·색인 여유를 두고 경고/차단 기준을 잡는다.
export const SIZE_WARN_BYTES = 600 * 1024;
export const SIZE_BLOCK_BYTES = 900 * 1024;
export const HISTORY_MAX = 5;
export const HISTORY_INTERVAL_MS = 30 * 60 * 1000;

export const RELATION_TYPES = {
  references: {fwd: '참고 자료', rev: '이 자료를 참고한 노트'},
  supports: {fwd: '뒷받침', rev: '이 기록이 뒷받침받음'},
  contradicts: {fwd: '반박/상충', rev: '이 기록과 상충'},
  same_event: {fwd: '같은 사건', rev: '같은 사건'},
  same_topic: {fwd: '같은 주제', rev: '같은 주제'},
  related: {fwd: '관련', rev: '관련'}
};

export const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));

export function safeHref(value) {
  const s = String(value ?? '').trim();
  if (!s) return '';
  try {
    const u = new URL(s);
    return ['http:', 'https:', 'mailto:'].includes(u.protocol) ? u.href : '';
  } catch { return ''; }
}
// 보관 이미지는 https(Firebase Storage)만. 로컬 시험 서버(localhost)만 http 허용.
export function safeImageUrl(value) {
  try { const u = new URL(String(value ?? '')); return u.protocol === 'https:' || (u.protocol === 'http:' && ['localhost', '127.0.0.1'].includes(u.hostname)) ? u.href : ''; } catch { return ''; }
}

export function isStudy(r) { return !!r && (r.kind === STUDY_KIND || r.contentFormat === CONTENT_FORMAT); }

/* ── 색상 ── */
function parseColor(input) {
  const s = String(input ?? '').trim().toLowerCase();
  let m = s.match(/^#([0-9a-f]{3})$/);
  if (m) return m[1].split('').map(h => parseInt(h + h, 16));
  m = s.match(/^#([0-9a-f]{6})$/);
  if (m) return [0, 2, 4].map(i => parseInt(m[1].slice(i, i + 2), 16));
  m = s.match(/^rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})(?:\s*,\s*([\d.]+))?\s*\)$/);
  if (m) { if (m[4] !== undefined && Number(m[4]) < 0.2) return null; return [m[1], m[2], m[3]].map(Number); }
  const named = {red: [255, 0, 0], blue: [0, 0, 255], green: [0, 128, 0], orange: [255, 165, 0], purple: [128, 0, 128], gray: [128, 128, 128], grey: [128, 128, 128], yellow: [255, 255, 0], pink: [255, 192, 203], black: [0, 0, 0], white: [255, 255, 255]};
  return named[s] || null;
}
const dist = (a, b) => Math.sqrt(a.reduce((t, v, i) => t + (v - b[i]) ** 2, 0));
// 붙여넣기·가져오기 색을 팔레트로 맞춘다. 본문 기본색(검정 계열)·흰 배경 계열은 색 없음(null).
export function nearestPalette(input, kind) {
  const rgb = parseColor(input);
  if (!rgb) return null;
  const palette = kind === 'highlight' ? HIGHLIGHT_COLORS : TEXT_COLORS;
  const neutral = kind === 'highlight' ? [[255, 255, 255], [250, 250, 245]] : [[0, 0, 0], [47, 47, 44], [35, 38, 43], [51, 51, 51]];
  const exact = palette.find(p => parseColor(p.value).every((v, i) => v === rgb[i]));
  if (exact) return exact.value;
  const neutralD = Math.min(...neutral.map(n => dist(n, rgb)));
  let best = null, bestD = Infinity;
  for (const p of palette) { const d = dist(parseColor(p.value), rgb); if (d < bestD) { bestD = d; best = p; } }
  if (neutralD <= bestD || neutralD < 60) return null;
  return best.value;
}
export const allowedTextColor = v => TEXT_COLORS.some(p => p.value === String(v || '').toLowerCase());
export const allowedHighlight = v => HIGHLIGHT_COLORS.some(p => p.value === String(v || '').toLowerCase());

/* ── 문서 파싱 ── */
export function emptyDoc() { return {type: 'doc', content: [{type: 'paragraph'}]}; }
export function parseDoc(json) {
  if (!json) return null;
  try {
    const d = typeof json === 'string' ? JSON.parse(json) : json;
    return d && d.type === 'doc' && Array.isArray(d.content) ? d : null;
  } catch { return null; }
}
// 구버전 일반 텍스트 본문 → 문단 문서(원본 body 는 건드리지 않음)
export function textToDoc(text) {
  const lines = String(text ?? '').replace(/\r\n?/g, '\n').split('\n');
  const content = lines.map(l => l ? {type: 'paragraph', content: [{type: 'text', text: l}]} : {type: 'paragraph'});
  return {type: 'doc', content: content.length ? content : [{type: 'paragraph'}]};
}
export function docForRecord(r) {
  const d = r && r.contentFormat === CONTENT_FORMAT ? parseDoc(r.contentDocJson) : null;
  return d || textToDoc(r ? (r.body || r.summary || '') : '');
}

export function walk(node, fn, parent = null) {
  if (!node || typeof node !== 'object') return;
  if (fn(node, parent) === false) return;
  for (const c of node.content || []) walk(c, fn, node);
}
const textOf = node => {
  if (!node) return '';
  if (node.type === 'text') return node.text || '';
  if (node.type === 'hardBreak') return '\n';
  return (node.content || []).map(textOf).join('');
};

/* ── 일반 텍스트 투영(body) ── */
export function docToPlainText(doc) {
  const out = [];
  const block = (node, prefix = '') => {
    switch (node.type) {
      case 'paragraph': case 'heading': out.push(prefix + textOf(node)); break;
      case 'codeBlock': out.push(textOf(node)); break;
      case 'horizontalRule': out.push('---'); break;
      case 'image': out.push(prefix + '[이미지' + (node.attrs?.alt ? ': ' + node.attrs.alt : '') + ']'); break;
      case 'blockquote': for (const c of node.content || []) block(c, prefix + '> '); break;
      case 'bulletList': for (const li of node.content || []) item(li, prefix, '- '); break;
      case 'orderedList': { let n = Number(node.attrs?.start) || 1; for (const li of node.content || []) item(li, prefix, (n++) + '. '); break; }
      case 'taskList': for (const li of node.content || []) item(li, prefix, (li.attrs?.checked ? '[x] ' : '[ ] ')); break;
      case 'table': for (const row of node.content || []) out.push(prefix + (row.content || []).map(cell => (cell.content || []).map(textOf).join(' ').replace(/\s+/g, ' ').trim()).join(' | ')); break;
      default: if (node.content) for (const c of node.content) block(c, prefix); else if (node.text) out.push(prefix + node.text);
    }
  };
  const item = (li, prefix, marker) => {
    const kids = li.content || [];
    kids.forEach((c, i) => {
      if (i === 0 && (c.type === 'paragraph' || c.type === 'heading')) out.push(prefix + marker + textOf(c));
      else block(c, prefix + '  ');
    });
    if (!kids.length) out.push(prefix + marker);
  };
  for (const c of (doc?.content || [])) block(c);
  while (out.length && !out[out.length - 1].trim()) out.pop();
  return out.join('\n');
}

export function headingsOf(doc) {
  const hs = [];
  (doc?.content || []).forEach((n, index) => { if (n.type === 'heading') hs.push({level: Math.min(3, Math.max(1, Number(n.attrs?.level) || 1)), text: textOf(n).trim() || '(제목 없음)', index}); });
  return hs;
}

export function imagesOf(doc) {
  const list = [];
  walk(doc, n => { if (n.type === 'image') list.push(n.attrs || {}); });
  return list;
}

export function docStats(doc) {
  const s = {headings: 0, paragraphs: 0, lists: 0, tasks: 0, tables: 0, images: 0, imagesStored: 0, imagesExternal: 0, imagesMissing: 0, links: 0, bold: 0, italic: 0, underline: 0, strike: 0, colors: 0, highlights: 0, quotes: 0, rules: 0, code: 0};
  walk(doc, n => {
    if (n.type === 'heading') s.headings++;
    else if (n.type === 'paragraph') s.paragraphs++;
    else if (n.type === 'bulletList' || n.type === 'orderedList') s.lists++;
    else if (n.type === 'taskList') s.tasks++;
    else if (n.type === 'table') s.tables++;
    else if (n.type === 'blockquote') s.quotes++;
    else if (n.type === 'horizontalRule') s.rules++;
    else if (n.type === 'codeBlock') s.code++;
    else if (n.type === 'image') {
      s.images++;
      const st = n.attrs?.status;
      if (st === 'external') s.imagesExternal++; else if (st === 'missing' || st === 'uploading') s.imagesMissing++; else s.imagesStored++;
    }
    for (const m of n.marks || []) {
      if (m.type === 'link') s.links++;
      else if (m.type === 'bold') s.bold++;
      else if (m.type === 'italic') s.italic++;
      else if (m.type === 'underline') s.underline++;
      else if (m.type === 'strike') s.strike++;
      else if (m.type === 'highlight') s.highlights++;
      else if (m.type === 'textStyle' && (m.attrs?.color || m.attrs?.backgroundColor)) s.colors++;
    }
  });
  return s;
}

/* ── 안전한 읽기 렌더 — 허용 노드·마크만, 모든 문자열 escape, URL·색 허용목록 ── */
function markOpen(m) {
  const a = m.attrs || {};
  switch (m.type) {
    case 'bold': return ['<strong>', '</strong>'];
    case 'italic': return ['<em>', '</em>'];
    case 'underline': return ['<u>', '</u>'];
    case 'strike': return ['<s>', '</s>'];
    case 'code': return ['<code>', '</code>'];
    case 'link': { const h = safeHref(a.href); return h ? ['<a href="' + esc(h) + '" target="_blank" rel="noopener noreferrer nofollow">', '</a>'] : ['', '']; }
    case 'highlight': { const c = allowedHighlight(a.color) ? a.color.toLowerCase() : HIGHLIGHT_COLORS[0].value; return ['<mark style="background-color:' + c + '">', '</mark>']; }
    case 'textStyle': {
      const st = [];
      if (allowedTextColor(a.color)) st.push('color:' + a.color.toLowerCase());
      if (allowedHighlight(a.backgroundColor)) st.push('background-color:' + a.backgroundColor.toLowerCase());
      return st.length ? ['<span style="' + st.join(';') + '">', '</span>'] : ['', ''];
    }
    default: return ['', ''];
  }
}
function inlineHTML(n) {
  if (n.type === 'hardBreak') return '<br>';
  if (n.type !== 'text') return esc(textOf(n));
  let html = esc(n.text || '');
  const marks = (n.marks || []).slice().reverse();
  for (const m of marks) { const [o, c] = markOpen(m); html = o + html + c; }
  return html;
}
const inlines = n => (n.content || []).map(inlineHTML).join('');
const intAttr = (v, max) => { const x = parseInt(v, 10); return Number.isFinite(x) && x > 1 && x <= max ? x : 0; };
const WIDTHS = ['25%', '50%', '75%', '100%'];

export function imageHTML(a, assets = {}) {
  const alt = String(a.alt || '');
  const asset = a.assetId ? assets[a.assetId] : null;
  const src = safeImageUrl(asset?.url || (a.status === 'stored' || !a.status ? a.src : ''));
  const width = WIDTHS.includes(a.width) ? a.width : '';
  const align = ['left', 'center', 'right'].includes(a.align) ? a.align : 'center';
  if (a.status === 'external') {
    const h = safeHref(a.originalSrc || a.src);
    return '<figure class="st-img st-img-missing" data-align="' + align + '"><div class="st-img-note">⚠ 보관되지 않은 외부 이미지' + (alt ? ' — ' + esc(alt) : '') + '<br><small>원본 사이트에서만 보입니다. 파일로 다시 첨부하면 보관됩니다.</small>' + (h ? '<br><a href="' + esc(h) + '" target="_blank" rel="noopener noreferrer nofollow">원본 이미지 주소 열기</a>' : '') + '</div></figure>';
  }
  if (a.status === 'pending') return '<figure class="st-img st-img-missing" data-align="' + align + '"><div class="st-img-note">⏳ 가져올 때 보관할 이미지' + (alt ? ' — ' + esc(alt) : '') + '</div></figure>';
  if (!src || a.status === 'missing' || a.status === 'uploading') {
    return '<figure class="st-img st-img-missing" data-align="' + align + '"><div class="st-img-note">⚠ 가져오지 못한 이미지' + (alt ? ' — ' + esc(alt) : '') + (a.note ? '<br><small>' + esc(a.note) + '</small>' : '') + '</div></figure>';
  }
  return '<figure class="st-img" data-align="' + align + '"><img src="' + esc(src) + '" alt="' + esc(alt) + '" loading="lazy"' + (width ? ' style="width:' + width + '"' : '') + '>' + (alt ? '<figcaption>' + esc(alt) + '</figcaption>' : '') + '</figure>';
}

function blockHTML(n, ctx) {
  const a = n.attrs || {};
  switch (n.type) {
    case 'paragraph': return '<p>' + (inlines(n) || '<br>') + '</p>';
    case 'heading': { const l = Math.min(3, Math.max(1, Number(a.level) || 1)); return '<h' + l + '>' + inlines(n) + '</h' + l + '>'; }
    case 'blockquote': return '<blockquote>' + blocks(n.content, ctx) + '</blockquote>';
    case 'bulletList': return '<ul>' + (n.content || []).map(li => '<li>' + blocks(li.content, ctx) + '</li>').join('') + '</ul>';
    case 'orderedList': { const s = parseInt(a.start, 10); return '<ol' + (Number.isFinite(s) && s !== 1 ? ' start="' + s + '"' : '') + '>' + (n.content || []).map(li => '<li>' + blocks(li.content, ctx) + '</li>').join('') + '</ol>'; }
    case 'taskList': return '<ul class="st-tasks">' + (n.content || []).map(li => '<li><input type="checkbox" disabled' + (li.attrs?.checked ? ' checked' : '') + ' aria-label="' + (li.attrs?.checked ? '완료' : '미완료') + '"><div>' + blocks(li.content, ctx) + '</div></li>').join('') + '</ul>';
    case 'horizontalRule': return '<hr>';
    case 'codeBlock': return '<pre><code>' + esc(textOf(n)) + '</code></pre>';
    case 'image': return imageHTML(a, ctx.assets);
    case 'table': return '<div class="st-tablewrap"><table>' + (n.content || []).map(row => '<tr>' + (row.content || []).map(cell => {
      const tag = cell.type === 'tableHeader' ? 'th' : 'td';
      const cs = intAttr(cell.attrs?.colspan, 50), rs = intAttr(cell.attrs?.rowspan, 500);
      return '<' + tag + (cs ? ' colspan="' + cs + '"' : '') + (rs ? ' rowspan="' + rs + '"' : '') + '>' + blocks(cell.content, ctx) + '</' + tag + '>';
    }).join('') + '</tr>').join('') + '</table></div>';
    default: return n.content ? blocks(n.content, ctx) : (n.text ? '<p>' + esc(n.text) + '</p>' : '');
  }
}
const blocks = (list, ctx) => (list || []).map(n => blockHTML(n, ctx)).join('');

// 제목(1~3단계) 기준으로 접기 섹션(details)을 만든다. 접혀도 내용은 DOM 에 그대로 있다.
export function renderDocHTML(doc, {assets = {}, idPrefix = 'sec'} = {}) {
  const ctx = {assets};
  const top = doc?.content || [];
  let html = '', stack = [], hIndex = 0;
  const close = level => { while (stack.length && stack[stack.length - 1] >= level) { html += '</div></details>'; stack.pop(); } };
  for (const n of top) {
    if (n.type === 'heading') {
      const l = Math.min(3, Math.max(1, Number(n.attrs?.level) || 1));
      close(l);
      const id = idPrefix + '-' + (hIndex++);
      html += '<details class="st-sec st-l' + l + '" open><summary><h' + l + ' id="' + esc(id) + '">' + (inlines(n) || '(제목 없음)') + '</h' + l + '></summary><div class="st-secbody">';
      stack.push(l);
    } else html += blockHTML(n, ctx);
  }
  close(0);
  return html;
}
export function tocHTML(doc, idPrefix = 'sec') {
  const hs = headingsOf(doc);
  if (hs.length < 2) return '';
  return '<nav class="st-toc" aria-label="목차"><b>목차</b>' + hs.map((h, i) => '<a href="#' + idPrefix + '-' + i + '" data-toc="' + idPrefix + '-' + i + '" class="st-toc-l' + h.level + '">' + esc(h.text) + '</a>').join('') + '</nav>';
}

/* ── 저장 계약 ── */
export const STUDY_OWNED = ['kind', 'title', 'oneLiner', 'studyType', 'studyStatus', 'topics', 'industries', 'themes', 'stocks', 'asOfDate', 'reviewAt', 'checks', 'userJudgment', 'aiInterpretation', 'verifyState', 'source', 'link', 'channel', 'contentFormat', 'contentVersion', 'contentDocJson', 'body', 'assets', 'origin'];

const cleanList = v => { const seen = new Set(), out = []; for (const x of Array.isArray(v) ? v : String(v ?? '').split(',')) { const t = String(x ?? '').replace(/\s+/g, ' ').trim(); if (t && !seen.has(t.toLowerCase())) { seen.add(t.toLowerCase()); out.push(t); } } return out; };
const dateOrEmpty = v => /^\d{4}-\d{2}-\d{2}$/.test(String(v || '')) ? String(v) : '';
export {cleanList};

// Firestore 는 undefined 를 거부 — 문서 트리에서 제거
export function stripUndefined(v) {
  if (Array.isArray(v)) return v.map(stripUndefined);
  if (v && typeof v === 'object') { const o = {}; for (const [k, x] of Object.entries(v)) if (x !== undefined) o[k] = stripUndefined(x); return o; }
  return v;
}

// 저장본에는 data:/blob: 등 임시 이미지 주소를 절대 남기지 않는다(base64 대량 저장 방지). 보관 안 된 이미지는 상태로 표시.
export function persistableDoc(doc) {
  const d = stripUndefined(JSON.parse(JSON.stringify(doc || emptyDoc())));
  walk(d, n => {
    if (n.type !== 'image') return;
    const a = n.attrs = n.attrs || {};
    delete a.tempId;
    if (a.status === 'external') { a.originalSrc = safeHref(a.originalSrc || a.src) || null; a.src = null; return; }
    if (a.status === 'uploading' || a.status === 'pending' || !safeImageUrl(a.src)) {
      if (a.status !== 'missing') a.note = a.note || '보관되지 않은 이미지';
      a.status = 'missing'; a.src = null;
    }
  });
  return d;
}

export function buildStudyPatch(form, doc) {
  if (!String(form.title || '').trim()) throw new Error('TITLE_REQUIRED');
  const d = persistableDoc(doc);
  const used = new Set(imagesOf(d).map(i => i.assetId).filter(Boolean));
  const assets = (form.assets || []).filter(a => a && a.id && used.has(a.id)).map(a => ({id: String(a.id), path: String(a.path || ''), url: safeImageUrl(a.url), name: String(a.name || ''), size: Number(a.size) || 0, type: String(a.type || ''), addedAt: Number(a.addedAt) || 0}));
  const sourceUrl = safeHref(form.sourceUrl);
  return {
    kind: STUDY_KIND,
    title: String(form.title).trim().slice(0, 300),
    oneLiner: String(form.oneLiner || '').trim().slice(0, 600),
    studyType: STUDY_TYPES[form.studyType] ? form.studyType : 'concept',
    studyStatus: STUDY_STATUS[form.studyStatus] ? form.studyStatus : 'learning',
    topics: cleanList(form.topics), industries: cleanList(form.industries), themes: cleanList(form.themes), stocks: cleanList(form.stocks),
    asOfDate: dateOrEmpty(form.asOfDate), reviewAt: dateOrEmpty(form.reviewAt),
    checks: (form.checks || []).filter(c => c && (c.date || c.what || c.action)).map(c => ({date: dateOrEmpty(c.date), what: String(c.what || ''), action: String(c.action || '')})),
    userJudgment: String(form.userJudgment || '').trim(),
    aiInterpretation: String(form.aiInterpretation || '').trim(),
    verifyState: String(form.verifyState || ''),
    source: {name: String(form.sourceName || '').trim(), url: sourceUrl},
    link: sourceUrl,
    channel: String(form.sourceName || '').trim(),
    contentFormat: CONTENT_FORMAT, contentVersion: CONTENT_VERSION,
    contentDocJson: JSON.stringify(d),
    body: docToPlainText(d),
    assets,
    origin: form.origin && typeof form.origin === 'object' ? stripUndefined(form.origin) : {app: 'records', format: CONTENT_FORMAT}
  };
}

export function studyFingerprint(r) {
  if (!r) return null;
  return JSON.stringify([r.studyRevision || 0, r.title ?? null, r.oneLiner ?? null, r.body ?? null, r.contentDocJson ?? null, r.userJudgment ?? null, r.kind ?? null]);
}
export const utf8Bytes = s => { let n = 0; for (const ch of String(s)) { const c = ch.codePointAt(0); n += c < 0x80 ? 1 : c < 0x800 ? 2 : c < 0x10000 ? 3 : 4; } return n; };
export function estimateRecordBytes(r) {
  // 필드명+값 UTF-8 길이 + 여유. Firestore 실제 계산보다 약간 크게 잡는다.
  return utf8Bytes(JSON.stringify(r || {})) + 1024;
}
export function sizeLevel(bytes) { return bytes >= SIZE_BLOCK_BYTES ? 'block' : bytes >= SIZE_WARN_BYTES ? 'warn' : 'ok'; }

// 관계 변경은 현재(서버) 목록에 편집 중 추가/삭제한 것만 반영 — 다른 곳에서 붙인 연결을 덮어쓰지 않는다.
export function mergeRelations(current, {add = [], remove = []} = {}, now = Date.now()) {
  const key = x => x.targetId + '|' + (x.type || 'related');
  const rm = new Set(remove.map(key));
  const out = (Array.isArray(current) ? current : []).filter(x => x && !rm.has(key(x)));
  const have = new Set(out.map(key));
  add.forEach((x, i) => { if (x && x.targetId && !have.has(key(x))) { out.push({relationId: 'rel_' + now + '_' + i, targetId: String(x.targetId), type: RELATION_TYPES[x.type] ? x.type : 'related', note: '', createdAt: now}); have.add(key(x)); } });
  return out;
}

// 저장 커밋 계산(트랜잭션 안에서 사용). 충돌이면 CONFLICT, 크기 초과면 SIZE_LIMIT.
export function commitStudy(current, patch, expected, {now = Date.now(), reason = 'edit', relations = null, date = ''} = {}) {
  if (current && studyFingerprint(current) !== expected) throw new Error('CONFLICT');
  if (!current && expected) throw new Error('CONFLICT');
  let history = Array.isArray(current?.studyHistory) ? current.studyHistory.slice() : [];
  if (current) {
    const changed = current.contentDocJson !== patch.contentDocJson || current.title !== patch.title || current.oneLiner !== patch.oneLiner || current.body !== patch.body;
    const last = history.length ? Number(history[history.length - 1].at) || 0 : 0;
    const forced = reason !== 'edit';
    const hadContent = current.contentDocJson || current.body;
    if (changed && hadContent && (forced || now - last >= HISTORY_INTERVAL_MS)) {
      history.push({revision: current.studyRevision || 0, at: now, reason, title: current.title || '', oneLiner: current.oneLiner || '', body: current.body || '', contentFormat: current.contentFormat || '', contentDocJson: current.contentDocJson || '', assets: current.assets || []});
    }
  }
  while (history.length > HISTORY_MAX) history.shift();
  const result = {...patch, studyRevision: (current?.studyRevision || 0) + 1, updatedAt: now, schemaVer: current?.schemaVer || 2, studyHistory: history};
  if (!current) { result.createdAt = now; result.date = date || new Date(now + 9 * 3600000).toISOString().slice(0, 10); }
  if (relations) result.relations = mergeRelations(current?.relations, relations, now);
  let bytes = estimateRecordBytes({...(current || {}), ...result});
  while (bytes >= SIZE_BLOCK_BYTES && result.studyHistory.length) { result.studyHistory = result.studyHistory.slice(1); bytes = estimateRecordBytes({...(current || {}), ...result}); }
  if (bytes >= SIZE_BLOCK_BYTES) { const e = new Error('SIZE_LIMIT'); e.bytes = bytes; throw e; }
  return {result, bytes, level: sizeLevel(bytes)};
}

/* ── 연결(양방향) ── */
export function relationView(records, id) {
  const byId = new Map((records || []).map(r => [r.id, r]));
  const self = byId.get(id);
  const fwd = (self?.relations || []).filter(Boolean).map(rl => ({rel: rl, target: byId.get(rl.targetId) || null, targetId: rl.targetId, type: rl.type || 'related', dir: 'fwd'}));
  const rev = [];
  for (const r of records || []) {
    if (r.id === id) continue;
    for (const rl of r.relations || []) if (rl && rl.targetId === id) rev.push({rel: rl, target: r, targetId: r.id, type: rl.type || 'related', dir: 'rev'});
  }
  const isIdea = x => x.target && x.target.kind === 'idea';
  return {
    references: fwd.filter(x => x.type === 'references' || !isIdea(x)),
    hypotheses: fwd.filter(x => isIdea(x) && x.type !== 'references').concat(rev.filter(isIdea)),
    backlinks: rev.filter(x => !isIdea(x)),
    all: fwd.concat(rev)
  };
}

/* ── MarkFlow 표기 ── */
export const MF_HL_RE = /⟦([1-5])([^⟦⟧]*)⟧/g;
export function parseMarkflowImageAlt(alt) {
  const s = String(alt || '');
  const code = s.match(/⟪([^⟫]*)⟫/);
  const out = {alt: s.replace(/\s*⟪[^⟫]*⟫/g, '').trim(), width: null, rotation: 0, height: null};
  if (code) {
    const w = code[1].match(/w(\d+)/), h = code[1].match(/h(\d+)/), r = code[1].match(/r(\d+)/);
    if (w) { const p = Number(w[1]); out.width = p <= 37 ? '25%' : p <= 62 ? '50%' : p <= 87 ? '75%' : '100%'; }
    if (h) out.height = Number(h[1]);
    if (r) out.rotation = Number(r[1]) % 360;
  }
  return out;
}
export function decodeMarkflowVideo(b64) {
  try {
    const bin = typeof atob === 'function' ? atob(b64) : Buffer.from(b64, 'base64').toString('binary');
    const bytes = Uint8Array.from(bin, c => c.charCodeAt(0));
    return safeHref(new TextDecoder().decode(bytes));
  } catch { return ''; }
}
export function markflowTitle(text) {
  for (const line of String(text || '').split(/\r?\n/)) {
    const t = line.replace(/^#{1,6}\s+/, '').replace(/[*_~`]/g, '').replace(MF_HL_RE, '$2').trim();
    if (t) return t.slice(0, 200);
  }
  return '';
}
// MarkFlow Markdown 전처리: 형광펜·동영상 표기를 HTML 로 바꾼다(이후 marked + 허용목록 정리).
export function preprocessMarkflowMarkdown(md, report) {
  let s = String(md || '').replace(/\r\n?/g, '\n');
  s = s.replace(/^⟦vid ([^⟧]+)⟧$/gm, (_, enc) => { const u = decodeMarkflowVideo(enc); report?.converted.push('동영상 → 링크' + (u ? '' : '(주소 해독 실패)')); return u ? '[▶ 동영상](' + u + ')' : '(동영상 주소를 읽지 못함)'; });
  s = s.replace(/^⟦vidfile:([A-Za-z0-9]+)⟧$/gm, () => { report?.missing.push('기기에만 저장된 동영상(가져올 수 없음)'); return '(MarkFlow 기기 저장 동영상 — 가져오지 못함)'; });
  s = s.replace(MF_HL_RE, (_, n, t) => '<mark data-mf-hl="' + n + '">' + t.replace(/</g, '&lt;') + '</mark>');
  return s;
}

export async function sha256Hex(text) {
  const data = new TextEncoder().encode(String(text));
  const h = await globalThis.crypto.subtle.digest('SHA-256', data);
  return [...new Uint8Array(h)].map(b => b.toString(16).padStart(2, '0')).join('');
}

export function reimportCandidates(records, {fileHash = '', documentId = ''} = {}) {
  return (records || []).filter(r => isStudy(r) && r.origin && r.origin.app === 'markflow' && ((fileHash && r.origin.fileHash === fileHash) || (documentId && r.origin.documentId === documentId)))
    .map(r => ({record: r, sameFile: !!fileHash && r.origin.fileHash === fileHash, sameDocument: !!documentId && r.origin.documentId === documentId}));
}

/* ── 목록용 ── */
export function studyNeedsReview(r, today) {
  return isStudy(r) && (r.studyStatus === 'needs_review' || (!!r.reviewAt && r.reviewAt <= today));
}

/* ── 백업 파일 ── */
export const BACKUP_FORMAT = 'records-study-backup/1';
export function buildBackup(record, images = {}, now = Date.now()) {
  const {id, ...fields} = record;
  return {format: BACKUP_FORMAT, exportedAt: new Date(now).toISOString(), recordId: id, record: fields, images};
}
export function parseBackup(json) {
  const b = typeof json === 'string' ? JSON.parse(json) : json;
  if (!b || b.format !== BACKUP_FORMAT || !b.record || !isStudy(b.record)) throw new Error('BACKUP_FORMAT');
  if (b.record.contentDocJson && !parseDoc(b.record.contentDocJson)) throw new Error('BACKUP_DOC');
  return b;
}
