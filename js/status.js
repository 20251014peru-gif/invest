// v 20260904-1310  status.js — 모든 앱 공통: ① 상단 경고 띠(status.json) ② 🐞 오류 오버레이 + [복사]
// 사용법:  <script src="js/status.js" data-app="hub" data-version="v 20260904-1310"></script>
// 규칙:   철칙 4 "실패는 소리를 낸다" — 문제가 있을 때만 나타난다(노션식). 문제 없으면 화면에 아무것도 안 그린다.
// 읽는 파일: data/status.json (schema "status/1")  — 이 파일은 워크플로(GitHub Actions)가 쓰고, 사람은 읽기만.
(function () {
  'use strict';
  var S = document.currentScript || {};
  var APP = S.dataset ? (S.dataset.app || 'app') : 'app';
  var VER = S.dataset ? (S.dataset.version || '') : '';
  // js/status.js 가 있는 곳의 한 단계 위가 저장소 루트 → data/status.json
  var ROOT = (S.src || location.href).replace(/js\/status\.js.*$/, '');
  var STATUS_URL = ROOT + 'data/status.json';
  var LS_DISMISS = 'status_dismissed_' + APP;

  /* ---------- KST ---------- */
  function kstNow() { return new Date(Date.now() + 9 * 3600 * 1000); }           // UTC+9 로 밀어 둔 Date (getUTC* 로 읽는다)
  function kstStr(d) {                                                              // "2026-09-04 13:10 KST"
    if (!(d instanceof Date)) d = new Date(d);
    if (isNaN(d)) return '시각 없음';
    var k = new Date(d.getTime() + 9 * 3600 * 1000), p = function (n) { return (n < 10 ? '0' : '') + n; };
    return k.getUTCFullYear() + '-' + p(k.getUTCMonth() + 1) + '-' + p(k.getUTCDate()) + ' ' + p(k.getUTCHours()) + ':' + p(k.getUTCMinutes()) + ' KST';
  }

  /* ---------- CSS ---------- */
  var css = [
    '#st-band{position:sticky;top:0;z-index:9998;font:14px/1.5 -apple-system,"Malgun Gothic",sans-serif;border-bottom:2px solid #f5b7b1;background:#fdecea;color:#7b241c;padding:10px 14px}',
    '#st-band.warn{background:#fff6e0;border-color:#f7dc9a;color:#7d5a00}',
    '#st-band .st-title{font-weight:700;display:flex;align-items:center;gap:8px;cursor:pointer;min-height:24px}',
    '#st-band .st-job{margin:6px 0 0 4px;padding-left:10px;border-left:3px solid currentColor}',
    '#st-band .st-job b{display:inline-block;min-width:64px}',
    '#st-band.folded .st-job{display:none}',
    '#st-band button{font:inherit;font-size:13px;min-height:32px;white-space:nowrap;padding:4px 12px;border-radius:8px;border:1px solid currentColor;background:#fff;color:inherit;cursor:pointer;margin-left:auto}',
    '#st-bug{position:fixed;right:14px;bottom:14px;z-index:9999;min-width:48px;height:48px;border-radius:24px;border:none;background:#f5b7b1;color:#7b241c;font:700 14px -apple-system,"Malgun Gothic",sans-serif;box-shadow:0 2px 8px rgba(0,0,0,.2);cursor:pointer;padding:0 14px}',
    '#st-ov{position:fixed;inset:0;z-index:10000;background:rgba(0,0,0,.35);display:flex;align-items:flex-end;justify-content:center}',
    '#st-ov .st-box{background:#fff;color:#222;width:min(720px,100%);max-height:80vh;border-radius:16px 16px 0 0;padding:14px 16px;font:14px/1.5 -apple-system,"Malgun Gothic",sans-serif;display:flex;flex-direction:column}',
    '#st-ov .st-head{display:flex;gap:8px;align-items:center;margin-bottom:8px}',
    '#st-ov .st-head b{font-size:16px}',
    '#st-ov .st-head button{font:inherit;min-height:44px;padding:0 16px;border-radius:10px;border:1px solid #ccc;background:#f4f6fb;cursor:pointer}',
    '#st-ov .st-head button.pri{background:#d6e4ff;border-color:#9dbbff}',
    '#st-ov pre{flex:1;overflow:auto;margin:0;background:#f7f7f9;border-radius:10px;padding:10px;font:12.5px/1.5 Consolas,monospace;white-space:pre-wrap;word-break:break-all}'
  ].join('');
  var st = document.createElement('style'); st.textContent = css; document.head.appendChild(st);

  /* ---------- ① 상단 경고 띠 ---------- */
  function showBand(level, title, jobs) {
    var old = document.getElementById('st-band'); if (old) old.remove();
    var band = document.createElement('div'); band.id = 'st-band'; if (level === 'warn') band.className = 'warn';
    var h = '<div class="st-title"><span>' + (level === 'warn' ? '⚠️' : '🔴') + ' ' + title + '</span>' +
      '<button type="button" data-act="fold">접기/펴기</button></div>';
    jobs.forEach(function (j) {
      h += '<div class="st-job"><b>' + esc(j.name || j.id) + '</b> ' + esc(j.statusText) +
        (j.ran ? ' · 마지막 ' + kstStr(j.ran) : '') +
        (j.cause ? '<br><b>원인</b> ' + esc(j.cause) : '') +
        (j.fix ? '<br><b>해결</b> ' + esc(j.fix) : '') +
        (j.link ? ' <a href="' + esc(j.link) + '" target="_blank" rel="noopener">열기</a>' : '') + '</div>';
    });
    band.innerHTML = h;
    band.querySelector('[data-act=fold]').onclick = function () { band.classList.toggle('folded'); };
    document.body.prepend(band);
  }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }

  // status.json 한 건을 판정: fail → 빨강 / due 가 지났으면 stale(노랑) / ok → 조용
  function judge(j) {
    var now = Date.now();
    if (j.status === 'fail') return { level: 'fail', text: '실패' };
    if (j.status === 'stopped') return null;                                       // status=중단 은 경고 아님(철칙 2)
    if (j.due && !isNaN(new Date(j.due)) && new Date(j.due).getTime() < now) return { level: 'warn', text: '늦음 — 예정 ' + kstStr(j.due) + ' 지남' };
    if (j.status === 'stale') return { level: 'warn', text: '오래됨' };
    return null;
  }
  function loadStatus() {
    fetch(STATUS_URL + '?t=' + Date.now(), { cache: 'no-store' }).then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    }).then(function (d) {
      if (!d || d.schema !== 'status/1' || !Array.isArray(d.jobs)) throw new Error('규격 아님(schema status/1 필요)');
      var bad = [], worst = 'warn';
      d.jobs.forEach(function (j) {
        var v = judge(j); if (!v) return;
        if (v.level === 'fail') worst = 'fail';
        bad.push({ id: j.id, name: j.name, statusText: v.text, ran: j.ran, cause: j.cause, fix: j.fix, link: j.link });
      });
      if (!bad.length) return;
      showBand(worst, (worst === 'fail' ? '실패한 작업 ' : '늦어진 작업 ') + bad.length + '개 — 갱신 ' + kstStr(d.updated), bad);
    }).catch(function (e) {
      showBand('warn', 'status.json 을 읽지 못함', [{ name: 'status.json', statusText: String(e.message || e),
        cause: '파일이 없거나 규격이 다르거나 GitHub Pages 반영 전', fix: 'data/status.json 이 저장소에 있는지, 첫 줄 "schema":"status/1" 인지 확인. 🐞 [복사] 로 Claude 에게 붙여넣기' }]);
    });
  }

  /* ---------- ② 🐞 오류 오버레이 + [복사] ---------- */
  var errors = [];
  function push(kind, msg, where) {
    errors.push({ t: kstStr(new Date()), kind: kind, msg: String(msg), where: where || '' });
    if (errors.length > 50) errors.shift();
    var b = document.getElementById('st-bug');
    if (!b) { b = document.createElement('button'); b.id = 'st-bug'; b.type = 'button'; b.onclick = openOverlay; (document.body || document.documentElement).appendChild(b); }
    b.textContent = '🐞 ' + errors.length;
  }
  function report() {
    return ['앱: ' + APP + '  ' + VER, '주소: ' + location.href, '시각: ' + kstStr(new Date()), '브라우저: ' + navigator.userAgent, '화면: ' + innerWidth + 'x' + innerHeight, '---']
      .concat(errors.map(function (e, i) { return (i + 1) + '. [' + e.t + '] ' + e.kind + ' ' + e.msg + (e.where ? '\n   @ ' + e.where : ''); })).join('\n');
  }
  function copyText(t, btn) {
    var done = function () { btn.textContent = '복사됨 ✓'; setTimeout(function () { btn.textContent = '복사'; }, 1500); };
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(t).then(done, function () { fallback(t); done(); });
    else { fallback(t); done(); }
  }
  function fallback(t) { var ta = document.createElement('textarea'); ta.value = t; ta.style.position = 'fixed'; ta.style.opacity = 0; document.body.appendChild(ta); ta.select(); try { document.execCommand('copy'); } catch (e) { } ta.remove(); }
  function openOverlay() {
    var ov = document.getElementById('st-ov'); if (ov) ov.remove();
    ov = document.createElement('div'); ov.id = 'st-ov';
    ov.innerHTML = '<div class="st-box"><div class="st-head"><b>🐞 오류 ' + errors.length + '건</b>' +
      '<button type="button" class="pri" data-act="copy">복사</button><button type="button" data-act="clear">비우기</button><button type="button" data-act="close">닫기</button></div>' +
      '<div style="color:#666;margin-bottom:6px">[복사] 를 누른 뒤 Claude 에게 그대로 붙여넣으면 됩니다.</div><pre></pre></div>';
    ov.querySelector('pre').textContent = report();
    ov.onclick = function (e) {
      var a = e.target.dataset && e.target.dataset.act;
      if (a === 'copy') copyText(report(), e.target);
      else if (a === 'clear') { errors = []; var b = document.getElementById('st-bug'); if (b) b.remove(); ov.remove(); }
      else if (a === 'close' || e.target === ov) ov.remove();
    };
    document.body.appendChild(ov);
  }
  window.addEventListener('error', function (e) { push('오류', e.message || (e.error && e.error.message) || String(e), (e.filename || '') + ':' + (e.lineno || '') + ':' + (e.colno || '')); });
  window.addEventListener('unhandledrejection', function (e) { var r = e.reason; push('Promise', (r && r.message) || String(r), r && r.stack ? r.stack.split('\n')[1] : ''); });
  var _ce = console.error.bind(console);
  console.error = function () { push('console', Array.prototype.map.call(arguments, function (a) { return a && a.message ? a.message : (typeof a === 'object' ? JSON.stringify(a) : String(a)); }).join(' ')); _ce.apply(console, arguments); };

  /* ---------- 밖에서 쓰는 것 ---------- */
  window.Status = {
    app: APP, version: VER, kstNow: kstNow, kstStr: kstStr,
    reload: loadStatus,
    log: function (msg) { push('앱', msg); },                          // 앱이 직접 오류를 올릴 때
    report: report,
    // 자가 점검용: 가짜 status 로 띠를 그려 보고, 가짜 오류를 던져 본다
    selfTest: function () {
      showBand('fail', '자가 점검 — 이 띠가 보이면 경고 띠 정상', [{ name: '테스트', statusText: '실패(가짜)', ran: new Date().toISOString(), cause: '자가 점검이 일부러 만든 실패', fix: '아무것도 안 해도 됨. 새로고침하면 사라짐' }]);
      push('테스트', '자가 점검이 만든 가짜 오류', 'selfTest');
      return errors.length > 0 && !!document.getElementById('st-band');
    }
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', loadStatus); else loadStatus();
})();
