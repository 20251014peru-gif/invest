// v 20260929-0200  nav.js — 모든 화면 공통 이동 박스. "보는 순서" 라벨 + 화면 3개 링크, 지금 화면 표시, 그 화면에서 뭘 보는지 한 줄.
// 2026-09-29c: status.js 의 상단 경고 띠(#st-band, 비동기로 늦게 붙음)와 같은 top:0 에서 겹치던 문제 수정 — 띠가 붙거나 사라질 때마다 다시 계산해서 그 아래로 붙인다.
// 2026-09-29b: 스크롤해도 안 사라지게 상단 고정(position:sticky)으로 변경 — "제목·이동을 찾으려고 맨 위로 안 가게" 요청 반영.
// 2026-09-29: 허브(index.html)를 매수시장 판단(regime-lite-v1.html)에 흡수, 수동입력을 보고서 입력으로 단순화하며 번호(①②③) 없이 이름만 쓰도록 다시 만듦.
// 사용: <script src="js/nav.js" data-page="journal|market|manual"></script>
(function () {
  var NAV = [
    { id: 'journal', name: '투자일지',       file: 'journal.html',        what: '하루 한 장 — 결론·시장 상태·시간순 기록', look: '매일 여기서 시작해서 오늘 결론을 쓴다' },
    { id: 'market',  name: '매수시장 판단',  file: 'regime-lite-v1.html', what: '지금 사도 되는 시장인지 + 종목 후보', look: '종합 판정 한 줄 → 지표 카드 → 우호적이면 아래 종목분석으로' },
    { id: 'manual',  name: '보고서 입력',    file: 'manual.html',         what: 'IMF·연준·한국은행 등 보고서 읽고 판정 기록', look: '왼쪽에서 보고서 고르기 → 판정(위/그대로/아래) → 기록 만들기' }
  ];
  var CSS = '#nav-strip{position:sticky;top:0;z-index:80;background:#fff;border-bottom:1px solid #e3e6ee;padding:8px 16px;box-shadow:0 2px 8px rgba(31,36,48,.06)}' +
    '#nav-strip .lbl{font-size:10.5px;font-weight:700;color:#9ca3af;letter-spacing:.02em;margin-bottom:4px}' +
    '#nav-strip .row{display:flex;flex-wrap:wrap;gap:6px;align-items:center;font-size:13px}' +
    '#nav-strip a{display:inline-flex;align-items:center;min-height:36px;padding:0 14px;border-radius:12px;border:1px solid #e3e6ee;text-decoration:none;color:#1f2430;background:#fff}' +
    '#nav-strip a.cur{background:#dbeafe;border-color:#93c5fd;font-weight:700;color:#1e40af}' +
    '#nav-strip .arrow{color:#9ca3af}#nav-strip .what{margin-top:4px;color:#374151;font-size:12px}#nav-strip .what b{color:#1e40af}';
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
  function reflow() {
    // 상단에 같이 고정되는 다른 요소(예: status.js 의 #st-band 경고 띠, 화면 자체 sticky 헤더)가 있으면
    // 그만큼 아래로 내려 붙여서 top:0 에서 서로 겹치지 않게 한다.
    var top = 0;
    var band = document.getElementById('st-band');
    if (band && band !== strip) top += band.offsetHeight;
    var hd = document.querySelector('header');
    if (hd && strip.previousElementSibling === hd && getComputedStyle(hd).position === 'sticky') top += hd.offsetHeight;
    strip.style.top = top + 'px';
  }
  function mount() {
    var hd = document.querySelector('header');
    if (hd && hd.parentNode) {
      hd.parentNode.insertBefore(strip, hd.nextSibling);
    } else {
      document.body.insertBefore(strip, document.body.firstChild);
    }
    reflow();
    // status.js 의 경고 띠는 data/status.json 을 fetch 한 뒤 비동기로 body 맨 앞에 붙는다 — 그때 다시 계산
    try {
      new MutationObserver(reflow).observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['class'] });
    } catch (e) {}
    window.addEventListener('resize', reflow);
  }
  if (document.body) mount(); else document.addEventListener('DOMContentLoaded', mount);
  window.Nav = { list: NAV, page: page };
})();
