import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const src = path.resolve(here, '../../data/ai_pricing.json');
const outDir = path.resolve(here, '../generated');
const dst = path.join(outDir, 'ai_pricing.json');

if (!fs.existsSync(src)) throw new Error(`canonical pricing missing: ${src}`);
const pricing = JSON.parse(fs.readFileSync(src, 'utf8'));
if (pricing.schema !== 'ai_pricing/1' || pricing.provider !== 'anthropic') {
  throw new Error('unexpected ai_pricing schema/provider');
}
fs.mkdirSync(outDir, {recursive: true});
fs.writeFileSync(dst, JSON.stringify(pricing, null, 2) + '\n', 'utf8');
console.log(`synced ${pricing.schema} verifiedAt=${pricing.verifiedAt}`);
