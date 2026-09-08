import {esc,safeUrl} from './core.js';
export function formatAnswer(raw,evidence,declared=[]){
 const known=new Map(evidence.map(e=>[e.id,e])),ordered=[];
 const add=id=>{if(known.has(id)&&!ordered.includes(id))ordered.push(id);};
 const marker=/\[\s*([INM]:[\w-]+)\s*\]/g;
 for(const m of raw.matchAll(marker))add(m[1]);for(const id of declared)add(id);
 const paragraphs=raw.split(/\n\s*\n/).map(p=>{
   const refs=new Set();let unknown=false;
   const text=p.replace(marker,(_,id)=>{if(known.has(id))refs.add(ordered.indexOf(id)+1);else unknown=true;return '';}).replace(/[ \t]+([.,。])/g,'$1').trim();
   return {text,refs:[...refs],unknown};
 });
 const html=paragraphs.map(p=>`<p>${esc(p.text)}${p.refs.map(n=>`<button type="button" class="source-ref" data-cite="${n}" aria-label="출처 ${n} 보기">[${n}]</button>`).join('')}${p.unknown?'<span class="muted"> [출처 확인 필요]</span>':''}</p>`).join('');
 const sources=ordered.map((id,i)=>{const e=known.get(id),u=safeUrl(e.url);return {...e,number:i+1,url:u};});
 const sourceHTML=sources.map(e=>`<p id="ai-source-${e.number}" tabindex="-1">[${e.number}] ${e.url?`<a href="${esc(e.url)}" target="_blank" rel="noopener noreferrer">${esc(e.title)}</a>`:esc(e.title)} · ${esc(e.asOf||'기준일은 상세 참조')}</p>`).join('');
 const plain=paragraphs.map(p=>p.text+p.refs.map(n=>` [${n}]`).join('')+(p.unknown?' [출처 확인 필요]':'')).join('\n\n')+(sources.length?'\n\n출처\n'+sources.map(e=>`[${e.number}] ${e.title}${e.url?' — '+e.url:''}`).join('\n'):'');
 return {html,sourceHTML,plain};
}
