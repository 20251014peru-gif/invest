// 공부노트 브라우저 시험 서버: node tests/study-browser/server.cjs [포트]
// records.html 의 Firebase SDK 를 시험 대역(firebase-mock.js)으로 바꿔서 제공한다 — 운영 데이터에 접속하지 않음.
// /__test/markflow.html : 옆 저장소(20251014peru-gif.github.io)의 실제 MarkFlow (환경변수 MARKFLOW_DIR)
const http = require('node:http'), fs = require('node:fs'), path = require('node:path');
const ROOT = path.resolve(__dirname, '../..');
const MF = process.env.MARKFLOW_DIR || path.resolve(ROOT, '../site');
const PORT = Number(process.argv[2] || 8123), EXT_PORT = PORT + 1;
const TYPES = {'.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.json': 'application/json; charset=utf-8', '.png': 'image/png', '.jpg': 'image/jpeg', '.svg': 'image/svg+xml', '.md': 'text/markdown; charset=utf-8'};
const files = new Map();
const PNG = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAIAAABLbSncAAAAGElEQVR4nGP4z8DwnwEPYBhVSFUhAAB0Hv8Bx5tH3wAAAABJRU5ErkJggg==', 'base64');
function send(res, code, body, type, extra = {}) { res.writeHead(code, {'content-type': type || 'text/plain; charset=utf-8', 'cache-control': 'no-store', ...extra}); res.end(body); }
http.createServer((req, res) => {
  const u = new URL(req.url, 'http://localhost');
  if (u.pathname === '/__test/upload' && req.method === 'POST') {
    const chunks = []; req.on('data', c => chunks.push(c)); req.on('end', () => {
      const id = files.size + 1; files.set(String(id), {type: req.headers['content-type'], body: Buffer.concat(chunks), path: u.searchParams.get('path')});
      send(res, 200, JSON.stringify({url: `http://localhost:${PORT}/__test/files/${id}`}), 'application/json');
    }); return;
  }
  if (u.pathname.startsWith('/__test/files/')) { const f = files.get(u.pathname.split('/').pop()); return f ? send(res, 200, f.body, f.type, {'access-control-allow-origin': '*'}) : send(res, 404, 'no'); }
  if (u.pathname === '/__test/uploads') return send(res, 200, JSON.stringify([...files].map(([k, v]) => ({id: k, path: v.path, size: v.body.length, type: v.type}))), 'application/json');
  let file;
  if (u.pathname.startsWith('/__test/markflow')) file = path.join(MF, u.pathname.replace('/__test/', ''));
  else if (u.pathname === '/__test/firebase-mock.js') file = path.join(__dirname, 'firebase-mock.js');
  else file = path.join(ROOT, decodeURIComponent(u.pathname === '/' ? '/records.html' : u.pathname));
  if (!file.startsWith(ROOT) && !file.startsWith(MF)) return send(res, 403, 'no');
  fs.readFile(file, (err, buf) => {
    if (err) return send(res, 404, 'not found');
    const ext = path.extname(file);
    if (/records\.html$/.test(file)) {
      let html = buf.toString('utf8');
      const before = html;
      html = html.replace(/<script src="https:\/\/www\.gstatic\.com\/firebasejs\/[^"]+"><\/script>\s*/g, '');
      if (html === before) return send(res, 500, 'firebase script tags not found');
      html = html.replace(/<script>(\r?\n)\/\* ══/, (m, nl) => '<script src="/__test/firebase-mock.js"></script>' + nl + m);
      return send(res, 200, html, TYPES['.html']);
    }
    send(res, 200, buf, TYPES[ext] || 'application/octet-stream');
  });
}).listen(PORT, () => console.log('study test server http://localhost:' + PORT));
// 외부 이미지 서버(다른 출처): /nocors.png 는 CORS 헤더 없음(복사 불가), /cors.png 는 허용
http.createServer((req, res) => {
  if (req.url.startsWith('/cors.png')) return send(res, 200, PNG, 'image/png', {'access-control-allow-origin': '*'});
  if (req.url.startsWith('/nocors.png')) return send(res, 200, PNG, 'image/png');
  send(res, 404, 'no');
}).listen(EXT_PORT, () => console.log('external image server http://localhost:' + EXT_PORT));
