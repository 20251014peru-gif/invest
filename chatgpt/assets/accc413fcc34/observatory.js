import {esc,delta,series,hashRoute,judgment} from './core.js';
import {usable,readingHTML} from './lens.js';

export const FIXED=['kospi','sp500','sox','vix','usdkrw','us10y'];
export const TOPICS=[
  ['경기·고용',['ism_pmi','payems_chg','unrate','kr_lead','china_pmi']],
  ['물가',['cpi_yoy','core_pce_yoy','kr_cpi_yoy','ahe_yoy']],
  ['금리·채권',['bok_rate','fedfunds','us10y','us2y','kr3y','kr10y','spread_10_2']],
  ['신용·위험',['credit_spread','kr_aa3','kr_bbb3','vix']],
  ['한국시장·기업실적',['kospi','kosdaq','kr_export_yoy']],
  ['기타 선행지표·해외시장',[]]
];
export const topic=id=>TOPICS.find(([,ids])=>ids.includes(id))?.[0]||TOPICS.at(-1)[0];
const day=now=>new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit'}).format(now);
const age=(date,now)=>(Date.parse(day(now))-Date.parse(date))/86400000;
export function snapshotTrend(history,id,now=new Date()){
  const pts=series(history,id).filter(p=>age(p.date,now)>=0&&age(p.date,now)<5);
  return pts.length<2?'5일 내 수집 이력 부족':`5일 내 수집 흐름 ${pts.at(-1).value>pts[0].value?'↑':pts.at(-1).value<pts[0].value?'↓':'→'}`;
}
// 스냅샷의 변경 감지는 실제 발표일이나 예상치 서프라이즈가 아니다.
export function attention(r,history,now=new Date()){
  if(!usable(r,now)||r.missing)return {score:0,reason:'자료 확인 필요'};
  const d=delta(r);
  const threshold=r.unit==='%'||r.unit==='%p'?0.1:1.5;
  const magnitude=d?Math.abs(r.unit==='%'||r.unit==='%p'?d.diff:d.pct??0)/threshold:0;
  if(r.cycle==='D')return age(r.as_of,now)>=0&&age(r.as_of,now)<=4&&magnitude>=1
    ?{score:20+Math.min(magnitude,10),reason:'최근 관측값의 큰 변화'}:{score:0,reason:'시장 보완'};
  const pts=series(history,r.id).filter(p=>age(p.date,now)>=0);
  const last=pts.at(-1),prev=pts.at(-2);
  const changed=last&&prev&&last.value===r.value&&last.value!==prev.value&&age(last.date,now)<=2&&age(prev.date,now)<=4;
  return changed?{score:40+Math.min(magnitude,10),reason:'최근 수집 이력에서 값 변경 확인'}:{score:0,reason:'발표·변경 시점 확인 필요'};
}
export function marketBoard(items,history,now=new Date()){
  const map=new Map(items.map(r=>[r.id,r]));
  const fixed=FIXED.flatMap(id=>map.has(id)?[{row:map.get(id),reason:'고정 핵심',score:0}]:[]);
  const candidates=items.filter(r=>!FIXED.includes(r.id)).map(row=>({row,...attention(row,history,now)}));
  const promoted=candidates.filter(x=>x.score>0).sort((a,b)=>b.score-a.score||a.row.id.localeCompare(b.row.id)).slice(0,4);
  const selected=new Set([...fixed,...promoted].map(x=>x.row.id));
  const fallback=['credit_spread','kr10y','us2y','dxy','wti','kosdaq','nasdaq'];
  const target=Math.max(9,fixed.length+promoted.length);
  const extras=[...promoted];
  for(const id of fallback){const row=map.get(id);if(fixed.length+extras.length>=target)break;if(row&&!selected.has(id)&&usable(row,now)){extras.push({row,reason:'시장 보완',score:0});selected.add(id);}}
  return {fixed,extras,remaining:items.filter(r=>!selected.has(r.id))};
}
export function axes(items,now=new Date()){
  const defs=[['경기',['ism_pmi','payems_chg','unrate','kr_lead']],['물가',['cpi_yoy','core_pce_yoy','kr_cpi_yoy']],['금리',['us10y','us2y','bok_rate','fedfunds']],['신용',['credit_spread','kr_bbb3']],['시장',['kospi','sp500','sox','vix','usdkrw']]];
  return defs.map(([name,ids])=>{
    const rows=ids.map(id=>items.find(r=>r.id===id)).filter(r=>r&&usable(r,now)&&!r.missing);
    const valid=rows.filter(r=>judgment(r).label!=='판단 보류');
    const good=valid.filter(r=>judgment(r).cls==='good').length,bad=valid.filter(r=>['bad','warn'].includes(judgment(r).cls)).length;
    const label=valid.length<2?'확인 필요':good&&bad?'혼재':bad?'부담':good?'우호':'중립';
    return {name,rows,label,coverage:`${valid.length}/${ids.length}`,cls:label==='우호'?'good':label==='부담'?'bad':''};
  });
}
export function overviewHTML(items,history,now=new Date()){
  const rows=axes(items,now),board=marketBoard(items,history,now);
  const changes=[...board.fixed.map(x=>({...x,...attention(x.row,history,now)})),...board.extras].filter(x=>x.score>0).sort((a,b)=>b.score-a.score).slice(0,3);
  const conclusion=rows.some(x=>x.label==='확인 필요')?'일부 축은 자료 확인이 필요합니다.':rows.some(x=>x.label==='부담'||x.label==='혼재')?'우호 신호와 부담 요인을 함께 확인하세요.':'현재 설정 기준으로 중립·우호 신호가 관찰됩니다.';
  return `<div class="panel-head"><div><span class="tag">최근 자료 기준 · 잠정 해석</span><h2>오늘의 매크로 종합판정</h2></div><button data-ask="지표 전체가 말하는 상황과 엇갈리는 신호를 설명해줘">AI에 전체 질문</button></div><p>${conclusion}</p><div class="macro-axes">${rows.map(x=>`<details class="axis-tile ${x.cls}"><summary>${x.name}<strong>${x.label}</strong></summary><p class="muted">유효 자료 ${x.coverage} · 기존 설정 판정</p>${x.rows.map(r=>`<a href="${hashRoute('indicators',r.id)}">${esc(r.name)} · ${judgment(r).label}</a><span class="muted">기준 ${esc(r.as_of)}</span>`).join('')}</details>`).join('')}</div><div class="today-changes"><strong>주목할 변화</strong> ${changes.length?changes.map(x=>`<a href="${hashRoute('indicators',x.row.id)}">${esc(x.row.name)} ${esc(delta(x.row)?.text||'값 변경')}</a>`).join(' '):'<span class="muted">최신 자료에서 승격 기준에 해당하는 변화가 없습니다.</span>'}</div><p class="muted">서로 다른 기준일의 설정 판정을 요약합니다. 금리 하락·주가 상승만으로 경기 회복을 확정하지 않습니다.</p><details class="macro-background"><summary>종합 해석의 근거 · 좋아질/나빠질 조건</summary>${readingHTML(items)}</details>`;
}
