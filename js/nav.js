// v 20260907-2030  nav.js — ★투자일지 앞, 예측 제거(유튜브 요약 쪽으로) — 모든 화면 공통 '읽는 순서' 길잡이. <header> 바로 아래에 ①→⑤ 띠를 붙이고, 지금 화면을 표시하고, '여기서 볼 것'과 '다음 →' 을 보여준다.
// 사용: <script src="js/nav.js" data-page="hub|market|axes|predict|manual"></script>  (헤더의 페이지 이동 버튼은 이 띠로 대체)
// 순서는 아침에 읽는 순서 그대로: 허브(오늘 뭐가 문제인가) → 시장(지금 어디인가) → 축·전략(왜, 그러면 뭘 하나) → 예측·채점(내가 맞았나) → 수동 입력(빈 값 채우기)
(function () {
  var NAV = [
    { id: 'journal', n: '★', name: '투자일지', file: 'journal.html', what: '하루 한 장 — 결론·시장 상태·시간순 기록', look: '매일 여기서 시작. 아래 화면들은 참고 서랍' },
    { id: 'hub',     n: '①', name: '허브',     file: 'index.html',   what: '오늘 상태 7칸 — 실패한 작업·확인 필요부터 본다', look: '확인 필요·실패한 작업 칸이 비어 있으면 정상. 시장 상태 한 줄로 오늘 레짐을 잡고 ②로' },
    { id: 'market',  n: '②', name: '시장',     file: 'cygnus.html',  what: '레짐 판정 + 지표(한국·미국·국제) + 고른 12개', look: '레짐 한 줄 → 확인/추정 태그 → 값 없음 카드는 수동 입력으로. 왜 그런지는 ③에서' },
    { id: 'axes',    n: '③', name: '축·전략',  file: 'axes.html',    what: '축 8개 × 6단계 — 왜 그렇고, 바뀌면 어떻게 하나', look: '축 이름을 눌러 읽기창: 근거 지표 → 변화 조건 → 대응 → 무효화. 전략 카드 5개로 행동' },
        { id: 'manual',  n: '④', name: '수동 입력', file: 'manual.html',  what: '자동 출처 없는 값(ISM PMI 등) 채우기', look: '출처 열기 → 값 입력 → JSON 복사 → GitHub 에서 붙여넣기 → 지금 실행' }
  ];
  var CSS = '#nav-strip{background:#fff;border-bottom:1px solid #e3e6ee;padding:8px 16px;display:flex;flex-wrap:wrap;gap:6px;align-items:center;font-size:13px}' +
    '#nav-strip a{display:inline-flex;align-items:center;gap:6px;min-height:40px;padding:0 12px;border-radius:12px;border:1px solid #e3e6ee;text-decoration:none;color:#1f2430;background:#fff}' +
    '#nav-strip a .n{font-weight:700;color:#6b7280}#nav-strip a.cur{background:#dbeafe;border-color:#93c5fd;font-weight:700}#nav-strip a.cur .n{color:#1e40af}' +
    '#nav-strip .arrow{color:#9ca3af}#nav-strip .what{flex-basis:100%;color:#374151;font-size:12.5px;display:flex;gap:8px;align-items:center;flex-wrap:wrap}' +
    '#nav-strip .what b{color:#1e40af}#nav-strip .next{margin-left:auto;display:inline-flex;align-items:center;min-height:36px;padding:0 12px;border-radius:10px;background:#eff6ff;border:1px solid #bfdbfe;text-decoration:none;color:#1e40af;font-weight:600}' +
    '@media (max-width:600px){#nav-strip a{padding:0 9px;min-height:40px}#nav-strip a .name{display:none}#nav-strip a.cur .name{display:inline}#nav-strip .arrow{display:none}}';
  var esc = function (s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); };
  var sc = document.currentScript, page = (sc && sc.getAttribute('data-page')) || '';
  if (!page) { var f = (location.pathname.split('/').pop() || 'index.html'); NAV.forEach(function (n) { if (n.file === f) page = n.id; }); }
  var idx = -1; NAV.forEach(function (n, i) { if (n.id === page) idx = i; });
  var st = document.createElement('style'); st.textContent = CSS; document.head.appendChild(st);
  var strip = document.createElement('nav'); strip.id = 'nav-strip'; strip.setAttribute('aria-label', '읽는 순서');
  var h = NAV.map(function (n, i) {
    return (i ? '<span class="arrow">→</span>' : '') + '<a href="' + n.file + '"' + (i === idx ? ' class="cur" aria-current="page"' : '') + ' title="' + esc(n.what) + '"><span class="n">' + n.n + '</span><span class="name">' + esc(n.name) + '</span></a>';
  }).join('');
  if (idx >= 0) {
    var cur = NAV[idx], nx = NAV[idx + 1];
    h += '<div class="what"><b>여기서 볼 것</b> ' + esc(cur.look) + (nx ? '<a class="next" href="' + nx.file + '">다음 ' + nx.n + ' ' + esc(nx.name) + ' →</a>' : '<a class="next" href="index.html">처음 ① 허브로</a>') + '</div>';
  }
  strip.innerHTML = h;
  function mount() { var hd = document.querySelector('header'); if (hd && hd.parentNode) hd.parentNode.insertBefore(strip, hd.nextSibling); else document.body.insertBefore(strip, document.body.firstChild); }
  if (document.body) mount(); else document.addEventListener('DOMContentLoaded', mount);
  window.Nav = { list: NAV, page: page };
})();
