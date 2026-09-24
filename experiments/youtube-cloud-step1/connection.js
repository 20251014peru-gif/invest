(function (root) {
  'use strict';
  function makeConnection(location, config) {
    config = config || {};
    var page = new URL(location.href);
    var local = page.protocol === 'file:';
    var fallback = local ? 'http://localhost:5055' : page.origin;
    function endpoint(value) {
      var u = new URL(value);
      var loopback = ['localhost', '127.0.0.1', '[::1]'].indexOf(u.hostname) >= 0;
      if (u.username || u.password || u.search || u.hash ||
          !(u.protocol === 'https:' || (u.protocol === 'http:' && (loopback || u.origin === page.origin)))) {
        throw new Error('서버 연결 주소를 확인하세요. HTTPS 또는 이 PC의 로컬 주소가 필요합니다.');
      }
      return u.href.replace(/\/+$/, '');
    }
    var apiBase = endpoint(config.apiBase || fallback);
    var captureBase = endpoint(config.captureBase || apiBase);
    // Flask의 /, /data 경로와 정적 호스팅의 youtube.html, data.html 경로를 모두 보존.
    var directory = new URL('.', page);
    var flaskPage = !local && (page.pathname === '/' || page.pathname === '/data');
    var summaryPage = local ? 'http://localhost:5055/' :
      (flaskPage ? page.origin + '/' : new URL('youtube.html', directory).href);
    var dataPage = local ? 'http://localhost:5055/data' :
      (flaskPage ? page.origin + '/data' : new URL('data.html', directory).href);
    return Object.freeze({
      apiBase: apiBase,
      captureBase: captureBase,
      dataPage: dataPage,
      summaryUrl: function (id) {
        var u = new URL(summaryPage);
        if (id) u.searchParams.set('open', id);
        return u.href;
      },
      captureUrl: function (path) {
        if (typeof path !== 'string' || !/^\/captures\//.test(path) || /[\\\r\n]/.test(path)) {
          throw new Error('캡처 이미지 경로를 확인하세요.');
        }
        return captureBase + path;
      }
    });
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = { makeConnection: makeConnection };
  if (root && root.location) root.YT_CONNECTION = makeConnection(root.location, root.YT_CONNECTION_CONFIG);
})(typeof window !== 'undefined' ? window : null);
