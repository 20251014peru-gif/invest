import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
const root=path.dirname(fileURLToPath(import.meta.url));
const read=f=>fs.readFileSync(path.join(root,f),'utf8');
const release=JSON.parse(read('release.json'));
const modules=['app.js','core.js','catalog.js','chart.js','storage.js','lens.js','ai.js','notebook.js','observatory.js','chart-sources.js','live-chart.js','news-summary.js','answer-view.js','news-priority.js'];
const hash=createHash('sha256').update(modules.map(read).join('\n')+read('styles.css')).digest('hex').slice(0,12);
const dir=path.join(root,'assets',hash);fs.mkdirSync(dir,{recursive:true});
for(const name of modules)fs.writeFileSync(path.join(dir,name),read(name));
fs.writeFileSync(path.join(dir,'styles.css'),read('styles.css'));
let html=read('index.html').replace(/href="(?:assets\/[^/]+\/)?styles.css[^\"]*"/,`href="assets/${hash}/styles.css"`).replace(/src="(?:assets\/[^/]+\/)?app.js[^\"]*"/,`src="assets/${hash}/app.js"`);
// Modules fetch config and release relative to the document URL, not module URL.
fs.writeFileSync(path.join(root,'index.html'),html);
fs.writeFileSync(path.join(root,'build-manifest.json'),JSON.stringify({version:release.version,assets:hash},null,2)+'\n');
console.log(JSON.stringify({version:release.version,assets:hash}));
