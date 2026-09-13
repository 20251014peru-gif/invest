export const RELEASE={version:'v017-20260913-231726-KST',at:'2026-09-13T14:17:26Z',summary:'CPI 3페이지 기본 보기 · 근거 연결 · 기록보관실 저장'};
export const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function safeUrl(value){try{const u=new URL(value);return ['https:','http:'].includes(u.protocol)?u.href:'';}catch{return '';}}
export function koreanTime(value){return new Intl.DateTimeFormat('ko-KR',{timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(value));}
export function koreanDate(value=Date.now()){const p=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date(value));const get=t=>p.find(x=>x.type===t).value;return `${get('year')}-${get('month')}-${get('day')}`;}
export function openPage(state,id){const pages=state.pages.slice();if(!pages.includes(id)){if(pages.length<3)pages.push(id);else pages[2]=id;}return {...state,pages,active:id,full:null};}
export function closePage(state,id){const pages=state.pages.filter(x=>x!==id);if(!pages.length)pages.push('summary');return {...state,pages,active:pages.at(-1),full:null};}
export function visiblePages(state,width){if(state.full)return [state.full];if(width<700)return [state.active];if(width<1100&&state.pages.length===3){return state.pages.filter(x=>x!==state.active).slice(-1).concat(state.active);}return state.pages;}
export function recordFingerprint(record){if(!record)return null;return JSON.stringify(['title','body','userJudgment','oneLiner','researchEvidence','researchRevision'].map(k=>record[k]??null));}
export function buildRecord(draft,data,now=Date.now()){
  if(!draft.title?.trim()||!draft.body?.trim())throw new Error('제목과 분석 내용을 입력해 주세요.');
  if(draft.body.length>20000)throw new Error('분석은 20,000자 이내로 작성해 주세요.');
  const ids=new Set(draft.evidence||[]);const sources=data.evidence.filter(x=>ids.has(x.id)).map(x=>({...x,sourceUrl:data.sourceUrl,period:data.period,publishedAt:data.publishedAt}));
  return {kind:'idea',schemaVer:2,title:draft.title.trim(),body:draft.body,userJudgment:draft.body,oneLiner:draft.oneLiner?.trim()||'',date:koreanDate(now),channel:'투자 통합분석실',topics:['CPI','미국 물가'],source:{name:data.sourceName,url:data.sourceUrl},link:data.sourceUrl,stocks:[],checks:[],star:0,researchTopicId:'us-cpi',researchEvidence:sources,researchReleasePeriod:data.period,updatedAt:now};
}
export function revisionPatch(current,patch,expected,now){
  if(recordFingerprint(current)!==expected)throw new Error('CONFLICT');
  const history=current?[...(current.researchHistory||[]),{at:now,title:current.title||'',body:current.body||'',userJudgment:current.userJudgment||'',researchEvidence:current.researchEvidence||[]}]:[];
  const owned=['title','body','userJudgment','oneLiner','researchEvidence','updatedAt'];
  const content=current?{...current,...Object.fromEntries(owned.map(k=>[k,patch[k]]))}:patch;
  return {...content,createdAt:current?.createdAt||now,researchRevision:(current?.researchRevision||0)+1,researchHistory:history};
}
export function validateData(data){if(data?.schema!=='research-cpi/1'||!/^\d{4}-\d{2}$/.test(data.period)||!safeUrl(data.sourceUrl)||!Array.isArray(data.points)||!data.points.length)throw new Error('CPI 자료 형식을 확인할 수 없습니다.');for(const s of ['all','core']){for(const key of ['yoy','previousYoy','mom','previousMom'])if(!Number.isFinite(data.series?.[s]?.[key]))throw new Error('CPI 수치가 누락됐습니다.');}if(!data.points.every(p=>/^\d{4}-\d{2}$/.test(p.period)&&Number.isFinite(p.all)&&Number.isFinite(p.core)))throw new Error('기간별 수치를 확인할 수 없습니다.');return data;}
