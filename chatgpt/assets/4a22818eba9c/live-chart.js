import {esc} from './core.js';
import {chartSource} from './chart-sources.js';

// Market instruments, not substitutions with ETFs, CFDs or spot commodities.
const symbols={usdkrw:'FX_IDC:USDKRW',sp500:'SP:SPX',nasdaq:'NASDAQ:IXIC',sox:'NASDAQ:SOX',vix:'CBOE:VIX',dxy:'TVC:DXY',hsi:'HSI:HSI',wti:'NYMEX:CL1!',copper:'COMEX:HG1!',gold:'COMEX:GC1!',bdry:'AMEX:BDRY'};
export function liveSource(id){
  if(id==='kospi'||id==='kosdaq')return {type:'external',symbol:id.toUpperCase()};
  if(symbols[id])return {type:'tradingview',symbol:symbols[id]};
  const c=chartSource(id);
  if(c?.provider==='FRED'){const u=new URL(c.url);return {type:'fred',query:u.searchParams.has('g')?'g='+u.searchParams.get('g'):'id='+u.pathname.split('/').at(-1)};}
  return null;
}
export function livePanel(r){const c=liveSource(r.id);if(c?.type==='external')return `<section class="panel live-chart-panel"><h2>네이버 전체 차트</h2><p>확대·축소와 분봉·일봉·주봉·월봉을 지원하는 네이버 전용 차트입니다.</p><div class="links chart-actions"><a href="https://m.stock.naver.com/fchart/domestic/index/${esc(c.symbol)}" target="_blank" rel="noopener noreferrer" data-external>네이버 전체 차트 열기 ↗</a></div><p class="muted">네이버가 외부 화면 삽입을 제한하여 새 창에서 엽니다. 흐릿한 확대 이미지는 표시하지 않습니다.</p></section>`;return `<section class="panel live-chart-panel"><div class="panel-head"><h2>${c?.type==='fred'?'공식 발표 이력 차트':'현재 시세 차트'}</h2>${c?'<button type="button" data-live-reload>차트 새로고침</button>':''}</div>${c?`<p class="muted">${c.type==='naver-page'?'네이버 금융 원본 인터랙티브 차트 · 분봉·일봉·주봉·월봉과 확대·축소를 사용할 수 있습니다.':c.type==='fred'?'FRED의 실제 발표 이력입니다. 발표 주기에 따라 갱신되며 실시간 거래 시세가 아닙니다.':'TradingView 제공 시세 · 분봉·일봉·기간을 차트에서 변경하세요. 거래소에 따라 지연되거나 장외에는 멈출 수 있습니다.'}</p><div data-live-chart="${esc(r.id)}"></div><p class="muted" data-live-status role="status">차트 불러오는 중…</p><p class="muted">차트의 기준 시각과 아래 수집값은 다를 수 있습니다. 차트가 제한되거나 나타나지 않으면 아래 웹 차트 버튼을 이용하세요.</p>`:'<p>이 지표는 공식 사이트에서 차트를 확인할 수 있습니다. 이 화면에 삽입 가능한 차트는 아직 지원하지 않습니다.</p>'}</section>`;}
export function mountLiveChart(root,r){
  const host=root.querySelector('[data-live-chart]'),status=root.querySelector('[data-live-status]'),c=liveSource(r.id);
  if(!host||!c)return ()=>{};
  let disposed=false;
  const setStatus=text=>{if(!disposed)status.textContent=text;};
  const draw=()=>{
    if(disposed)return;host.replaceChildren();
    setStatus('차트 불러오는 중…');
    if(c.type==='fred'){
      const frame=document.createElement('iframe');frame.title=r.name+' FRED 발표 이력 차트';frame.className='live-frame';
      frame.src='https://fred.stlouisfed.org/graph/graph-landing.php?'+c.query+'&width=1000&height=500';frame.onload=()=>setStatus('FRED 차트 · 발표 기준일은 차트에서 확인');host.append(frame);
    }else{
      const box=document.createElement('div');box.className='tradingview-widget-container live-tv';
      const widget=document.createElement('div');widget.className='tradingview-widget-container__widget';box.append(widget);
      const credit=document.createElement('div');credit.className='tradingview-widget-copyright';const a=document.createElement('a');a.href='https://www.tradingview.com/symbols/'+c.symbol.replace(':','-')+'/';a.target='_blank';a.rel='noopener noreferrer';a.textContent=r.name+' chart by TradingView';credit.append(a);box.append(credit);
      const script=document.createElement('script');script.src='https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js';script.async=true;
      script.textContent=JSON.stringify({autosize:true,symbol:c.symbol,interval:'D',timezone:'Asia/Seoul',theme:'light',style:'1',locale:'kr',allow_symbol_change:false,hide_top_toolbar:false,hide_side_toolbar:false,withdateranges:true,save_image:true,calendar:false,backgroundColor:'#ffffff'});
      script.onerror=()=>setStatus('차트 연결 실패 · 아래 웹 차트 버튼을 이용하세요.');script.onload=()=>setStatus('시세 연결 중 · 제공처의 차트와 지연 표시를 확인하세요.');box.append(script);host.append(box);
    }
  };
  draw();const reload=root.querySelector('[data-live-reload]');reload.onclick=draw;
  return ()=>{disposed=true;reload.onclick=null;host.replaceChildren();};
}
