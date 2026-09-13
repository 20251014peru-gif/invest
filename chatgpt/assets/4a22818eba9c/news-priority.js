import {esc,hashRoute,kst} from './core.js';
export const NEWS_AREAS=['이익 전망','산업 변화','정책·자금'];
const rules=[
 ['이익 전망',/실적|영업이익|순이익|매출|가이던스|판매가격|판가|원가|수주|공급계약|계약.{0,8}취소/,/상향|하향|늘|줄|증가|감소|인상|인하|체결|취소|해지|수주|적자|흑자|갱신/,'매출·이익 또는 계약 조건의 변화'],
 ['산업 변화',/설비|시설투자|시설 투자|설비투자|설비 투자|투자 확대|투자 축소|투자 감축|증설|공장|생산능력|공급 부족|공급부족|재고|양산|기술 전환|기술전환|수율|인수|합병|점유율/,/확대|축소|증설|착공|가동|중단|재개|양산|전환|부족|인수|합병|투자|취소|감축/,'투자·생산·경쟁 구조의 변화'],
 ['정책·자금',/관세|수출.{0,5}규제|수출.{0,5}통제|보조금|기준금리|정책금리|연준|한국은행|중앙은행|양적.{0,3}긴축|유동성|자금.{0,4}유출|자금.{0,4}유입/,/시행|발효|확정|승인|인상|인하|동결|철회|유예|규제|통제|축소|확대|유출|유입|결정/,'정책·조달 비용·자금 이동의 변화']
];
const tentative=/검토|추진|예정|계획|가능성|전망|예상|기대|협의|논의|목표|것으로|할 수/;
const executed=/공시|체결|확정|승인|발효|시행|착공|가동|완료|취소|해지|발표했|발표한|집계|기록했/;
const metric=/(?:\d[\d,.]*\s*(?:조|억|만)?\s*(?:원|달러|%p?|배|톤|대|개|bp))|(?:전년|전분기|직전|대비).{0,20}(?:상향|하향|증가|감소)/i;
const titleNoise=/추천주|급등주|테마주|목표주가|목표가|주가.{0,5}(?:급등|급락)|상한가|하한가|특징주|마감시황|마감 시황/;
export function assessNews(n,now=Date.now()){
 const title=n.title||'',body=n.body||'';
 const sentences=(title+'\n'+body).split(/\n+|(?<=[.!?。])\s+/).map(s=>s.trim()).filter(Boolean);
 const hits=rules.map(([area,subject,action,why])=>{
   const matches=sentences.filter(s=>subject.test(s)&&action.test(s));
   const sentence=matches.sort((a,b)=>Number(metric.test(b))-Number(metric.test(a))||Number(executed.test(b)&&!tentative.test(b))-Number(executed.test(a)&&!tentative.test(a)))[0];
   return sentence?{area,why,sentence}:null;
 }).filter(Boolean);
 const primary=hits.find(h=>rules.find(r=>r[0]===h.area)[1].test(title))||hits[0];
 const quote=primary?.sentence||'';
 const revised=/(?:전망|예상|가이던스|컨센서스).{0,60}(?:상향|하향).{0,12}(?:조정됐|조정했|조정된|발표|공시)/.test(quote);
 const negated=/(?:체결|확정|시행|가동|완료|승인).{0,8}(?:않|아니|미정)|미확정|미체결/.test(quote);
 const concrete=metric.test(quote),uncertain=negated||(/검토|추진|예정|계획|가능성|기대|협의|논의|목표|할 수/.test(quote))||(!revised&&tentative.test(quote)),actual=(executed.test(quote)||revised)&&!uncertain;
 const age=n.time?(now-n.time)/3600000:null,fresh=age!==null&&age>=-1&&age<=72;
 const enough=body.trim().length>=180;
 const promotion=/상장설|루머|찌라시|베팅|불법 투자|투자 권유|은퇴|연금자산|IRP|적금|이벤트|프로모션|설명회/.test(title);
 const noise=titleNoise.test(title)||promotion;
 const titleRelated=!!primary&&rules.some(([area,re])=>area===primary.area&&re.test(title));
 const tier=primary&&concrete&&actual&&fresh&&enough&&!noise&&titleRelated?'먼저 분석':primary&&!promotion?'후속 확인':'간단히 보기';
 const stage=!primary?'변화 근거 미포착':uncertain?'계획·전망 표현':actual?'발표·실행 표현':'단계 확인 필요';
 const reasons=primary?[primary.why,concrete?'변화 문장에 수치·비교 기준 포함':'영향 규모 확인 필요',stage]:['세 분야의 구체적인 변화 문장을 찾지 못함'];
 if(primary&&!fresh)reasons.push(age===null?'기사 시각 확인 필요':age< -1?'미래 시각 확인 필요':'72시간 이전 기사');
 if(primary&&!enough)reasons.push('본문이 짧아 원문 확인 필요');if(noise)reasons.push(promotion?'루머·상품·홍보 중심 제목은 별도 확인':'주가·추천 중심 제목은 우선 승격 제외');
 return {n,areas:hits.map(h=>h.area),tier,stage,quote,reasons,score:(tier==='먼저 분석'?100:tier==='후속 확인'?40:0)+(concrete?8:0)+(actual?4:0)};
}
const key=n=>(n.title||'').replace(/\[[^\]]*\]|\([^)]*\)/g,'').replace(/[^\p{L}\p{N}]/gu,'').toLowerCase();
export function prioritizeNews(news,now=Date.now()){
 const groups=new Map();for(const n of news){const k=key(n)||n.id;const list=groups.get(k)||[];list.push(n);groups.set(k,list);}
 return [...groups.values()].map(list=>{const assessed=list.map(n=>assessNews(n,now)).sort((a,b)=>(b.n.body||'').length-(a.n.body||'').length||b.n.time-a.n.time);return {...assessed[0],duplicates:list.filter(n=>n.id!==assessed[0].n.id)};}).sort((a,b)=>b.score-a.score||b.n.time-a.n.time||a.n.id.localeCompare(b.n.id));
}
export function deepFocus(n){const a=assessNews(n);return `투자 중요 뉴스 심층 해설. 분야: ${a.areas.join('·')||'변화 확인'}. 규칙 선별은 분석 후보일 뿐 확정 판단이 아니야. 기사에서 새로 바뀐 사실을 먼저 찾고, 직접 영향을 받는 기업·업종의 매출·원가·마진에 어떻게 연결되는지 설명해. 금액은 기업 매출 대비 비중·계약 기간·집행 규모 등 비교 근거가 있을 때만 크기를 평가해. 발표·검토·계약·실제 집행과 영향 발생 시점을 구분해. 수주면 취소 조건과 수익성, 투자면 가동·양산 조건, 정책이면 대상·시행일·예외 중 관련된 내용을 확인해. 기사에 없는 항목은 미확인으로 남겨. 과거 기사나 예상치가 없으면 새로운 사건·서프라이즈·주가 반영 여부를 단정하지 마. 해설형 3~4문단을 유지하고 마지막에 가장 중요한 확인 조건을 짚어줘.`;}
export function priorityHTML(news,{area='전체',tier='전체',now=Date.now()}={}){
 const all=prioritizeNews(news,now),rows=all.filter(x=>(area==='전체'||x.areas.includes(area))&&(tier==='전체'||x.tier===tier));
 const selected=rows.filter(x=>x.tier!=='간단히 보기').slice(0,12);
 return `<section class="news-priority panel"><h2>투자 판단에 중요한 뉴스</h2><p>이익 전망 · 산업 변화 · 정책과 자금 흐름</p><p class="muted">수집 텍스트의 변화 표현·수치·실행 단계로 고른 후보입니다. 중요도는 매수 추천이 아니며, 새 사건인지와 영향 규모는 심층 해설에서 확인합니다.</p><div class="priority-news-filters"><label>관심 분야 <select id="investment-area">${['전체',...NEWS_AREAS].map(s=>`<option${s===area?' selected':''}>${s}</option>`).join('')}</select></label><label>확인 순서 <select id="investment-tier">${['전체','먼저 분석','후속 확인','간단히 보기'].map(s=>`<option${s===tier?' selected':''}>${s}</option>`).join('')}</select></label></div><p class="muted">먼저 분석 ${all.filter(x=>x.tier==='먼저 분석').length} · 후속 확인 ${all.filter(x=>x.tier==='후속 확인').length} · 간단히 보기 ${all.filter(x=>x.tier==='간단히 보기').length} · 제목 중복 묶음 기준</p>${(tier==='간단히 보기'?rows.slice(0,12):selected).map(x=>`<article class="investment-news"><div class="pill-row"><span class="tag">${x.tier}</span><span>${esc(x.areas.join(' · ')||'기타')}</span><span class="muted">${esc(x.n.time?kst(x.n.time):'시각 확인 필요')}</span></div><h3><a href="${hashRoute('news',x.n.id)}">${esc(x.n.title)}</a></h3><p class="selection-reason">선별 이유 · ${esc(x.reasons.join(' · '))}</p>${x.quote?`<details><summary>어떤 문장에서 골랐나요?</summary><p>${esc(x.quote)}</p><p class="muted">기사의 주장입니다. 독립 검증된 사실이나 기업 전체의 실행 단계를 뜻하지 않습니다.</p></details>`:''}<div class="pill-row"><button data-deep-news="${esc(x.n.id)}">투자 영향 심층 해설</button><button data-ai-news="${esc(x.n.id)}">짧게 읽기</button></div>${x.duplicates.length?`<details><summary>같은 제목 보도 ${x.duplicates.length}건</summary>${x.duplicates.map(n=>`<p><a href="${hashRoute('news',n.id)}">${esc(n.title)}</a> · ${esc(n.source)}</p>`).join('')}</details>`:''}</article>`).join('')||'<p>이 조건에 맞는 후보가 없습니다. 아래 전체 뉴스는 그대로 볼 수 있습니다.</p>'}<p class="muted">후보는 최대 12개 표시합니다. 같은 제목만 묶으며 유사 사건 전체의 중복 여부는 아직 판단하지 않습니다.</p><details><summary>선별 기준</summary><p>먼저 분석: 최근 72시간, 본문 180자 이상, 같은 변화 문장에 수치·비교와 발표·실행 표현이 있고 불확실한 계획 표현이 없고 제목도 해당 분야와 관련된 기사입니다. 전망치의 실제 상향·하향 조정은 포함합니다. 그 외 변화 후보는 후속 확인, 루머·상품·홍보 중심 제목은 간단히 보기로 분류합니다. 제목의 주가 급등·추천 표현만으로는 승격하지 않습니다. 기업 대비 영향 규모와 과거 대비 신규성은 이 규칙만으로 확정하지 않습니다.</p></details></section>`;
}
