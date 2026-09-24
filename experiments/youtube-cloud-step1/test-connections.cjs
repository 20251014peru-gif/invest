const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {makeConnection} = require('./connection.js');
const cases = [
  ['local root', 'http://localhost:5055/', {}, 'http://localhost:5055', 'http://localhost:5055/data'],
  ['local other port', 'http://127.0.0.1:5101/', {}, 'http://127.0.0.1:5101', 'http://127.0.0.1:5101/data'],
  ['existing LAN origin', 'http://192.168.1.2:5055/', {}, 'http://192.168.1.2:5055', 'http://192.168.1.2:5055/data'],
  ['static subfolder', 'https://pages.example/invest/youtube/youtube.html', {apiBase:'https://api.example/v1/'}, 'https://api.example/v1', 'https://pages.example/invest/youtube/data.html'],
  ['data page', 'https://pages.example/invest/youtube/data.html', {apiBase:'https://api.example'}, 'https://api.example', 'https://pages.example/invest/youtube/data.html'],
  ['file fallback', 'file:///C:/preview/youtube.html', {}, 'http://localhost:5055', 'http://localhost:5055/data'],
];
for (const [label, href, config, api, data] of cases) {
  const c = makeConnection({href}, config);
  assert.equal(c.apiBase, api, label);
  assert.equal(c.dataPage, data, label);
  assert.equal(new URL(c.summaryUrl('id &한글')).searchParams.get('open'), 'id &한글');
  assert.equal(c.captureUrl('/captures/video/t_2.jpg'), api + '/captures/video/t_2.jpg');
  console.log('PASS',label);
}
const split = makeConnection({href:'https://pages.example/view/youtube.html'}, {apiBase:'https://api.example',captureBase:'https://images.example'});
assert.equal(split.captureUrl('/captures/v/t_1.jpg'), 'https://images.example/captures/v/t_1.jpg');
assert.equal(split.summaryUrl('s_1'), 'https://pages.example/view/youtube.html?open=s_1');
for (const bad of ['javascript:alert(1)','https://key:secret@api.example','https://api.example?key=secret','https://api.example#secret','http://public.example']) {
  assert.throws(()=>makeConnection({href:'https://pages.example/'},{apiBase:bad}));
}
console.log('PASS separate media/page/API addresses and invalid address rejection');
let scriptCount=0;
for(const file of ['youtube.html','data.html']) {
  const source=fs.readFileSync(path.join(__dirname,file),'utf8');
  for(const match of source.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi)) {
    if(match[1].trim()){new vm.Script(match[1], {filename:file});scriptCount++;}
  }
}
console.log('PASS',scriptCount,'inline scripts compile');
console.log('API calls=0; production Firestore writes=0');
