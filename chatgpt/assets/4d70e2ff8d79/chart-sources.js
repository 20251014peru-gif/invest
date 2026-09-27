import {esc,hashRoute} from './core.js';

// Explicit registry: do not substitute DXY with a broad dollar index, futures
// with spot prices, or changes with index levels. See docs/CHART-AUDIT.md.
const yahoo={usdkrw:'KRW=X',sp500:'^GSPC',nasdaq:'^IXIC',sox:'^SOX',vix:'^VIX',dxy:'DX-Y.NYB',hsi:'^HSI',wti:'CL=F',copper:'HG=F',gold:'GC=F',bdry:'BDRY'};
const fred={us10y:['DGS10','lin'],us2y:['DGS2','lin'],fedfunds:['FEDFUNDS','lin'],cpi_yoy:['CPIAUCSL','pc1'],core_pce_yoy:['PCEPILFE','pc1'],m2:['M2SL','lin'],fed_bs:['WALCL','lin'],payems_chg:['PAYEMS','chg'],unrate:['UNRATE','lin'],ahe_yoy:['CES0500000003','pc1'],spread_10_2:['T10Y2Y','lin']};
const ecos={bok_rate:'K051',kr3y:'K056',kr_aa3:'K057',kr_cpi_yoy:'K401',kr_lead:'K254',kr_export_yoy:'K358'};
// Generated using FRED's Custom Graph Link with automatic updates through latest.
// Plain graph ?id=...&units=pc1 silently reverted to levels in browser verification.
const transformed={cpi_yoy:'1Yh9Z',core_pce_yoy:'1Yha5',payems_chg:'1Yhab',ahe_yoy:'1Yhaw'};
const ecosURL=id=>'https://ecos.bok.or.kr/#/StatisticsByTheme/KoreanStat100/'+id;
export function chartSource(id){
  if(id==='kospi'||id==='kosdaq')return {url:'https://m.stock.naver.com/fchart/domestic/index/'+id.toUpperCase(),provider:'네이버 금융',kind:'chart',note:'국내 지수는 네이버 금융에서 확인합니다. 분봉·일봉·주봉·월봉과 확대·축소를 사용할 수 있습니다. 카드와 시세 기준 시각은 다를 수 있습니다.'};
  if(yahoo[id])return {url:'https://finance.yahoo.com/quote/'+encodeURIComponent(yahoo[id])+'/chart/',provider:'Yahoo Finance',kind:'chart',note:id==='usdkrw'?'시장 환율 차트입니다. 카드의 ECOS 매매기준율과 시각·값이 다를 수 있습니다.':id==='bdry'?'BDRY ETF 가격입니다. 발틱운임 원지수가 아닙니다.':['wti','copper','gold'].includes(id)?'카드와 같은 선물 종목입니다. 만기 교체에 따른 가격 차이가 있을 수 있습니다.':'웹 차트의 시세와 카드의 수집 기준 시각은 다를 수 있습니다.'};
  if(fred[id]){const [symbol,units]=fred[id];return {url:transformed[id]?'https://fred.stlouisfed.org/graph/?g='+transformed[id]:'https://fred.stlouisfed.org/series/'+symbol,provider:'FRED',kind:'chart',units,note:units==='pc1'?'전년 동월 대비 변화율(%)로 설정한 차트입니다.':units==='chg'?'고용자 수 수준이 아닌 전월 대비 증감(천명) 차트입니다.':'동일한 FRED 시계열의 장기 그래프입니다.'};}
  if(ecos[id])return {url:ecosURL(ecos[id]),provider:'한국은행 ECOS',kind:'chart',note:['kr_cpi_yoy','kr_export_yoy'].includes(id)?'공식 그래프에 원지수와 전년동기대비 증감률이 함께 표시됩니다. 카드와 비교할 때 증감률 축을 보세요.':id==='bok_rate'?'결정일 기준 금리 이력입니다. 카드의 월간 집계와 구분해 보세요.':'선택한 지표의 공식 차트·기간 조절 화면입니다.'};
  if(id==='kr10y')return {url:'https://www.investing.com/rates-bonds/south-korea-10-year-bond-yield-advanced-chart',provider:'Investing.com',kind:'chart',note:'한국 10년물 시장 수익률입니다. ECOS 고시 수익률과 시각·호가가 다를 수 있습니다.'};
  if(id==='ism_pmi'||id==='china_pmi')return {url:'https://tradingeconomics.com/'+(id==='ism_pmi'?'united-states':'china')+'/business-confidence',provider:'Trading Economics',kind:'chart',note:id==='ism_pmi'?'ISM 제조업 PMI입니다. S&P Global 제조업 PMI와 구분합니다.':'중국 국가통계국 NBS 제조업 PMI입니다. 민간 RatingDog PMI와 구분합니다.'};
  if(id==='credit_spread')return {url:ecosURL('K057'),provider:'한국은행 ECOS',kind:'components',note:'신용 스프레드 자체의 직접 차트 주소는 확인되지 않았습니다. AA- 회사채와 국고3년 차트를 각각 열어 비교합니다. 스프레드 = AA- 회사채 − 국고3년.',extra:[{url:ecosURL('K056'),label:'국고3년 차트'}]};
  if(id==='kr_bbb3')return {url:'https://ecos.bok.or.kr/#/SearchStat',provider:'한국은행 ECOS',kind:'selection',note:'BBB- 3년물은 공유 가능한 직접 차트 주소를 확보하지 못했습니다. ECOS에서 1.3.2.1 시장금리(일별) → 회사채(3년, BBB-) → 빠른 조회 → 차트를 선택하세요. 통계표 817Y002, 항목 010320000.'};
  return null;
}
export function chartLink(r,label){const c=chartSource(r.id);return c?`<a href="${esc(c.url)}" target="_blank" rel="noopener noreferrer" data-external data-chart-link="${esc(r.id)}">${esc(label||(c.kind==='chart'?'웹 차트 바로 보기 ↗':c.kind==='components'?'구성금리 차트 ↗':'공식 차트 조회 ↗'))}</a>`:'';}
export function chartTitle(r){return `<a href="${hashRoute('indicators',r.id)}">${esc(r.name)}</a>`;}
export function chartPanel(r){const c=chartSource(r.id);return `<section class="panel web-chart-panel"><h2>웹에서 장기 그래프 보기</h2>${c?`<div class="links chart-actions">${chartLink(r)}${(c.extra||[]).map(x=>`<a href="${esc(x.url)}" target="_blank" rel="noopener noreferrer" data-external>${esc(x.label)} ↗</a>`).join('')}</div><p>${esc(c.note)}</p><p class="muted">${esc(c.provider)} · 새 브라우저 창에서 기간 확대·축소를 사용할 수 있습니다.</p>`:'<p>이 지표의 외부 차트 연결을 아직 등록하지 않았습니다.</p>'}</section>`;}
