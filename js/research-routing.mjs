export function legacyDestination(path,hash='',search='') {
 const base='research-dashboard.html';
 const decode=v=>{try{return decodeURIComponent(v);}catch{return '';}};
 const raw=hash.replace(/^#\/?/,''),[route]=raw.split('?'),parts=route.split('/');
 const target=(kind,id)=>id?base+'#'+encodeURIComponent(kind+':'+decode(id)):base;
 if(path.includes('research-cpi'))return new URLSearchParams(search).get('record')?target('record',new URLSearchParams(search).get('record')):base+'?cpi=1#indicator%3Acpi_yoy';
 if(path.includes('chatgpt')||['indicators','news','records'].includes(parts[0])&&raw.includes('/')){
  if(parts[0]==='indicators')return target('indicator',parts[1]);
  if(parts[0]==='records')return parts[1]?target('private',parts[1]):base+'?section=private';
  if(parts[0]==='news')return base+'?section=news'+(parts[1]?'&newsId='+encodeURIComponent(decode(parts[1])):'');
 }
 if(parts[0]==='cpi')return base+'?cpi=1#indicator%3Acpi_yoy';
 if(parts[0]==='analysis'&&parts[1])return target('indicator',parts[1]);
 if(parts[0]==='records')return base+'?section=archive';
 if(parts[0]==='news')return base+'?section=news';
 if(path.includes('macro')&&parts[0])return target('indicator',parts[0]);
 return base;
}
