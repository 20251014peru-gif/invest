const ctx=window.parent!==window?window.parent.FollowupSharedContext:null;
const error=document.getElementById('shared-error');window.followupDirty=false;
if(!ctx){error.textContent='투자 기록보관실의 확인·복기에서 열어 주세요.';}
else try{
 const {openInvestmentDetail}=await import('/dalnim-calendar/src/components/investment-detail.js?v=0.14.1');
 const d=document.getElementById('editor'),notify=text=>{document.getElementById('toast').textContent=text;};
 const store={isCloud:true,cache:[],request:ctx.request,
  async reload(){const r=await this.request('/events');this.cache=r.events||[];return this;},
  async list(){await this.reload();return this.cache;},
  async saveOnline(event,expectedRevision){const r=await this.request('/events','POST',{event,expectedRevision});await this.reload();return r.event;}};
 error.hidden=true;d.addEventListener('input',()=>window.followupDirty=true);d.addEventListener('change',()=>window.followupDirty=true);
 d.addEventListener('close',()=>{window.followupDirty=false;ctx.close();},{once:true});
 await openInvestmentDetail({dialog:d,store,record:{id:ctx.id,title:'확인·복기',source:{app:'investment-archive',recordId:ctx.id.slice('investment-followup:'.length)},integration:{type:'followup',editable:false}},onChange:async item=>{if(item?.integration)window.followupDirty=false;ctx.changed();},onSettings:()=>window.open('/dalnim-calendar/?investment='+encodeURIComponent(ctx.id),'_blank','noopener'),notify});
 const nav=document.createElement('nav');nav.className='shared-tools';
 const a=document.createElement('a');a.href='/dalnim-calendar/?investment='+encodeURIComponent(ctx.id);a.target='_blank';a.rel='noopener';a.textContent='캘린더에서 같은 항목 ↗';
 const extra=document.createElement('button');extra.type='button';extra.className='soft';extra.textContent='질문·사진·추가 정보';extra.onclick=ctx.legacy;
 nav.append(a,extra);d.prepend(nav);
}catch(e){error.hidden=false;error.textContent='공통 화면 연결 실패: '+e.message+' · 저장된 자료는 그대로입니다.';const b=document.createElement('button');b.textContent='닫기';b.onclick=ctx.close;error.append(b);}
