// 공부노트 읽기 화면 — 편집기 번들 없이 study-core 의 안전한 렌더러만 사용(빠르게 열림).
import * as C from './study-core.mjs';

const chip = (t, cls = '') => '<span class="m1 ' + cls + '">' + t + '</span>';

export function relationListHTML(records, id, KINDS) {
  const v = C.relationView(records, id);
  const row = x => {
    const k = KINDS?.[x.target?.kind] || {i: '📄', n: '기록'};
    const lbl = x.dir === 'fwd' ? (C.RELATION_TYPES[x.type]?.fwd || '관련') : (C.RELATION_TYPES[x.type]?.rev || '관련');
    if (!x.target) return '<div class="st-rel is-missing"><span>⚠</span> <span class="st-warn">삭제됐거나 찾을 수 없는 기록</span> <small class="st-muted">' + C.esc(lbl) + ' · ID ' + C.esc(x.targetId) + '</small></div>';
    return '<div class="st-rel"><span>' + k.i + '</span> <button type="button" class="st-link" data-goto="' + C.esc(x.target.id) + '">' + C.esc(x.target.title || '(제목 없음)') + '</button> <small class="st-muted">' + C.esc(lbl) + (x.dir === 'rev' ? ' · 상대 기록에서 연결' : '') + '</small></div>';
  };
  return {refs: v.references.map(row).join(''), hyps: v.hypotheses.map(row).join(''), back: v.backlinks.map(row).join('')};
}

export function renderStudyPage(r, {records = [], KINDS = {}, VERIFY_STATES = {}} = {}) {
  const doc = C.docForRecord(r);
  const assets = Object.fromEntries((r.assets || []).map(a => [a.id, a]));
  const legacy = r.contentFormat !== C.CONTENT_FORMAT;
  const meta = [
    chip('📚 ' + C.esc(C.STUDY_TYPES[r.studyType] || '개념 정리')),
    chip(C.esc(C.STUDY_STATUS[r.studyStatus] || '공부 중'), 'st-status-' + (r.studyStatus || 'learning')),
    chip('자료 기준일 ' + C.esc(r.asOfDate || '미지정')),
    r.reviewAt ? chip('재검토 ' + C.esc(r.reviewAt), r.reviewAt <= new Date(Date.now() + 9 * 3600000).toISOString().slice(0, 10) ? 'st-due' : '') : '',
    r.date ? chip('📅 작성 ' + C.esc(r.date)) : '',
    r.updatedAt ? chip('수정 ' + C.esc(new Date(r.updatedAt).toLocaleString('ko-KR', {hour12: false}))) : '',
    C.safeHref(r.source?.url || r.link) ? '<a class="m1" href="' + C.esc(C.safeHref(r.source?.url || r.link)) + '" target="_blank" rel="noopener noreferrer">🔗 ' + C.esc(r.source?.name || r.channel || '출처 열기') + '</a>' : (r.source?.name ? chip('출처: ' + C.esc(r.source.name)) : ''),
    r.verifyState && VERIFY_STATES[r.verifyState] ? '<span class="vbadge" style="background:' + VERIFY_STATES[r.verifyState].c + '">🔍 ' + C.esc(VERIFY_STATES[r.verifyState].n) + '</span>' : chip('검증 상태 미지정', 'st-muted')
  ].join('');
  const tags = [...(r.topics || []).map(t => '<span class="stag" style="background:#eef3fb">#' + C.esc(t) + '</span>'), ...(r.industries || []).map(t => '<span class="stag st-ind">산업 ' + C.esc(t) + '</span>'), ...(r.themes || []).map(t => '<span class="stag st-theme">테마 ' + C.esc(t) + '</span>'), ...(r.stocks || []).map(s => '<span class="stag">' + C.esc(s) + '</span>')].join('');
  const rel = relationListHTML(records, r.id, KINDS);
  const o = r.origin || {};
  const origin = o.app === 'markflow' ? 'MarkFlow ' + (o.format === 'markflow-md' ? 'Markdown' : 'HTML') + ' 파일에서 가져옴' + (o.importedAt ? ' · ' + C.esc(o.importedAt.slice(0, 10)) : '') + (o.documentId ? ' · 문서 ID ' + C.esc(o.documentId) : '') : o.app === 'backup' ? '노트 파일에서 복원' : '';
  const checks = (r.checks || []).slice().sort((a, b) => (a.date || '').localeCompare(b.date || ''));
  const st = C.docStats(doc);
  return '<div class="st-page">'
    + '<h2 class="st-ptitle">' + C.esc(r.title || '') + '</h2>'
    + (r.oneLiner ? '<div class="pg-oneliner">📌 ' + C.esc(r.oneLiner) + '</div>' : '')
    + '<div class="pg-meta">' + meta + '</div>'
    + (tags ? '<div class="pg-stocks">' + tags + '</div>' : '')
    + '<p class="st-hint">정리 상태는 공부 진행 정도이며, 본문 내용의 사실 확인 여부와는 별개입니다.' + (origin ? ' · ' + origin : '') + '</p>'
    + (st.imagesExternal || st.imagesMissing ? '<p class="st-warn">⚠ 보관되지 않았거나 누락된 이미지 ' + (st.imagesExternal + st.imagesMissing) + '개가 있어요 — 수정 화면에서 파일로 다시 첨부할 수 있어요.</p>' : '')
    + '<div class="st-readbar"><button type="button" class="st-mini" data-secs="open">모두 펼치기</button><button type="button" class="st-mini" data-secs="close">모두 접기</button>' + (legacy ? '<small class="st-muted">서식 없는 이전 형식 본문 — 수정하면 서식 문서로 바뀌어요</small>' : '') + '</div>'
    + '<div class="st-readgrid">' + C.tocHTML(doc, 'pv') + '<article class="st-prose st-read">' + C.renderDocHTML(doc, {assets, idPrefix: 'pv'}) + '</article></div>'
    + (r.userJudgment ? '<div class="pg-h4">🙋 내 판단</div><div class="pg-body" style="max-height:none">' + C.esc(r.userJudgment) + '</div>' : '')
    + (r.aiInterpretation ? '<div class="pg-h4">🤖 AI 해석 <small class="st-muted">내 판단과 구분</small></div><div class="pg-body" style="max-height:none">' + C.esc(r.aiInterpretation) + '</div>' : '')
    + '<div class="st-rels st-readrels"><div class="st-relcol"><h4>참고 자료</h4>' + (rel.refs || '<small class="st-muted">연결한 자료 없음</small>') + '</div><div class="st-relcol"><h4>관련 투자 가설</h4>' + (rel.hyps || '<small class="st-muted">연결한 가설 없음</small>') + '</div>'
    + (rel.back ? '<div class="st-relcol"><h4>이 노트를 연결한 기록</h4>' + rel.back + '</div>' : '') + '</div>'
    + (checks.length ? '<div class="pg-h4">📅 다음 확인사항</div><table class="pg-checktbl"><tr><th>날짜</th><th>확인할 것</th><th>그때 할 행동</th></tr>' + checks.map(c => '<tr><td>' + C.esc(c.date || '') + '</td><td>' + C.esc(c.what || '') + '</td><td>' + C.esc(c.action || '') + '</td></tr>').join('') + '</table>' : '')
    + '</div>';
}

export function bindStudyPage(host, {onGoto} = {}) {
  host.querySelectorAll('[data-toc]').forEach(a => a.addEventListener('click', ev => {
    ev.preventDefault();
    const t = host.querySelector('#' + CSS.escape(a.dataset.toc));
    if (!t) return;
    for (let p = t.parentElement; p && p !== host; p = p.parentElement) if (p.tagName === 'DETAILS') p.open = true;
    t.scrollIntoView({block: 'start', behavior: 'smooth'});
  }));
  host.querySelectorAll('[data-secs]').forEach(b => b.addEventListener('click', () => host.querySelectorAll('details.st-sec').forEach(d => { d.open = b.dataset.secs === 'open'; })));
  host.querySelectorAll('[data-goto]').forEach(b => b.addEventListener('click', () => onGoto?.(b.dataset.goto)));
}
