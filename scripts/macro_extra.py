# MACRO_STANDARD v1 보강 수집기
# 역할: 기존 scripts/macro.py 를 건드리지 않고 검증된 신규 핵심지표를 별도 수집한다.
# 출력: facts/macro_extra.json, facts/macro_extra_history.json
import csv, datetime as dt, io, json, os, urllib.request

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P=lambda *a: os.path.join(ROOT,*a)
KST=dt.timezone(dt.timedelta(hours=9))

def now_iso(): return dt.datetime.now(KST).replace(microsecond=0).isoformat()
def load(path,default):
    try:
        with open(path,encoding='utf-8') as f:return json.load(f)
    except Exception:return default

def save(path,obj):
    os.makedirs(os.path.dirname(path),exist_ok=True)
    with open(path,'w',encoding='utf-8',newline='\n') as f:json.dump(obj,f,ensure_ascii=False,indent=2)

def fred(series):
    url=f'https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}'
    raw=urllib.request.urlopen(url,timeout=25).read().decode('utf-8')
    out=[]
    for r in csv.DictReader(io.StringIO(raw)):
        v=r.get(series) or r.get('VALUE') or ''
        if not str(v).strip() or str(v).strip()=='.':continue
        d=r.get('observation_date') or r.get('DATE')
        out.append((d,float(v)))
    return out

def yoy(rows):
    if len(rows)<14: raise RuntimeError('yoy 계산에 14개 이상 필요')
    prev=(rows[-2][1]/rows[-14][1]-1)*100
    cur=(rows[-1][1]/rows[-13][1]-1)*100
    return rows[-1][0],cur,prev

def mom_pct(rows):
    if len(rows)<3: raise RuntimeError('mom 계산에 3개 이상 필요')
    prev=(rows[-2][1]/rows[-3][1]-1)*100 if rows[-3][1] else None
    cur=(rows[-1][1]/rows[-2][1]-1)*100 if rows[-2][1] else None
    return rows[-1][0],cur,prev

def level_4w(rows):
    if len(rows)<5: raise RuntimeError('4주 평균 계산에 5개 이상 필요')
    cur=rows[-1][1]; prev=rows[-2][1]
    avg4=sum(v for _,v in rows[-4:])/4
    prev4=sum(v for _,v in rows[-5:-1])/4
    return rows[-1][0],cur,prev,avg4,prev4

def run():
    cfg=load(P('data','macro_extra_indicators.json'),{})
    items=[]; errors=[]
    for ind in cfg.get('items',[]):
        rec={k:ind.get(k) for k in ['id','name','unit','country','group','role','cycle','official','source_url','schedule_url','meaning','interpretation'] if k in ind}
        rec.update({'source':'fred','symbol':ind['symbol'],'value':None,'prev':None,'change':None,'as_of':'','collected_at':now_iso(),'error':''})
        try:
            rows=fred(ind['symbol'])
            kind=ind.get('derive')
            if kind=='yoy':
                d,cur,prev=yoy(rows); rec.update({'as_of':d,'value':round(cur,3),'prev':round(prev,3),'change':round(cur-prev,3)})
            elif kind=='mom_pct':
                d,cur,prev=mom_pct(rows); rec.update({'as_of':d,'value':round(cur,3),'prev':round(prev,3),'change':round(cur-prev,3)})
            elif kind=='level_4w':
                d,cur,prev,avg4,prev4=level_4w(rows); rec.update({'as_of':d,'value':round(cur,1),'prev':round(prev,1),'change':round(cur-prev,1),'avg4':round(avg4,1),'prev_avg4':round(prev4,1),'avg4_change':round(avg4-prev4,1)})
            else:
                if len(rows)<2: raise RuntimeError('데이터 부족')
                rec.update({'as_of':rows[-1][0],'value':rows[-1][1],'prev':rows[-2][1],'change':rows[-1][1]-rows[-2][1]})
        except Exception as e:
            rec['error']=f'{type(e).__name__}: {e}'[:180]; errors.append(f"{ind['id']}: {rec['error']}")
        items.append(rec)
    out={'schema':'macro_extra/1','version':cfg.get('version',''),'collected_at':now_iso(),'ok':sum(1 for x in items if not x['error']),'total':len(items),'items':items,'errors':errors}
    save(P('facts','macro_extra.json'),out)
    hist=load(P('facts','macro_extra_history.json'),{'schema':'macro_extra_history/1','days':{}})
    key=dt.datetime.now(KST).date().isoformat(); day=hist.setdefault('days',{}).setdefault(key,{})
    for x in items:
        if x.get('value') is not None:
            day[x['id']]=x['value']
            if 'avg4' in x: day[x['id']+'_avg4']=x['avg4']
    # 최대 500일
    keys=sorted(hist['days'])
    for k in keys[:-500]: hist['days'].pop(k,None)
    save(P('facts','macro_extra_history.json'),hist)
    print(f"macro_extra: {out['ok']}/{out['total']} ok")
    if errors:
        print('\n'.join(errors))

if __name__=='__main__': run()
