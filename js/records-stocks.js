/* Stock history is a read-only projection; the original records and thesisLog remain the source. */
(function(root){
  'use strict';
  function text(v){ return v == null ? '' : String(v).trim(); }
  function millis(v){
    if(v && typeof v.toMillis==='function') return v.toMillis();
    if(v && typeof v.seconds==='number') return v.seconds*1000;
    return typeof v==='number' ? v : (Date.parse(v)||0);
  }
  function kstDate(v){ return new Date(millis(v)+9*3600000).toISOString().slice(0,10); }
  function stamp(r){ return millis(r.updatedAt||r.createdAt||r.at); }
  function date(r){ return text(r.date).slice(0,10) || (stamp(r)?kstDate(stamp(r)):''); }
  function newest(a,b){ return date(b).localeCompare(date(a)) || stamp(b)-stamp(a) || (b._stockIndex||0)-(a._stockIndex||0); }
  function fields(item){
    item=item||{};
    return [['status','상태'],['quantity','보유수량'],['avgCost','매수단가'],['targetPrice','목표가']]
      .filter(function(f){return text(item[f[0]]);}).map(function(f){return {label:f[1],value:String(item[f[0]])};})
      .concat((item.customFields||[]).filter(function(f){return f && text(f.value);}).map(function(f){return {label:text(f.label),value:String(f.value)};}));
  }
  function logs(item){
    return ((item||{}).thesisLog||[]).map(function(x,i){return Object.assign({},x,{_stockIndex:i});})
      .filter(function(x){return text(x.text);}).sort(newest);
  }
  function entries(name,item,records){
    var related=records.filter(function(r){return (r.stocks||[]).indexOf(name)>=0;});
    var history=logs(item).map(function(x){
      return {id:'stock-log:'+encodeURIComponent(name)+':'+x._stockIndex,_stockLog:true,_stockIndex:x._stockIndex,
        kind:'memo',title:x.auto?'정보 변경':'투자논지',channel:'종목에 직접 남긴 이력',date:date(x),createdAt:millis(x.at||x.createdAt),
        body:x.text,oneLiner:x.text,stocks:[name],topics:[]};
    });
    return related.concat(history).sort(newest);
  }
  function followupsFor(name,items,records){
    var ids=new Set(records.filter(function(r){return (r.stocks||[]).includes(name);}).map(function(r){return r.id;}));
    return (items||[]).filter(function(x){return (x.stocks||[]).includes(name)||(x.sourceIds||[]).some(function(id){return ids.has(id);});});
  }
  function pending(items){
    return (items||[]).filter(function(x){return x.state==='open'||x.state==='working';}).slice().sort(function(a,b){return (a.dueAt||'9999').localeCompare(b.dueAt||'9999')||text(a.question).localeCompare(text(b.question),'ko');});
  }
  function schedules(items,records,scope){
    scope=scope||{};
    var ids=new Set(records.map(function(r){return r.id;})), seen=new Set();
    var list=scope.stock?followupsFor(scope.stock,items,scope.allRecords||records):items;
    return pending(list).filter(function(x){
      if(!x.dueAt||seen.has(x.id))return false;
      if(!scope.stock&&!scope.all&&!(x.sourceIds||[]).some(function(id){return ids.has(id);}))return false;
      seen.add(x.id);return true;
    });
  }
  function overview(item){
    var all=fields(item), core=all.filter(function(f){return ['상태','보유수량','매수단가'].includes(f.label);});
    var reason=all.find(function(f){return ['관심 이유','매수사유','핵심가정'].includes(f.label);});
    return {core:core,reason:reason||null,details:all.filter(function(f){return !core.includes(f)&&f!==reason;})};
  }
  function summary(name,item,records,followups){
    var all=entries(name,item,records), info=fields(item), own=logs(item);
    var linkedFollowups=followupsFor(name,followups,records);
    return {name:name,entries:all,total:all.length,linked:all.length-own.length,history:own.length,fields:info,
      followups:linkedFollowups,pending:pending(linkedFollowups),hasContent:!!(all.length||info.length||linkedFollowups.length),last:all.length?date(all[0]):'',
      preview:all.length?text(all[0].oneLiner||all[0].body||all[0].title):info.length?info.map(function(f){return f.label+': '+f.value;}).join(' · '):linkedFollowups.map(function(x){return x.question;}).join(' · ')};
  }
  function directory(names,itemOf,records,query,onlyContent,followups){
    var q=text(query).toLocaleLowerCase();
    return names.map(function(n){return summary(n,itemOf(n),records,followups);}).filter(function(s){
      if(onlyContent&&!s.hasContent)return false;
      return !q||[s.name,s.fields.map(function(f){return f.label+' '+f.value;}).join(' '),s.entries.map(function(r){
        return [r.title,r.oneLiner,r.body,r.userJudgment,r.aiInterpretation,(r.topics||[]).join(' ')].join(' ');
      }).join(' '),s.followups.map(function(x){return [x.question,x.result,x.expectation].join(' ');}).join(' ')].join(' ').toLocaleLowerCase().includes(q);
    }).sort(function(a,b){return Number(b.hasContent)-Number(a.hasContent)||newest(a.entries[0]||{},b.entries[0]||{})||a.name.localeCompare(b.name,'ko');});
  }
  // Firestore map key order differs between query snapshots and transaction reads.
  // Field identity must compare content, while preserving meaningful array order.
  function sameValue(a,b){
    function stable(v){return JSON.stringify(v,function(_,x){
      return x&&typeof x==='object'&&!Array.isArray(x)?Object.keys(x).sort().reduce(function(o,k){o[k]=x[k];return o;},{}):x;
    });}
    return stable(a)===stable(b);
  }
  function mergeFields(base,original,edits){
    Object.keys(edits).forEach(function(k){
      if(sameValue(edits[k],original[k]))return;
      if(!sameValue(base[k],original[k]))throw new Error('다른 기기에서 같은 항목을 변경했습니다. 입력을 복사한 뒤 다시 열어 비교해 주세요.');
      base[k]=edits[k];
    });
  }
  var api={millis:millis,kstDate:kstDate,newest:newest,fields:fields,logs:logs,entries:entries,summary:summary,directory:directory,mergeFields:mergeFields,sameValue:sameValue,followupsFor:followupsFor,pending:pending,schedules:schedules,overview:overview};
  if(typeof module==='object'&&module.exports)module.exports=api;
  else root.RecordStocks=api;
})(typeof window!=='undefined'?window:globalThis);
