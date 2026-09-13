"""Read-only source collection for period bars. Never changes macro.json or records.
No date interpolation, zero filling, or collection-snapshot relabelling.
"""
import csv, io, json, pathlib, datetime as dt, urllib.request, concurrent.futures, math
ROOT = pathlib.Path(__file__).resolve().parents[1]

def transform(rows, kind):
    by_period = {d[:7]:v for d,v in rows}
    result=[]
    for d,v in rows:
        if not math.isfinite(v): continue
        if kind in ('yoy','diff','mom_pct'):
            year,month=map(int,d[:7].split('-'))
            if kind=='yoy': prior=f'{year-1:04}-{month:02}'
            else: prior=f'{year-1:04}-12' if month==1 else f'{year:04}-{month-1:02}'
            old=by_period.get(prior)
            if old is None or (kind!='diff' and old==0): continue
            v=v-old if kind=='diff' else (v/old-1)*100
        result.append({'period':d,'value':round(v,4)})
    return result[-120:]

def collect(ind):
    symbol=ind['symbol'];url='https://fred.stlouisfed.org/graph/fredgraph.csv?id='+symbol
    request=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (invest period charts)'})
    raw=urllib.request.urlopen(request,timeout=25).read().decode('utf-8')
    rows=[]
    for r in csv.DictReader(io.StringIO(raw)):
        d=r.get('observation_date') or r.get('DATE');v=r.get(symbol) or r.get('VALUE')
        if not d or not v or v=='.':continue
        dt.date.fromisoformat(d)
        value=float(v)
        if math.isfinite(value):rows.append((d,value))
    rows.sort();kind=ind.get('derive');points=transform(rows,kind)
    if not points:raise ValueError('No dated observations')
    return {'source_url':url,'symbol':symbol,'cycle':ind.get('cycle'),'unit':ind.get('unit'),'formula':{'yoy':'(당월 지수 / 전년 같은 달 지수 − 1) × 100','diff':'당월 값 − 전월 값','mom_pct':'(당월 값 / 전월 값 − 1) × 100'}.get(kind,'공식 원자료 값'),'collected_at':dt.datetime.now(dt.timezone.utc).isoformat(),'points':points}

def main():
    path=ROOT/'facts/macro_periods.json'
    old=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'schema':'macro_periods/1','items':{}}
    defs=[]
    for name in ['indicators.json','macro_extra_indicators.json']:
        defs.extend(json.loads((ROOT/'data'/name).read_text(encoding='utf-8')).get('items',[]))
    defs=[i for i in defs if i.get('source')=='fred']
    errors={}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        jobs={pool.submit(collect,i):i for i in defs}
        for job in concurrent.futures.as_completed(jobs):
            ind=jobs[job]
            try:old['items'][ind['id']]=job.result()
            except Exception as error:errors[ind['id']]=type(error).__name__+': '+str(error)[:120]
    old['errors']=errors;old['attempted_at']=dt.datetime.now(dt.timezone.utc).isoformat()
    path.write_text(json.dumps(old,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'collected':len(defs)-len(errors),'failed':errors,'retained_items':len(old['items'])},ensure_ascii=False))
if __name__=='__main__':main()
