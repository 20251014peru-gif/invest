import {esc} from './core.js';
import {chartSource} from './chart-sources.js';

// Market instruments, not substitutions with ETFs, CFDs or spot commodities.
const symbols={usdkrw:'FX_IDC:USDKRW',sp500:'SP:SPX',nasdaq:'NASDAQ:IXIC',sox:'NASDAQ:SOX',vix:'CBOE:VIX',dxy:'TVC:DXY',hsi:'HSI:HSI',wti:'NYMEX:CL1!',copper:'COMEX:HG1!',gold:'COMEX:GC1!',bdry:'AMEX:BDRY'};
export function liveSource(id){
  if(id==='kospi'||id==='kosdaq')return {type:'naver',symbol:id.toUpperCase()};
  if(symbols[id])return {type:'tradingview',symbol:symbols[id]};
  const c=chartSource(id);
  if(c?.provider==='FRED'){const u=new URL(c.url);return {type:'fred',query:u.searchParams.has('g')?'g='+u.searchParams.get('g'):'id='+u.pathname.split('/').at(-1)};}
  return null;
}
export function livePanel(r){const c=liveSource(r.id);return `<section class="panel live-chart-panel"><div class="panel-head"><h2>${c?.type==='fred'?'공식 발표 이력 차트':'현재 시세 차트'}</h2>${c?'<button type="button" data-live-reload>차트 새로고침</button>':''}</div>${c?`<p class="muted">${c.type==='naver'?'네이버 금융 · 1분마다 차트 이미지 갱신 · 장외에는 마지막 거래 흐름을 표시합니다.':c.type==='fred'?'FRED의 실제 발표 이력입니다. 발표 주기에 따라 갱신되며 실시간 거래 시세가 아닙니다.':'TradingView 제공 시세 · 분봉·일봉·기간을 차트에서 변경하세요. 거래소에 따라 지연되거나 장외에는 멈출 수 있습니다.'}</p><div data-live-chart="${esc(r.id)}"></div><p class="muted" data-live-status role="status">차트 불러오는 중…</p><p class="muted">차트의 기준 시각과 아래 수집값은 다를 수 있습니다. 차트가 제한되거나 나타나지 않으면 아래 웹 차트 버튼을 이용하세요.</p>`:'<p>이 지표는 공식 사이트에서 차트를 확인할 수 있습니다. 이 화면에 삽입 가능한 차트는 아직 지원하지 않습니다.</p>'}</section>`;}
export function mountLiveChart(root,r){
  const host=root.querySelector('[data-live-chart]'),status=root.querySelector('[data-live-status]'),c=liveSource(r.id);
  if(!host||!c)return ()=>{};
  let timer,disposed=false,period='day',generation=0;
  const setStatus=text=>{if(!disposed)status.textContent=text;};
  const draw=()=>{
    if(disposed)return;const gen=++generation;host.replaceChildren();
    setStatus('차트 불러오는 중…');
    if(c.type==='naver'){
      const nav=document.createElement('div');nav.className='segments live-periods';
      for(const [p,label] of [['day','1일'],['day90','3개월'],['day365','1년'],['day1095','3년']]){const b=document.createElement('button');b.type='button';b.textContent=label;b.setAttribute('aria-pressed',String(p===period));b.onclick=()=>{period=p;draw();};nav.append(b);}
      const img=document.createElement('img');img.className='naver-live-chart';img.alt=r.name+' 네이버 '+period+' 시세 차트';img.referrerPolicy='no-referrer';
      img.onload=()=>{if(gen===generation)setStatus('차트 이미지 수신 '+new Date().toLocaleTimeString('ko-KR')+' · 시세 기준 시각은 차트 확인');};
      img.onerror=()=>{if(gen===generation)setStatus('네이버 차트를 불러오지 못했습니다. 아래 네이버 웹 차트를 열어주세요.');};
      img.src='https://ssl.pstatic.net/imgstock/chart3/'+period+'/'+c.symbol+'.png?sidcode='+Date.now();host.append(nav,img);
    }else if(c.type==='fred'){
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
  if(c.type==='naver')timer=setInterval(()=>{if(!document.hidden)draw();},60000);
  return ()=>{disposed=true;clearInterval(timer);reload.onclick=null;host.replaceChildren();};
}
