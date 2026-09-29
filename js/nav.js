// v 20260929-0000  nav.js — 모든 화면 공통 이동 박스. <header> 바로 아래에 "보는 순서" 라벨 + 화면 3개 링크를 붙이고, 지금 화면을 표시하고, 그 화면에서 뭘 보는지 한 줄로 알려준다.
// 2026-09-29: 허브(index.html)를 매수시장 판단(regime-lite-v1.html)에 흡수, 수동입력을 보고서 입력으로 단순화하며 번호(①②③) 없이 이름만 쓰도록 다시 만듦.
// 사용: <script src="js/nav.js" data-page="journal|market|manual"></script>
(function () {
  var NAV = [
    { id: 'journal', name: '투자일지',       file: 'journal.html',        what: '하루 한 장 — 결론·시장 상태·시간순 기록', look: '매일 여기서 시작해서 오늘 결론을 쓴다' },
    { id: 'market',  name: '매수시장 판단',  file: 'regime-lite-v1.html', what: '지금 사도 되는 시장인지 + 종목 후보', look: '종합 판정 한 줄 → 지표 카드 → 우호적이면 아래 종목분석으로' },
    { id: 'manual',  name: '보고서 입력',    file: 'manual.html',         what: 'IMF·연준·한국은행 등 보고서 읽고 판정 기록', look: '왼쪽에서 보고서 고르기 → 판정(위/그대로/아래) → 기록 만들기' }
  ];
  var CSS = '#nav-strip{background:#fff;border-bottom:1px solid #e3e6ee;padding:10px 16px}' +
    '#nav-strip .lbl{font-size:11px;font-weight:700;color:#9ca3af;letter-spacing:.02em;margin-bottom:6px}' +
    '#nav-strip .row{display:flex;flex-wrap:wrap;gap:6px;align-items:center;font-size:13px}' +
    '#nav-strip a{display:inline-flex;align-items:center;min-height:40px;padding:0 14px;border-radius:12px;border:1px solid #e3e6ee;text-decoration:none;color:#1f2430;background:#fff}' +
    '#nav-strip a.cur{background:#dbeafe;border-color:#93c5fd;font-weight:700;color:#1e40af}' +
    '#nav-strip .arrow{color:#9ca3af}#nav-strip .what{margin-top:6px;color:#374151;font-size:12.5px}#nav-strip .what b{color:#1e40af}';
  var esc = function (s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); };
  var sc = document.currentScript, page = (sc && sc.getAttribute('data-page')) || '';
  if (!page) { var f = (location.pathname.split('/').pop() || 'journal.html'); NAV.forEach(function (n) { if (n.file === f) page = n.id; }); }
  var idx = -1; NAV.forEach(function (n, i) { if (n.id === page) idx = i; });
  var st = document.createElement('style'); st.textContent = CSS; document.head.appendChild(st);
  var strip = document.createElement('nav'); strip.id = 'nav-strip'; strip.setAttribute('aria-label', '화면 이동');
  var row = NAV.map(function (n, i) {
    return (i ? '<span class="arrow">→</span>' : '') + '<a href="' + n.file + '"' + (i === idx ? ' class="cur" aria-current="page"' : '') + ' title="' + esc(n.what) + '">' + esc(n.name) + '</a>';
  }).join('');
  var h = '<div class="lbl">보는 순서 · 화면 이동</div><div class="row">' + row + '</div>';
  if (idx >= 0) h += '<div class="what"><b>여기서 볼 것</b> ' + esc(NAV[idx].look) + '</div>';
  strip.innerHTML = h;
  function mount() { var hd = document.querySelector('header'); if (hd && hd.parentNode) hd.parentNode.insertBefore(strip, hd.nextSibling); else document.body.insertBefore(strip, document.body.firstChild); }
  if (document.body) mount(); else document.addEventListener('DOMContentLoaded', mount);
  window.Nav = { list: NAV, page: page };
})();
