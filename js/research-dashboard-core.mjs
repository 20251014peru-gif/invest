import {safeUrl} from './research-core.mjs';
export const DASH_RELEASE={version:'v021-20260914-064309-KST',summary:'통합 3페이지 작업공간 · 뉴스 목록 · 그래프·분석 내부 연결'};
export const KINDS={indicator:'지표',news:'뉴스',idea:'분석',memo:'메모',chart:'차트',youtube:'유튜브',study:'공부노트',record:'기록'};
export const VIEWS={card:'카드',list:'목록',table:'표',board:'종류 보드',topic:'주제별',calendar:'달력',timeline:'타임라인',gallery:'갤러리'};
export const strings=v=>Array.isArray(v)?v.filter(x=>typeof x==='string'&&x.trim()):[];
export const finite=v=>typeof v==='number'&&Number.isFinite(v);
export function trustedRow(r){return r.official===true&&['ecos','fred','fred(예비)'].includes(r.source)&&!r.error&&!r.pending;}
export function periodPoints(r,store){const s=store?.items?.[r.id];if(!trustedRow(r)||!s||!safeUrl(s.source_url)||s.symbol!==r.symbol||s.unit!==r.unit)return [];
 const rows=(s.points||[]).filter(p=>finite(p.value)&&/^\d{4}-\d{2}(-\d{2})?$/.test(p.period||''));
 return [...new Map(rows.map(p=>[r.cycle==='M'?p.period.slice(0,7):p.period,{period:r.cycle==='M'?p.period.slice(0,7):p.period,value:p.value}])).values()].sort((a,b)=>a.period.localeCompare(b.period));}
export function indicators(defs,macro,extra,meta,periods){const merged=new Map([...(defs?.items||[]),...(defs?.derived||[]),...(extra?.items||[])].map(r=>[r.id,{...r}]));for(const r of [...(macro?.items||[]),...(extra?.items||[])])merged.set(r.id,{...merged.get(r.id),...r});
 return [...merged.values()].map(r=>{const m=meta?.items?.[r.id]||{},ok=trustedRow(r);const points=periodPoints(r,periods),group=meta?.groups?.find(g=>g.id===m.group)?.title||'미분류';const origin=r.source==='ecos'?'https://ecos.bok.or.kr/':r.source?.startsWith('fred')&&r.symbol?'https://fred.stlouisfed.org/series/'+encodeURIComponent(r.symbol):safeUrl(r.source_url)||safeUrl(m.source_url);return {key:'indicator:'+r.id,id:r.id,kind:'indicator',title:r.name||r.id,date:r.cycle==='M'?String(r.as_of||'').slice(0,7):r.as_of||'',topics:[group,r.name||r.id,...(['cpi_yoy','core_cpi_yoy'].includes(r.id)?['CPI']:[])],stocks:[],sourceName:r.source||'',sourceUrl:origin,summary:r.note||'',value:ok&&finite(r.value)?r.value:null,previous:ok&&finite(r.prev)?r.prev:null,unit:r.unit||'',status:ok?'공식 경로 수집값':'수치 확인 필요',points,raw:r,meta:m};});}
export function records(rows){return rows.filter(r=>r&&typeof r.id==='string').map(r=>({key:'record:'+r.id,id:r.id,kind:KINDS[r.kind]?r.kind:'record',title:r.title||'제목 없음',date:r.date||'',topics:strings(r.topics),stocks:strings(r.stocks),sourceName:r.source?.name||r.channel||'',sourceUrl:safeUrl(r.source?.url)||safeUrl(r.link),summary:r.oneLiner||'',raw:r}));}
export function filterItems(rows,{query='',kind='all',topic='all'}={}){const terms=query.toLocaleLowerCase().trim().split(/\s+/).filter(Boolean);return rows.filter(r=>(kind==='all'||r.kind===kind)&&(topic==='all'||r.topics.includes(topic))&&terms.every(t=>[r.title,r.summary,r.sourceName,...r.topics,...r.stocks].join(' ').toLocaleLowerCase().includes(t)));}
export function related(item,rows){return rows.filter(r=>r.key!==item.key&&(r.topics.some(t=>item.topics.includes(t))||r.stocks.some(t=>item.stocks.includes(t))));}
export function dateKey(item){return /^\d{4}-\d{2}-\d{2}$/.test(item.date)?item.date:'';}
export function calendarRows(rows,month){return {dated:rows.filter(r=>dateKey(r).startsWith(month)&&dateKey(r)),undated:rows.filter(r=>!dateKey(r))};}
export function parseSelection(hash){try{return decodeURIComponent(hash.replace(/^#/,''));}catch{return '';}}
export function groupItems(rows,key){const groups=new Map();for(const r of rows){const ks=key==='topic'?(r.topics.length?r.topics:['주제 미지정']):[KINDS[r.kind]];for(const k of ks){if(!groups.has(k))groups.set(k,[]);groups.get(k).push(r);}}return [...groups];}
