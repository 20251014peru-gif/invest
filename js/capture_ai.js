// v 20260907-2330  capture_ai.js — cygnus 「📸 캡쳐 분석」 애드온
// 캡쳐(스크린샷)를 붙여넣으면 사용자의 Claude API 키로 이미지를 Claude 에게 보내 재무를 자동 추출·분석한다.
// 키/모델은 이 브라우저 localStorage 에만 저장(중계서버 주소처럼). api.anthropic.com 으로만 전송.
(function () {
  var LS_KEY = 'cai_key', LS_MODEL = 'cai_model', LS_RES = 'cai_results';
  function g(k, d) { try { return localStorage.getItem(k) || d; } catch (e) { return d; } }
  function s(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  function esc(x) { return String(x == null ? '' : x).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function fmt(n) { if (n == null || isNaN(n)) return '-'; return Number(n).toLocaleString('ko-KR', { maximumFractionDigits: 2 }); }
  function results() { try { return JSON.parse(localStorage.getItem(LS_RES) || '[]'); } catch (e) { return []; } }
  function saveResults(a) { s(LS_RES, JSON.stringify(a.slice(0, 20))); }

  var PROMPT = '이 네이버 증권 종목 화면 캡쳐에서 재무 정보를 읽어 JSON 하나만 출력해. 설명이나 코드블록 없이 순수 JSON 만. 키: {"name":종목명, "code":종목코드, "price":현재가, "per":PER배수, "pbr":PBR배수, "eps_this":올해EPS, "eps_next":내년추정EPS, "w52hi":52주최고가, "w52lo":52주최저가, "rev_yoy":매출성장률퍼센트, "op_margin":영업이익률퍼센트, "op_margin_prev":전기영업이익률퍼센트, "net_margin":순이익률퍼센트, "roe":ROE퍼센트, "roe_prev":전기ROE퍼센트, "debt_ratio":부채비율퍼센트, "div_yield":배당수익률퍼센트}. 화면에 없는 값은 null. 숫자는 콤마 없이 숫자로만. 확실하지 않으면 null.';

  function analyze(f) {
    var out = {};
    if (f.eps_next != null && f.per != null) { out.fair = Math.round(f.eps_next * f.per); if (f.price) out.upside = Math.round((out.fair - f.price) / f.price * 100); }
    if (out.fair != null) out.buyLine = Math.round(out.fair * 0.85);          // 매수 적정선 = 적정주가 −15%(안전마진)
    if (f.price != null) { out.stopLine = Math.round(f.price * 0.95); out.stopCB = Math.round(f.price * 0.875); } // 손절 −5%(규칙) · 계좌서킷 −12.5%
    out.pos = (out.upside != null) ? (out.upside > 20 ? '싼 자리' : out.upside < -20 ? '비싼 자리' : '보통') : null;
    out.epsDir = (f.eps_next != null && f.eps_this != null) ? (f.eps_next > f.eps_this * 1.01 ? '상향' : f.eps_next < f.eps_this * 0.99 ? '하향' : '유지') : null;
    if (out.pos && out.epsDir) {
      var cheap = out.pos === '싼 자리', pricey = out.pos === '비싼 자리', up = out.epsDir === '상향', dn = out.epsDir === '하향';
      if (cheap && up) out.signal = '🟢 쌀 때 실적 오르는 자리';
      else if (pricey && dn) out.signal = '🔴 비쌀 때 실적 꺾이는 자리';
      else if (cheap && dn) out.signal = '🟡 싸지만 실적 꺾임 — 함정 주의';
      else if (pricey && up) out.signal = '🟡 실적 좋지만 이미 비쌈';
      else out.signal = '🟡 중립';
    }
    // ROE 저평가 함정 필터: 싸 보여도 자본효율(ROE)이 낮으면 함정일 수 있다
    if (out.pos === '싼 자리' && f.roe != null) {
      out.trap = f.roe >= 15 ? { t: '진짜 저평가 — ROE ' + f.roe + '% (자본효율 높음)', c: 'good' }
        : f.roe < 8 ? { t: '⚠️ 저평가 함정 주의 — ROE ' + f.roe + '% (자본효율 낮음, 싼 데는 이유가 있을 수 있음)', c: 'bad' }
        : { t: 'ROE ' + f.roe + '% (보통)', c: 'mid' };
      if (f.roe < 8 && out.signal && out.signal.indexOf('🟢') >= 0) out.signal = '🟡 싸 보이나 자본효율 낮음 — 함정 주의';
    }
    if (f.op_margin != null && f.op_margin > 40) { out.diag = '경기민감 고점 신호: 초고마진' + ((f.roe_prev != null && f.roe != null && f.roe < f.roe_prev) ? ' · ROE 꺾임' : ''); }
    return out;
  }

  function card(f) {
    var a = analyze(f);
    var h = '<div class="card" style="margin-bottom:12px;border-color:#93c5fd">';
    h += '<div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:6px;align-items:center"><b style="font-size:16px">' + esc(f.name || '종목') + (f.code ? ' <span class="muted" style="font-size:12px">' + esc(f.code) + '</span>' : '') + '</b><span class="muted" style="font-size:12px">' + esc(f._at || '') + ' <button class="cai-del" data-id="' + esc(f._id) + '" type="button" style="border:0;background:none;cursor:pointer;font-size:13px">🗑</button></span></div>';
    if (a.signal) h += '<div class="k" style="margin:8px 0;background:' + (a.signal.indexOf('🟢') >= 0 ? '#dcfce7' : a.signal.indexOf('🔴') >= 0 ? '#fee2e2' : '#fefce8') + '"><b>' + esc(a.signal) + '</b></div>';
    if (a.diag) h += '<div class="k" style="margin:8px 0;background:#fefce8;border:1px solid #fde047"><b>⚠️ ' + esc(a.diag) + '</b></div>';
    if (a.trap) h += '<div class="k" style="margin:8px 0;background:' + (a.trap.c === 'good' ? '#dcfce7' : a.trap.c === 'bad' ? '#fee2e2' : '#f1f5f9') + '"><b>' + esc(a.trap.t) + '</b></div>';
    var rows = [];
    function row(l, v, x) { if (v == null || v === '') return; rows.push('<tr><td>' + l + '</td><td><b>' + v + '</b></td><td class="muted">' + (x || '') + '</td></tr>'); }
    row('현재가', f.price != null ? fmt(f.price) : null, (f.w52lo != null && f.w52hi != null) ? '52주 ' + fmt(f.w52lo) + '~' + fmt(f.w52hi) : '');
    if (a.fair != null) row('적정주가', fmt(a.fair) + '원', (a.upside != null ? '상승여력 ' + (a.upside > 0 ? '+' : '') + a.upside + '% · ' + (a.pos || '') : '') + ' (내년EPS×PER)');
    if (a.buyLine != null || a.stopLine != null) row('매수·손절 (참고)', (a.buyLine != null ? '매수선 ' + fmt(a.buyLine) : '') + (a.stopLine != null ? ' · 손절 ' + fmt(a.stopLine) : ''), '적정×0.85(안전마진) · 매수 후 −5%(손절규칙)' + (a.stopCB != null ? ' · 계좌 −12.5% 서킷' : ''));
    row('PER / PBR', (f.per != null ? f.per + '배' : '-') + ' / ' + (f.pbr != null ? f.pbr + '배' : '-'));
    row('EPS 올해→내년', (f.eps_this != null ? fmt(f.eps_this) : '-') + ' → ' + (f.eps_next != null ? fmt(f.eps_next) : '-'), a.epsDir ? '(' + a.epsDir + ')' : '');
    row('매출 성장', f.rev_yoy != null ? (f.rev_yoy > 0 ? '▲' : f.rev_yoy < 0 ? '▼' : '') + Math.abs(f.rev_yoy) + '%' : null);
    row('영업이익률', f.op_margin != null ? f.op_margin + '%' : null, f.op_margin_prev != null ? '전기 ' + f.op_margin_prev + '%' : '');
    row('순이익률', f.net_margin != null ? f.net_margin + '%' : null);
    row('ROE', f.roe != null ? f.roe + '%' : null, f.roe_prev != null ? '전기 ' + f.roe_prev + '%' : '');
    row('부채비율', f.debt_ratio != null ? f.debt_ratio + '%' : null, f.debt_ratio != null ? (f.debt_ratio < 50 ? '건전' : f.debt_ratio < 100 ? '보통' : '높음') : '');
    row('배당수익률', f.div_yield != null ? f.div_yield + '%' : null);
    h += '<table style="margin-top:8px"><tr><th>구분</th><th>값</th><th>참고</th></tr>' + rows.join('') + '</table>';
    h += '<p class="muted" style="font-size:12px;margin-top:4px">📸 캡쳐에서 Claude 가 읽음 · 최종 판단은 회사표 「판단(달님)」 칸에</p></div>';
    return h;
  }

  function renderAll() { var wrap = document.getElementById('caiResults'); if (!wrap) return; var rs = results(); wrap.innerHTML = rs.length ? rs.map(card).join('') : ''; }

  function callClaude(b64, mt, statusEl) {
    var key = g(LS_KEY, ''), model = g(LS_MODEL, 'claude-sonnet-4-6');
    if (!key) { statusEl.innerHTML = '<span style="color:#c00">사진은 받았지만 <b>API 키가 없어</b> 읽지 못했습니다 — 위 ⚙ Claude API 설정에서 키를 저장하고 다시 붙여넣으세요. 키 없이 쓰려면 캡쳐를 채팅(Claude)에 보내는 방식.</span>'; var d = document.querySelector('#caiPanel details'); if (d) d.open = true; return; }
    statusEl.textContent = '🔍 Claude 가 캡쳐 읽는 중…';
    fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: { 'x-api-key': key, 'anthropic-version': '2023-06-01', 'anthropic-dangerous-direct-browser-access': 'true', 'content-type': 'application/json' },
      body: JSON.stringify({ model: model, max_tokens: 1024, messages: [{ role: 'user', content: [{ type: 'image', source: { type: 'base64', media_type: mt, data: b64 } }, { type: 'text', text: PROMPT }] }] })
    }).then(function (r) { return r.json(); }).then(function (d) {
      if (d.error) { statusEl.innerHTML = '<span style="color:#c00">오류: ' + esc(d.error.message || JSON.stringify(d.error)) + '</span>'; return; }
      var txt = (d.content && d.content[0] && d.content[0].text) || '';
      var m = txt.match(/\{[\s\S]*\}/); if (!m) { statusEl.innerHTML = '<span style="color:#c00">읽기 실패 — 응답 앞부분: ' + esc(txt.slice(0, 120)) + '</span>'; return; }
      var f; try { f = JSON.parse(m[0]); } catch (e) { statusEl.innerHTML = '<span style="color:#c00">JSON 파싱 실패</span>'; return; }
      f._id = 'c' + Date.now();
      f._at = new Date().toLocaleString('ko-KR', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
      var a = analyze(f); f.signal = a.signal || ''; f.pos = a.pos || null; f.diag = a.diag || null; // 회사표 🟢🔴 뱃지용
      var rs = results(); rs.unshift(f); saveResults(rs); renderAll();
      try { document.dispatchEvent(new Event('cai-updated')); } catch (e) {} // 회사표 뱃지 갱신 신호
      statusEl.textContent = '✅ ' + (f.name || '종목') + ' 분석 완료';
    }).catch(function (e) { statusEl.innerHTML = '<span style="color:#c00">호출 실패: ' + esc(e.message) + ' (키·모델·네트워크 확인)</span>'; });
  }

  function reveal() {                                   // 📸 구역이 접혀 있으면 펴고, 패널로 스크롤 — 붙여넣은 뒤 아무 반응이 없어 보이는 문제 방지(2026-09-07)
    var h = document.getElementById('cap'), body = h && h.nextElementSibling;
    if (body && body.hidden) h.click();
    var pnl = document.getElementById('caiPanel'); if (pnl) pnl.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
  function handleFile(file, statusEl) {
    if (!file || !/^image\//.test(file.type)) return;
    reveal();
    var rd = new FileReader();
    rd.onload = function () { var res = rd.result; var b64 = res.split(',')[1]; var mt = (res.match(/^data:(image\/[^;]+)/) || [])[1] || 'image/png'; callClaude(b64, mt, statusEl); };
    rd.readAsDataURL(file);
  }

  function buildUI(host) {
    if (!host || document.getElementById('caiPanel')) return;
    var panel = document.createElement('div');
    panel.id = 'caiPanel';
    panel.innerHTML =
      '<div class="card" style="margin-bottom:10px;border-color:#c4b5fd;background:#faf5ff">'
      + '<details style="margin-bottom:8px"><summary style="cursor:pointer;font-weight:600">⚙ Claude API 설정 (처음 1번만)</summary>'
      + '<div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:8px;align-items:center">'
      + '<input id="caiKey" type="password" placeholder="Claude API 키 (sk-ant-...)" style="flex:1;min-width:220px;padding:6px;border:1px solid #ccc;border-radius:6px">'
      + '<input id="caiModel" placeholder="모델" style="width:180px;padding:6px;border:1px solid #ccc;border-radius:6px">'
      + '<button class="btn pri" id="caiSave" type="button">저장</button></div>'
      + '<p class="muted" style="font-size:12px;margin:6px 0 0">키는 <b>이 브라우저에만</b> 저장돼요(중계서버 주소처럼). 다른 곳으로 안 나가고 api.anthropic.com 으로만 갑니다. 모델 기본값 claude-sonnet-4-6(달님 표준).</p></details>'
      + '<div id="caiDrop" tabindex="0" style="border:2px dashed #c4b5fd;border-radius:8px;padding:16px;text-align:center;cursor:pointer;background:#fff">'
      + '📸 여기를 클릭한 뒤 <b>붙여넣기(Ctrl+V)</b> 하거나, <label style="color:#7c3aed;text-decoration:underline;cursor:pointer">파일 선택<input id="caiFile" type="file" accept="image/*" hidden></label><br>'
      + '<span class="muted" style="font-size:13px">네이버 종목 화면(투자정보·기업실적분석)을 캡쳐해 붙여넣으면 Claude 가 읽어 재무요약을 만듭니다</span></div>'
      + '<div id="caiStatus" class="muted" style="margin-top:6px;font-size:13px"></div>'
      + '</div><div id="caiResults"></div>';
    host.parentNode.insertBefore(panel, host);
    document.getElementById('caiKey').value = g(LS_KEY, '');
    document.getElementById('caiModel').value = g(LS_MODEL, 'claude-sonnet-4-6');
    var statusEl = document.getElementById('caiStatus');
    document.getElementById('caiSave').onclick = function () { s(LS_KEY, document.getElementById('caiKey').value.trim()); s(LS_MODEL, document.getElementById('caiModel').value.trim() || 'claude-sonnet-4-6'); statusEl.textContent = '✅ 저장됨'; };
    document.getElementById('caiFile').onchange = function (e) { handleFile(e.target.files[0], statusEl); };
    var drop = document.getElementById('caiDrop');
    drop.onclick = function () { drop.focus(); };
    document.addEventListener('paste', function (e) {
      if (!document.getElementById('caiPanel')) return;
      var t = e.target; if (t && (t.id === 'caiKey' || t.id === 'caiModel')) return;
      var items = (e.clipboardData || {}).items || [];
      for (var i = 0; i < items.length; i++) { if (items[i].type.indexOf('image') === 0) { handleFile(items[i].getAsFile(), statusEl); e.preventDefault(); return; } }
    });
    document.addEventListener('click', function (e) { var b = e.target.closest ? e.target.closest('.cai-del') : null; if (b) { var id = b.getAttribute('data-id'); saveResults(results().filter(function (x) { return x._id !== id; })); renderAll(); } });
    renderAll();
  }

  function init() { var host = document.getElementById('capBox'); if (!host) { return setTimeout(init, 600); } buildUI(host); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
