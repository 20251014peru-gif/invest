import {build} from 'esbuild';
import {readFileSync, writeFileSync, mkdirSync} from 'node:fs';
const out = new URL('../../js/study/vendor/study-editor-vendor.mjs', import.meta.url);
mkdirSync(new URL('.', out), {recursive: true});
const pkg = JSON.parse(readFileSync(new URL('./package.json', import.meta.url)));
const r = await build({entryPoints: [new URL('./entry.mjs', import.meta.url).pathname.replace(/^\/(\w:)/, '$1')], bundle: true, format: 'esm', minify: true, target: 'es2020', write: false, legalComments: 'eof'});
const banner = `/* study-editor-vendor — tools/study-editor 에서 생성(직접 수정 금지). ${Object.entries(pkg.devDependencies).filter(([k]) => k !== 'esbuild').map(([k, v]) => k + '@' + v).join(', ')} · 라이선스: MIT (각 패키지) */\n`;
writeFileSync(out, banner + r.outputFiles[0].text);
console.log('bytes', r.outputFiles[0].contents.length);
