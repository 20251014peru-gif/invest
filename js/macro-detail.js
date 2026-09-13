(function(root){
'use strict';
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num=v=>typeof v==='number'&&Number.isFinite(v);
const fmt=v=>num(v)?v.toLocaleString('ko-KR',{maximumFractionDigits:3}):'—';
const url=v=>{try{const u=new URL(v);return u.protocol==='https:'?u.href:'';}catch{return '';}};
const link=(u,t)=>url(u)?`<a href="${esc(url(u))}" target="_blank" rel="noopener noreferrer">${esc(t)} ↗</a>`:'';
function baseline(m){const b=m?.benchmark;return b?.verified_official===true&&num(b.value)&&url(b.source_url)&&b.label?b:null;}
function validEvent(e){return e?.verified_official===true&&url(e.source_url)&&/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(Z|[+-]\d{2}:\d{2})$/.test(e.at)&&Number.isFinite(Date.parse(e.at));}
function releases(r,calendar,now=Date.now()){
  const events=(calendar?.events||[]).filter(e=>e.ids?.includes(r.id)&&validEvent(e)).sort((a,b)=>Date.parse(a.at)-Date.parse(b.at));
  const period=r.cycle==='M'?String(r.as_of||'').slice(0,7):r.as_of;
  const past=events.filter(e=>e.status==='released'&&Date.parse(e.at)<=now);
  return {current:past.filter(e=>e.period===period).at(-1)||null,latest:past.at(-1)||null,next:events.find(e=>Date.parse(e.at)>now)||null};
}
function eventText(e){if(!e)return '공식 일정 미확인';return new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(e.at))+' KST';}
function eventHTML(e){if(!e)return '공식 일정 미확인';const local=e.timezone?new Intl.DateTimeFormat('sv-SE',{timeZone:e.timezone,dateStyle:'short',timeStyle:'short'}).format(new Date(e.at))+' '+e.timezone:'원 시간대 미확인';return link(e.source_url,eventText(e))+`<small>${esc(e.period||'')} 자료 · ${esc(local)}</small>`;}
function points(r,series){
  const stored=series?.items?.[r.id];
  const source=stored?.points||r.observations||[];
  const rows=source.filter(p=>num(p.value)&&/^\d{4}-\d{2}(-\d{2})?$/.test(p.period||'')).map(p=>({period:r.cycle==='M'?p.period.slice(0,7):p.period,value:p.value}));
  // A known observation date can seed one bar; previous dates are never inferred.
  if(!rows.length&&num(r.value)&&r.as_of&&['fred','fred(예비)','ecos'].includes(r.source))rows.push({period:r.cycle==='M'?r.as_of.slice(0,7):r.as_of,value:r.value});
  return [...new Map(rows.map(p=>[p.period,p])).values()].sort((a,b)=>a.period.localeCompare(b.period));
}
function withPeriodValues(r,series){
  const data=series?.items?.[r.id],ps=data?.points;
  if(!ps?.length||!url(data.source_url)||data.symbol!==r.symbol||data.unit!==r.unit||!num(ps.at(-1).value)||!(Date.parse(data.collected_at)>Date.parse(r.collected_at||'')))return r;
  const latest=ps.at(-1),previous=ps.at(-2);
  if(String(latest.period).slice(0,7)<String(r.as_of||'').slice(0,7))return r;
  return {...r,value:latest.value,prev:previous?.value??null,as_of:latest.period,collected_at:data.collected_at,source:'fred',error:'',pending:false,judge:Math.abs(latest.value-r.value)>.005?'':r.judge,original_value:r.value,original_as_of:r.as_of,period_source:data.source_url,change_pct:previous?.value?(latest.value/previous.value-1)*100:null,change:previous?latest.value-previous.value:null};
}
function bars(rows,b,unit=''){
  if(!rows.length)return '<p>기준기간이 확인된 값이 없습니다. 수집일 스냅샷을 발표 이력으로 바꾸지 않습니다.</p>';
  const lo=Math.min(0,...rows.map(p=>p.value),b?.value??0),hi=Math.max(0,...rows.map(p=>p.value),b?.value??0);
  const span=hi-lo||1,min=lo<0?lo-span*.08:0,max=hi>0?hi+span*.16:1;
  const w=Math.max(680,rows.length*56+100),h=290,left=65,top=30,bottom=230,step=(w-left-20)/rows.length;
  const y=v=>top+(max-v)/(max-min)*(bottom-top),zero=y(0);
  let svg='';for(let i=0;i<=4;i++){const v=min+(max-min)*i/4,yy=y(v);svg+=`<line x1="${left}" x2="${w-20}" y1="${yy}" y2="${yy}" stroke="#e5e7eb"/><text x="${left-8}" y="${yy+5}" text-anchor="end" font-size="14">${fmt(v)}</text>`;}
  rows.forEach((p,i)=>{const x=left+i*step+step*.2,yy=y(p.value);svg+=`<rect x="${x}" y="${Math.min(yy,zero)}" width="${step*.6}" height="${Math.abs(yy-zero)}" fill="${i===rows.length-1?'#4338ca':'#a5b4fc'}"><title>${esc(p.period)}: ${fmt(p.value)} ${esc(unit)}</title></rect><text x="${x+step*.3}" y="${p.value>=0?yy-7:yy+18}" text-anchor="middle" font-size="14">${fmt(p.value)}</text><text transform="translate(${x+step*.3},${bottom+22}) rotate(-25)" text-anchor="end" font-size="13">${esc(p.period)}</text>`;});
  if(b)svg+=`<line data-official-baseline="true" x1="${left}" x2="${w-20}" y1="${y(b.value)}" y2="${y(b.value)}" stroke="#b45309" stroke-width="2" stroke-dasharray="6 4"/><text x="${left+8}" y="${y(b.value)-8}" font-size="14" fill="#92400e">${esc(b.label)}</text>`;
  return `<div class="period-scroll"><svg role="img" aria-label="기간별 값 막대그래프 · ${esc(unit)}" viewBox="0 0 ${w} ${h}" style="width:${w}px;min-width:100%;height:290px">${svg}</svg></div><p class="period-note">가로축: 원자료 기준기간 · 세로축: ${esc(unit||'원자료 단위')} · 막대 시작점 0은 값의 크기를 나타내며 경제적 중립 판정이 아닙니다.</p>`;
}
function summary(r,m,calendar,series){const b=baseline(m),ev=releases(r,calendar),p=points(r,series),stored=series?.items?.[r.id];let cells=[['최근 수집값',fmt(r.value)+' '+esc(r.unit||'')],['이전 수집값',fmt(r.prev)+' '+esc(r.unit||'')],['공식 기준선',b?link(b.source_url,b.label):'확인된 공식 기준선 없음'],['자료 기준기간',esc(r.cycle==='M'?String(r.as_of||'—').slice(0,7):r.as_of||'—')],['해당 자료 발표일',eventHTML(ev.current)],['다음 공식 발표일',eventHTML(ev.next)]];
  const mismatch=stored&&p.length&&(p.at(-1).period!==(r.cycle==='M'?String(r.as_of).slice(0,7):r.as_of)||Math.abs(p.at(-1).value-r.value)>.005);
  return `<div class="period-summary">${cells.map(([k,v])=>`<div><span>${k}</span><strong>${v}</strong></div>`).join('')}</div>${!ev.current&&ev.latest?`<p>최근 확인된 공식 발표: ${eventHTML(ev.latest)} · 현재 수집값의 기준기간과 다릅니다.</p>`:''}${r.original_value!==undefined&&Math.abs(r.original_value-r.value)>.005?`<p>기존 수집본 ${fmt(r.original_value)} → 현재 원자료 계산 ${fmt(r.value)}. 같은 기준월 원자료로 계산했으며 과거 수집본은 보존됩니다.</p>`:''}${m?.benchmark_note?`<p>${esc(m.benchmark_note)}</p>`:''}${mismatch?'<p role="status">수집값과 차트 원자료의 기준기간 또는 값이 다릅니다. 각 출처·수집시각을 확인하세요.</p>':''}`;
}
function panel(r,m,calendar,series){const p=points(r,series),stored=series?.items?.[r.id];return `<section class="period-panel">${summary(r,m,calendar,series)}<h3>기간별 값 <small>${esc(r.unit||'')}</small></h3><label>표시 범위 <select data-period-range><option value="12">최근 12개 기간</option><option value="24">최근 24개 기간</option><option value="0">전체 수집 기간</option></select></label><div data-period-chart>${bars(p.slice(-12),baseline(m),r.unit)}</div><p>${stored?link(stored.source_url,'차트 원자료')+' · '+esc(stored.formula||'원자료 값')+' · 수집 '+esc(stored.collected_at):'확인된 기준기간 '+p.length+'개 · 이전값의 기준기간 미확인 시 막대를 만들지 않습니다.'}</p><details><summary>기간별 수치 표</summary><table><thead><tr><th>기준기간</th><th>값</th></tr></thead><tbody>${p.slice().reverse().map(x=>`<tr><td>${esc(x.period)}</td><td>${fmt(x.value)} ${esc(r.unit||'')}</td></tr>`).join('')}</tbody></table></details></section>`;}
function bind(host,r,m,series){const select=host.querySelector('[data-period-range]');if(select)select.onchange=()=>{const p=points(r,series),n=Number(select.value);host.querySelector('[data-period-chart]').innerHTML=bars(n?p.slice(-n):p,baseline(m),r.unit);};}
root.MacroDetail={baseline,releases,eventText,eventHTML,points,bars,summary,panel,bind,link,withPeriodValues};
})(globalThis);
