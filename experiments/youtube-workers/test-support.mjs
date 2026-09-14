import {SummaryJobs} from './worker.mjs';
export class Storage {
  constructor(map=new Map()){this.map=map;this.alarm=null;}
  async get(k){return structuredClone(this.map.get(k));}
  async put(k,v){this.map.set(k,structuredClone(v));}
  async delete(k){this.map.delete(k);}
  async setAlarm(n){this.alarm=n;}
  async transaction(fn){const copy=new Storage(structuredClone(this.map));copy.alarm=this.alarm;const result=await fn(copy);this.map=copy.map;this.alarm=copy.alarm;return result;}
}
export function setup(env={},storage=new Storage()){
  let chain=Promise.resolve();const ctx={storage,blockConcurrencyWhile(fn){const p=chain.then(fn);chain=p.catch(()=>{});return p;}};
  const config={LIVE_AI:'0',MONTHLY_LIMIT_USD:'0',...env};const jobs=new SummaryJobs(ctx,config);
  return {jobs,storage,env:config};
}
