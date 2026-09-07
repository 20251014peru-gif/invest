// v 20260907-2100  regime.js — 레짐 요약 카드(공통). analysis/regime.json(regime/1) 을 읽어 el 에 그린다. axes.html·cygnus.html 이 같이 씀.
// 사용: <script src="js/regime.js"></script> 뒤에 window.Regime.render(document.getElementById('regime'), {compact:false})
// 원칙: 판정 옆에 반드시 신뢰(확인/추정/판단 불가) · 근거 지표 값 · 바뀌는 조건. 값 없는 신호는 '값 없음' 으로 그대로 보인다(조용히 숨기지 않음).
(function () {
  var esc = function (s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); };
  var CSS = '.rg{display:grid;gap:10px;grid-template-columns:repeat(auto-fit,minmax(260px,1fr))}' +
    '.rg .rk{background:#fff;border:1px solid #e3e6ee;border-radius:14px;padding:12px 14px;min-width:0}' +
    '.rg .rk.q{background:#f5f3ff;border-color:#ddd6fe}.rg .rk.memo{background:#fafafa;border-style:dashed}' +
    '.rg .rn{font-size:12px;color:#6b7280;display:flex;justify-content:space-between;align-items:center;gap:6px}' +
    '.rg .rv{font-size:20px;font-weight:700;margin:4px 0 2px;line-height:1.25}.rg .rv small{font-size:13px;font-weight:400;color:#6b7280}' +
    '.rg .rt{font-size:11px;padding:1px 8px;border-radius:8px;border:1px solid #e3e6ee;white-space:nowrap}' +
    '.rg .rt.ok{background:#dcfce7;color:#166534;border-color:#bbf7d0}.rg .rt.est{background:#fef3c7;color:#92400e;border-color:#fde68a}.rg .rt.na{background:#fee2e2;color:#991b1b;border-color:#fecaca}' +
    '.rg ul{margin:6px 0 0;padding:0;list-style:none;font-size:12.5px}.rg li{display:flex;gap:6px;padding:3px 0;border-top:1px dashed #e3e6ee;align-items:baseline;flex-wrap:wrap}' +
    '.rg li .w{font-weight:600;white-space:nowrap}.rg li .r{color:#374151}.rg li .off{font-size:11px;color:#6b7280;margin-left:auto}.rg li.none{color:#9ca3af}' +
    '.rg .flip{margin-top:8px;font-size:12px;color:#6b7280;background:#f6f7fb;border-radius:8px;padding:6px 8px}' +
    '.rg details summary{cursor:pointer;font-size:12.5px;color:#2563eb;min-height:32px;display:flex;align-items:center;margin-top:6px}' +
    '.rg .one{grid-column:1/-1;background:#eff6ff;border:1px solid #bfdbfe;border-radius:12px;padding:10px 14px;font-size:14px}' +
    '.rg .one small{display:block;color:#6b7280;font-size:12px;margin-top:2px}';
  var CYC = { D: '일간', W: '주간', M: '월간', Q: '분기', A: '연간' };
  function tag(c) { var k = c === '확인' ? 'ok' : c === '추정' ? 'est' : 'na'; return '<span class="rt ' + k + '">' + esc(c) + '</span>'; }
  function kst(iso) { if (!iso) return ''; var m = String(iso).match(/^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/); return m ? m[1] + ' ' + m[2] : String(iso).slice(0, 16); }
  function block(b, compact) {
    var sig = (b.signals || []).map(function (s) {
      var none = s.score == null;
      return '<li' + (none ? ' class="none"' : '') + '><span class="w">' + esc(s.name) + '</span><span class="r">' + esc(s.read) + '</span>' +
        (s.as_of ? '<span class="off">기준 ' + esc(s.as_of) + (s.cycle ? ' · ' + esc(CYC[s.cycle] || s.cycle) : '') + '</span>' : '') + '<span class="off">' + (s.official ? '공식' : '참고') + ' ×' + esc(s.weight) + '</span></li>';
    }).join('');
    var head = '<div class="rn"><span>' + esc(b.name) + '</span>' + tag(b.confidence) + '</div>' +
      '<div class="rv">' + esc(b.verdict) + (b.direction ? ' <small>· ' + esc(b.direction) + '</small>' : '') + ' <small>점수 ' + (b.score > 0 ? '+' : '') + esc(b.score) + ' · 신호 ' + esc(b.used) + '/' + (b.signals || []).length + '(공식 ' + esc(b.official_used) + ')</small></div>';
    var body = '<ul>' + sig + '</ul>' + (b.flip ? '<div class="flip">바뀌는 조건: ' + esc(b.flip) + '</div>' : '');
    return '<div class="rk">' + head + (compact ? '<details><summary>근거 ' + esc(b.used) + '개 · 바뀌는 조건</summary>' + body + '</details>' : body) + '</div>';
  }
  function render(el, opt) {
    opt = opt || {};
    if (!el) return;
    if (!document.getElementById('rg-css')) { var st = document.createElement('style'); st.id = 'rg-css'; st.textContent = CSS; document.head.appendChild(st); }
    el.classList.add('rg');
    el.innerHTML = '<div class="rk" style="grid-column:1/-1;color:#6b7280">레짐 읽는 중…</div>';
    return fetch('analysis/regime.json?t=' + Date.now(), { cache: 'no-store' }).then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); }).then(function (r) {
      var q = r.quadrant || {};
      var h = '<div class="one"><b>' + esc(r.one_line) + '</b><small>판정 ' + esc(kst(r.computed_at)) + ' KST · 값 수집 ' + esc(kst(r.macro_collected_at)) + ' · 기준값은 data/regime_rules.json(추정, 달님 판별 전)</small></div>';
      h += block(r.growth, opt.compact) + block(r.inflation, opt.compact) + block(r.liquidity, opt.compact);
      h += '<div class="rk q"><div class="rn"><span>4분면 (성장×물가)</span>' + tag(q.confidence) + '</div><div class="rv">' + esc(q.name) + (q.assets ? ' <small>→ ' + esc(q.assets) + ' 우위</small>' : '') + '</div><div style="font-size:12.5px;color:#374151;margin-top:4px">' + esc(q.note || '') + '</div>' +
        (r.growth && r.growth.verdict !== '판단 불가' ? '' : '') + '</div>';
      if (r.review && r.review.length) {
        var rows = r.review.map(function (x) { return '<tr><td>' + esc(x.block) + '</td><td>' + esc(x.id) + '</td><td>' + esc(x.current) + '</td><td>' + esc(x.status) + '</td><td>' + esc(x.suggest || '—') + '</td></tr>'; }).join('');
        var nSug = r.review.filter(function (x) { return x.status === '제안 있음'; }).length;
        h += '<div class="rk" style="grid-column:1/-1"><details' + (nSug ? ' open' : '') + '><summary>기준값 재검토(추정 ' + r.review.length + '개) — ' + (nSug ? '<b>제안 ' + nSug + '개</b>' : '아직 이력 부족, 제안 없음') + '</summary><div style="overflow-x:auto"><table style="border-collapse:collapse;width:100%;font-size:12.5px;min-width:520px"><thead><tr><th style="text-align:left;padding:4px 6px">칸</th><th style="text-align:left;padding:4px 6px">신호</th><th style="text-align:left;padding:4px 6px">현행(추정)</th><th style="text-align:left;padding:4px 6px">상태</th><th style="text-align:left;padding:4px 6px">제안(실측)</th></tr></thead><tbody>' + rows + '</tbody></table></div><div style="font-size:12px;color:#6b7280;margin-top:6px">제안은 자동 반영하지 않음 — 달님이 보고 data/regime_rules.json 의 숫자를 고치면 다음 판정부터 적용</div></details></div>';
      }
      if (r.memo && (r.memo.text || r.memo.basis)) h += '<div class="rk memo"><div class="rn"><span>축 문장(수동)</span><span class="rt est">초안 ' + esc(r.memo.as_of || '') + '</span></div><div style="font-size:13.5px;margin-top:4px">' + esc(r.memo.text) + '</div>' + (r.memo.basis ? '<div style="font-size:12px;color:#6b7280;margin-top:4px">근거: ' + esc(r.memo.basis) + '</div>' : '') + '</div>';
      el.innerHTML = h;
      if (typeof opt.after === 'function') opt.after(r);
      return r;
    }).catch(function (e) {
      el.innerHTML = '<div class="rk" style="grid-column:1/-1;background:#fee2e2;border-color:#fecaca">레짐 판정 파일(analysis/regime.json)을 못 읽음 — ' + esc(e.message) + '. Macro Collector 가 한 번 돌면 생깁니다.</div>';
      if (typeof opt.after === 'function') opt.after(null);
    });
  }
  window.Regime = { render: render };
})();
