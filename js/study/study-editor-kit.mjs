// 편집기 구성 — TipTap 확장 묶음, 붙여넣기·가져오기 HTML 허용목록 정리, 제목 섹션 접기 플러그인.
import {Editor, Extension, StarterKit, Table, TableRow, TableHeader, TableCell, Image, TextStyle, Color, Highlight, TaskList, TaskItem, Placeholder, Plugin, PluginKey, Decoration, DecorationSet} from './vendor/study-editor-vendor.mjs';
import {nearestPalette, safeHref, parseMarkflowImageAlt, MARKFLOW_HL, MF_HL_RE, decodeMarkflowVideo, HIGHLIGHT_COLORS} from './study-core.mjs';

/* ── 이미지 노드: 보관 첨부(assetId)·외부/누락 상태를 문서에 남긴다 ── */
const StudyImage = Image.extend({
  draggable: true,
  // 기본 Image 는 img[src] 만 읽어 주소 없는(누락) 이미지·data 주소 이미지를 조용히 버린다 → 모든 img 를 읽고 상태로 구분
  parseHTML() { return [{tag: 'img'}]; },
  addAttributes() {
    const data = (name, def = null) => ({default: def, parseHTML: el => el.getAttribute('data-' + name) || def, renderHTML: v => (v[camel(name)] ? {['data-' + name]: v[camel(name)]} : {})});
    return {
      ...this.parent?.(),
      assetId: data('asset-id'), width: data('width'), align: data('align'), status: data('status', 'stored'),
      originalSrc: data('original-src'), note: data('note'), tempId: data('temp-id')
    };
  },
  addNodeView() {
    return ({node}) => {
      const fig = document.createElement('figure');
      const paint = n => {
        const a = n.attrs;
        fig.className = 'st-img st-edimg';
        fig.dataset.align = a.align || 'center';
        fig.textContent = '';
        const ok = a.src && (a.status === 'stored' || a.status === 'uploading' || a.status === 'pending');
        if (ok) {
          const img = document.createElement('img');
          img.src = a.src; img.alt = a.alt || '';
          if (a.width) img.style.width = a.width;
          fig.append(img);
          if (a.status === 'uploading') { const s = document.createElement('div'); s.className = 'st-img-note'; s.textContent = '⏳ 이미지 보관 중…'; fig.append(s); }
        } else {
          const d = document.createElement('div');
          d.className = 'st-img-note';
          d.textContent = a.status === 'external' ? '⚠ 보관되지 않은 외부 이미지 — 선택 후 [파일로 교체]로 보관할 수 있어요' : '⚠ 가져오지 못한 이미지' + (a.note ? ' — ' + a.note : '') + ' · 선택 후 [파일로 교체]';
          fig.classList.add('st-img-missing');
          fig.append(d);
        }
        if (a.alt) { const c = document.createElement('figcaption'); c.textContent = a.alt; fig.append(c); }
      };
      paint(node);
      return {dom: fig, update: n => { if (n.type.name !== 'image') return false; paint(n); return true; }, selectNode: () => fig.classList.add('is-selected'), deselectNode: () => fig.classList.remove('is-selected')};
    };
  }
}).configure({inline: false, allowBase64: false});
function camel(s) { return s.replace(/-([a-z])/g, (_, c) => c.toUpperCase()); }

/* ── 제목 섹션 접기: 문서는 그대로 두고 화면 표시만 숨긴다(저장 내용 손실 없음) ── */
export const foldKey = new PluginKey('studyFold');
function foldRanges(doc, folded) {
  const tops = [];
  doc.forEach((node, offset) => tops.push({node, pos: offset}));
  const ranges = [];
  for (const p of folded) {
    const i = tops.findIndex(t => t.pos === p);
    if (i < 0 || tops[i].node.type.name !== 'heading') continue;
    const level = tops[i].node.attrs.level;
    let j = i + 1;
    while (j < tops.length && !(tops[j].node.type.name === 'heading' && tops[j].node.attrs.level <= level)) j++;
    if (j > i + 1) ranges.push({head: p, from: tops[i + 1].pos, to: tops[j - 1].pos + tops[j - 1].node.nodeSize, items: tops.slice(i + 1, j)});
    else ranges.push({head: p, from: 0, to: 0, items: []});
  }
  return ranges;
}
export const SectionFold = Extension.create({
  name: 'sectionFold',
  addProseMirrorPlugins() {
    return [new Plugin({
      key: foldKey,
      state: {
        init: () => [],
        apply(tr, value, _old, state) {
          let folded = value.map(p => tr.mapping.map(p)).filter(p => { const n = state.doc.nodeAt(p); return n && n.type.name === 'heading'; });
          const meta = tr.getMeta(foldKey);
          if (meta?.toggle !== undefined) folded = folded.includes(meta.toggle) ? folded.filter(p => p !== meta.toggle) : folded.concat(meta.toggle);
          if (meta?.clear) folded = [];
          // 커서가 숨긴 구간으로 들어가면(찾기·방향키) 자동으로 펼친다
          const sel = state.selection.from;
          for (const r of foldRanges(state.doc, folded)) if (r.to > r.from && sel >= r.from && sel <= r.to) folded = folded.filter(p => p !== r.head);
          return [...new Set(folded)];
        }
      },
      props: {
        decorations(state) {
          const folded = foldKey.getState(state) || [];
          const decos = [];
          state.doc.forEach((node, pos) => {
            if (node.type.name !== 'heading') return;
            const isF = folded.includes(pos);
            decos.push(Decoration.widget(pos + 1, view => {
              const b = document.createElement('button');
              b.type = 'button'; b.className = 'st-foldbtn'; b.contentEditable = 'false';
              b.textContent = isF ? '▸' : '▾';
              b.setAttribute('aria-label', isF ? '섹션 펼치기' : '섹션 접기');
              b.setAttribute('aria-expanded', String(!isF));
              b.addEventListener('mousedown', e => { e.preventDefault(); view.dispatch(view.state.tr.setMeta(foldKey, {toggle: pos})); });
              return b;
            }, {side: -1, key: 'fold-' + pos + '-' + isF, ignoreSelection: true}));
            if (isF) decos.push(Decoration.node(pos, pos + node.nodeSize, {class: 'st-is-folded'}));
          });
          for (const r of foldRanges(state.doc, folded)) for (const it of r.items) decos.push(Decoration.node(it.pos, it.pos + it.node.nodeSize, {class: 'st-hidden-by-fold'}));
          return DecorationSet.create(state.doc, decos);
        }
      }
    })];
  }
});

// 브라우저는 style.color 를 rgb() 로 돌려준다 → 저장 전에 항상 팔레트 hex 로 맞춘다
const PaletteColor = Color.extend({
  addGlobalAttributes() {
    return [{types: ['textStyle'], attributes: {color: {default: null, parseHTML: el => nearestPalette(el.style.color, 'text'), renderHTML: a => (a.color ? {style: 'color:' + a.color} : {})}}}];
  }
});
const PaletteHighlight = Highlight.extend({
  addAttributes() {
    return {color: {default: null, parseHTML: el => nearestPalette(el.getAttribute('data-color') || el.style.backgroundColor, 'highlight') || HIGHLIGHT_COLORS[0].value, renderHTML: a => (a.color ? {'data-color': a.color, style: 'background-color:' + a.color} : {})}};
  }
});

export function extensions({placeholder = '여기에 공부한 내용을 자유롭게 정리하세요…'} = {}) {
  return [
    StarterKit.configure({
      heading: {levels: [1, 2, 3]},
      codeBlock: {},
      link: {openOnClick: false, autolink: true, protocols: ['http', 'https', 'mailto'], isAllowedUri: url => !!safeHref(url), HTMLAttributes: {rel: 'noopener noreferrer nofollow', target: '_blank'}}
    }),
    TextStyle, PaletteColor,
    PaletteHighlight.configure({multicolor: true}),
    Table.configure({resizable: false}), TableRow, TableHeader, TableCell,
    TaskList, TaskItem.configure({nested: true}),
    StudyImage,
    Placeholder.configure({placeholder}),
    SectionFold
  ];
}

/* ── HTML 허용목록 정리(붙여넣기·가져오기 공통) ──
   DOMParser 문서는 스크립트가 실행되지 않는 비활성 문서다. 여기서 한 번 더 걸러낸 뒤 편집기 스키마(허용 노드)로만 읽는다. */
const DROP = 'script,style,noscript,iframe,frame,frameset,object,embed,applet,form,button,select,textarea,link,meta,base,svg,math,template,canvas,audio,source,track,head,title,.mf-hlmark,.mf-figcap,.mf-video,.mf-imgact,.ProseMirror-widget';
const KEEP_ATTR = {a: ['href', 'title'], img: ['src', 'alt', 'title', 'width', 'data-asset-id', 'data-width', 'data-align', 'data-status', 'data-original-src', 'data-note', 'data-temp-id'], ol: ['start'], td: ['colspan', 'rowspan'], th: ['colspan', 'rowspan'], li: ['data-type', 'data-checked'], ul: ['data-type'], mark: ['data-color'], span: [], input: ['type', 'checked'], code: [], pre: []};

export function cleanHTML(html, {report, onImage} = {}) {
  const doc = new DOMParser().parseFromString('<!doctype html><body>' + String(html || ''), 'text/html');
  const body = doc.body;
  body.querySelectorAll(DROP).forEach(n => { if (n.matches('.mf-video,video') && report) report.converted.push('동영상 → 제외(본문 표기는 링크로)'); n.remove(); });
  body.querySelectorAll('video').forEach(v => { const src = safeHref(v.getAttribute('src') || v.querySelector('source')?.getAttribute('src')); const p = doc.createElement('p'); if (src) { const a = doc.createElement('a'); a.href = src; a.textContent = '▶ 동영상'; p.append(a); } else p.textContent = '(동영상 — 가져오지 못함)'; v.replaceWith(p); report?.converted.push('동영상 → 링크'); });
  // 제목 4~6단계 → 제목 3 (편집기는 3단계까지)
  body.querySelectorAll('h4,h5,h6').forEach(h => { const n = doc.createElement('h3'); n.append(...h.childNodes); h.replaceWith(n); report?.converted.push('제목 4~6단계 → 제목 3'); });
  // MarkFlow 형광펜(내보내기 HTML: span.mf-hl.mf-hl-N / Markdown 전처리: mark[data-mf-hl])
  body.querySelectorAll('span.mf-hl, mark[data-mf-hl]').forEach(el => {
    const n = el.getAttribute('data-mf-hl') || (String(el.className).match(/mf-hl-([1-5])/) || [])[1] || '1';
    const m = doc.createElement('mark'); m.setAttribute('data-color', MARKFLOW_HL[n] || HIGHLIGHT_COLORS[0].value);
    m.append(...el.childNodes); el.replaceWith(m);
    report?.converted.push('MarkFlow 형광펜 → 강조색');
  });
  // 체크리스트: GFM(input[type=checkbox]) · Toast UI(li.task-list-item) → TipTap taskList
  body.querySelectorAll('li').forEach(li => {
    const box = li.querySelector(':scope > input[type=checkbox], :scope > p > input[type=checkbox]');
    const tui = li.classList.contains('task-list-item') || li.hasAttribute('data-task');
    if (!box && !tui) return;
    const checked = box ? box.checked || box.hasAttribute('checked') : (li.classList.contains('checked') || li.getAttribute('data-task-checked') === 'true');
    box?.remove();
    li.setAttribute('data-type', 'taskItem'); li.setAttribute('data-checked', String(!!checked));
    const parent = li.parentElement; if (parent && parent.tagName === 'UL') parent.setAttribute('data-type', 'taskList');
  });
  // 스타일 → 팔레트(글자색) / 강조(배경색). 그 밖의 인라인 스타일은 버린다.
  body.querySelectorAll('[style]').forEach(el => {
    const color = nearestPalette(el.style.color, 'text');
    const bg = nearestPalette(el.style.backgroundColor || el.style.background, 'highlight');
    const tag = el.tagName.toLowerCase();
    const isInline = ['span', 'font', 'strong', 'b', 'em', 'i', 'u', 's', 'mark', 'a', 'code'].includes(tag);
    let target = el;
    if ((color || bg) && !isInline) { const s = doc.createElement('span'); s.append(...el.childNodes); el.append(s); target = s; }
    if (bg) { const m = doc.createElement('mark'); m.setAttribute('data-color', bg); m.append(...target.childNodes); target.append(m); target = m; }
    if (color) { const s = doc.createElement('span'); s.setAttribute('style', 'color:' + color); s.append(...target.childNodes); target.append(s); }
    if ((el.style.color && !color) || ((el.style.backgroundColor || el.style.background) && !bg)) report?.converted.push('팔레트에 없는 색 → 기본색');
    el.removeAttribute('style');
  });
  body.querySelectorAll('font[color]').forEach(el => { const c = nearestPalette(el.getAttribute('color'), 'text'); const s = doc.createElement('span'); if (c) s.setAttribute('style', 'color:' + c); s.append(...el.childNodes); el.replaceWith(s); });
  body.querySelectorAll('mark').forEach(m => { const c = nearestPalette(m.getAttribute('data-color'), 'highlight') || HIGHLIGHT_COLORS[0].value; m.setAttribute('data-color', c); m.setAttribute('style', 'background-color:' + c); });
  // 이미지
  body.querySelectorAll('img').forEach(img => {
    const raw = img.getAttribute('src') || '';
    const mf = parseMarkflowImageAlt(img.getAttribute('alt'));
    if (/⟪/.test(img.getAttribute('alt') || '')) { img.setAttribute('alt', mf.alt); if (mf.width) img.setAttribute('data-width', mf.width); if (mf.rotation) report?.converted.push('이미지 회전(' + mf.rotation + '°) → 회전 없이'); report?.converted.push('MarkFlow 이미지 크기 표기 → 폭 ' + (mf.width || '기본')); }
    else if (!img.getAttribute('data-width')) { const w = img.getAttribute('width') || img.style?.width || ''; const pct = /%$/.test(w) ? parseInt(w, 10) : 0; if (pct) img.setAttribute('data-width', pct <= 37 ? '25%' : pct <= 62 ? '50%' : pct <= 87 ? '75%' : '100%'); }
    if (img.getAttribute('data-asset-id') && img.getAttribute('data-status') === 'stored') return; // 이미 보관된 첨부(편집기 내부 복사)
    const info = onImage ? onImage(raw, img) : null;
    if (info) for (const [k, v] of Object.entries(info)) { if (v === null || v === undefined) img.removeAttribute(k); else img.setAttribute(k, v); }
    else { img.setAttribute('data-status', 'missing'); img.setAttribute('data-note', '이미지 주소를 처리할 수 없음'); img.removeAttribute('src'); }
  });
  // 속성 허용목록 · 위험 링크 제거
  body.querySelectorAll('*').forEach(el => {
    const tag = el.tagName.toLowerCase();
    const keep = KEEP_ATTR[tag] || [];
    for (const at of [...el.attributes]) {
      if (at.name === 'style' && (tag === 'span' || tag === 'mark') && /^(color|background-color):#[0-9a-f]{6}$/.test(at.value)) continue;
      if (!keep.includes(at.name)) el.removeAttribute(at.name);
    }
    if (tag === 'a') { const h = safeHref(el.getAttribute('href')); if (h) el.setAttribute('href', h); else { el.removeAttribute('href'); if (el.getAttribute('href') === null && report && el.textContent) report.converted.push('허용되지 않은 링크 주소 → 글자만'); } }
    if (tag === 'input' && el.getAttribute('type') !== 'checkbox') el.remove();
  });
  return body.innerHTML;
}

// 본문 글자 속 MarkFlow 표기(복사해서 붙여넣은 경우)를 강조·링크로 바꾼다
export function convertMarkflowText(editor) {
  const {state} = editor;
  const hl = state.schema.marks.highlight, link = state.schema.marks.link;
  let tr = state.tr, changed = 0;
  const hits = [];
  state.doc.descendants((node, pos) => {
    if (!node.isTextblock) return;
    const text = node.textContent;
    const vid = text.match(/^⟦vid ([^⟧]+)⟧$/);
    if (vid) { hits.push({kind: 'vid', from: pos + 1, to: pos + 1 + text.length, url: decodeMarkflowVideo(vid[1])}); return false; }
    // 한 텍스트 노드 안에 온전히 있는 표기만(글자 위치 오차 방지)
    node.forEach((child, off) => {
      if (!child.isText) return;
      MF_HL_RE.lastIndex = 0; let m;
      while ((m = MF_HL_RE.exec(child.text))) hits.push({kind: 'hl', from: pos + 1 + off + m.index, len: m[0].length, n: m[1], inner: m[2]});
    });
    return false;
  });
  for (const h of hits.reverse()) {
    if (h.kind === 'vid') { if (h.url) tr = tr.replaceWith(h.from, h.to, state.schema.text('▶ 동영상', [link.create({href: h.url})])); else tr = tr.insertText('(동영상 주소를 읽지 못함)', h.from, h.to); changed++; continue; }
    tr = tr.delete(h.from + 2 + h.inner.length, h.from + h.len).delete(h.from, h.from + 2);
    if (h.inner) tr = tr.addMark(h.from, h.from + h.inner.length, hl.create({color: MARKFLOW_HL[h.n]}));
    changed++;
  }
  if (changed) editor.view.dispatch(tr);
  return changed;
}

// 화면 없이 HTML → 문서 JSON (가져오기 미리보기용)
export function htmlToDoc(html) {
  const el = document.createElement('div');
  const ed = new Editor({element: el, extensions: extensions(), content: html});
  convertMarkflowText(ed);
  const json = ed.getJSON();
  ed.destroy();
  return json;
}

export {Editor};
