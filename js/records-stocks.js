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
  function summary(name,item,records){
    var all=entries(name,item,records), info=fields(item), own=logs(item);
    return {name:name,entries:all,total:all.length,linked:all.length-own.length,history:own.length,fields:info,
      hasContent:!!(all.length||info.length),last:all.length?date(all[0]):'',
      preview:all.length?text(all[0].oneLiner||all[0].body||all[0].title):info.map(function(f){return f.label+': '+f.value;}).join(' · ')};
  }
  function directory(names,itemOf,records,query,onlyContent){
    var q=text(query).toLocaleLowerCase();
    return names.map(function(n){return summary(n,itemOf(n),records);}).filter(function(s){
      if(onlyContent&&!s.hasContent)return false;
      return !q||[s.name,s.fields.map(function(f){return f.label+' '+f.value;}).join(' '),s.entries.map(function(r){
        return [r.title,r.oneLiner,r.body,r.userJudgment,r.aiInterpretation,(r.topics||[]).join(' ')].join(' ');
      }).join(' ')].join(' ').toLocaleLowerCase().includes(q);
    }).sort(function(a,b){return Number(b.hasContent)-Number(a.hasContent)||newest(a.entries[0]||{},b.entries[0]||{})||a.name.localeCompare(b.name,'ko');});
  }
  function mergeFields(base,original,edits){
    Object.keys(edits).forEach(function(k){
      if(JSON.stringify(edits[k])===JSON.stringify(original[k]))return;
      if(JSON.stringify(base[k])!==JSON.stringify(original[k]))throw new Error('다른 기기에서 같은 항목을 변경했습니다. 입력을 복사한 뒤 다시 열어 비교해 주세요.');
      base[k]=edits[k];
    });
  }
  var api={millis:millis,kstDate:kstDate,newest:newest,fields:fields,logs:logs,entries:entries,summary:summary,directory:directory,mergeFields:mergeFields};
  if(typeof module==='object'&&module.exports)module.exports=api;
  else root.RecordStocks=api;
})(typeof window!=='undefined'?window:globalThis);
