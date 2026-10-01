"""Supplemental funding observations; facility usage is never a crisis score."""
import csv,datetime as dt,hashlib,io,json,math
from zoneinfo import ZoneInfo
IORB='https://fred.stlouisfed.org/graph/fredgraph.csv?id=IORB&cosd='
OPERATIONS='https://markets.newyorkfed.org/api/rp/all/all/results/lastTwoWeeks.json'

def parse_iorb(raw):
    rows=[]
    for r in csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))):
        if r['IORB'] in ('','.'):continue
        day=r.get('observation_date') or r['DATE'];dt.date.fromisoformat(day);v=float(r['IORB'])
        if not math.isfinite(v):raise ValueError('non_finite_iorb')
        rows.append({'date':day,'value':v})
    if not rows:raise ValueError('iorb_missing')
    if len({r['date'] for r in rows})!=len(rows):raise ValueError('iorb_duplicate_date')
    return sorted(rows,key=lambda r:r['date'])

def parse_operations(raw,at):
    rows=json.loads(raw)['repo']['operations'];out=[];ids=set()
    for r in rows:
        if r['auctionStatus']!='Results':continue
        if r['operationId'] in ids:raise ValueError('duplicate_operation_id')
        ids.add(r['operationId'])
        stamp=dt.datetime.fromisoformat(r['lastUpdated']).replace(tzinfo=ZoneInfo('America/New_York'))
        if stamp>at:raise ValueError('future_operation_result')
        v=float(r['totalAmtAccepted'])
        if not math.isfinite(v) or v<0:raise ValueError('invalid_accepted_amount')
        out.append({k:r.get(k) for k in ('operationId','operationDate','operationType','operationMethod','term','settlementDate','maturityDate','releaseTime','closeTime','lastUpdated','totalAmtAccepted','note','acceptedCpty','participatingCpty')})
    if not out:raise ValueError('operations_missing')
    latest=max(r['operationDate'] for r in out)
    latest_rows=[r for r in out if r['operationDate']==latest]
    totals={kind:sum(r['totalAmtAccepted'] for r in latest_rows if r['operationType']==kind) for kind in ('Repo','Reverse Repo')}
    return dict(observation_date=latest,operations=out,latest_operations=latest_rows,totals_usd=totals,classification='all_reported_operations_not_srf_only',full_day_completeness='not_asserted',note='운영 결과 합계. 소액 시험 포함 가능. SRF 전용 수치·수요 압력·위기 여부로 자동 해석하지 않음.')

def collect(get,raw_dir):
    at=dt.datetime.now(dt.timezone.utc);result={'schema':'funding_context/1','sources':[]}
    for name,url in [('IORB',IORB+(at.date()-dt.timedelta(days=45)).isoformat()),('NYFED_OPERATIONS',OPERATIONS)]:
        row={'id':name,'source_url':url,'status':'error'}
        try:
            raw=get(url);retrieved=dt.datetime.now(dt.timezone.utc)
            data={'observations':parse_iorb(raw)} if name=='IORB' else parse_operations(raw,retrieved)
            if name=='IORB' and data['observations'][-1]['date']>retrieved.date().isoformat():raise ValueError('future_iorb')
            path=raw_dir/('funding_'+name+('.csv' if name=='IORB' else '.json'));path.write_bytes(raw)
            row.update(status='connected',retrieved_at=retrieved.isoformat(),raw_sha256=hashlib.sha256(raw).hexdigest(),raw_file=path.name,**data)
        except Exception as exc:row.update(error=type(exc).__name__,retrieved_at=dt.datetime.now(dt.timezone.utc).isoformat())
        result['sources'].append(row)
    result['counts']={k:sum(x['status']==k for x in result['sources']) for k in ('connected','error')}
    return result
