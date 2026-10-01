"""Official Treasury XML and Nasdaq anonymous EOD history, no quote-page headlines."""
import datetime as dt
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

TREASURY='https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml'
NASDAQ='https://indexes.nasdaqomx.com/Index/HistoryData'

def treasury_rows(raw,field):
    if field not in ('BC_2YEAR','BC_10YEAR','BC_30YEAR'):raise ValueError('treasury_field_unregistered')
    root=ET.fromstring(raw);rows=[]
    for p in root.iter():
        if p.tag!='{http://schemas.microsoft.com/ado/2007/08/dataservices/metadata}properties':continue
        r={x.tag.rsplit('}',1)[-1]:x.text for x in p}
        if r.get(field) is not None:rows.append((r['NEW_DATE'][:10],r[field]))
    if not rows:raise ValueError('treasury_rows_missing')
    return rows

def nasdaq_rows(raw):
    obj=json.loads(raw);rows=[]
    data=obj.get('aaData',[])
    if not data or int(obj.get('iTotalRecords',-1))!=len(data):raise ValueError('nasdaq_eod_rows_missing_or_truncated')
    for r in data:
        stamp=re.fullmatch(r'/Date\((\d+)\)/',r.get('TimeStamp',''))
        if not stamp or r.get('Value') is None:raise ValueError('nasdaq_eod_schema_changed')
        date=dt.datetime.fromtimestamp(int(stamp[1])/1000,dt.timezone.utc).astimezone(ZoneInfo('America/New_York')).date()
        rows.append((date.isoformat(),r['Value']))
    # This endpoint returns unrounded daily values; headline NetChange is not used.
    return rows

def retrieve(spec,today,get):
    if spec['provider']=='treasury':
        url=TREASURY+'?'+urllib.parse.urlencode({'data':'daily_treasury_yield_curve','field_tdr_date_value':today.year})
        raw=get(url);return treasury_rows(raw,spec['treasury_field']),raw,url,'treasury_xml',[]
    if spec['provider']=='nasdaq_eod':
        if spec['series'] not in ('COMP','SOX'):raise ValueError('nasdaq_symbol_unregistered')
        params={'id':spec['series'],'startDate':(today-dt.timedelta(days=45)).isoformat()+'T00:00:00','endDate':today.isoformat()+'T00:00:00','timeOfDay':'EOD'}
        req=urllib.request.Request(NASDAQ,data=urllib.parse.urlencode(params).encode(),headers={'User-Agent':'invest-report-feeds/2.5'})
        with urllib.request.urlopen(req,timeout=25) as res:raw=res.read(3000000)
        return nasdaq_rows(raw),raw,NASDAQ+'?'+urllib.parse.urlencode(params),'nasdaq_eod_json',[]
    raise ValueError('official_source_unregistered')

def compare(primary,secondary,tolerance):
    a={p['date']:p['value'] for p in primary};b={p['date']:p['value'] for p in secondary}
    common=sorted(a.keys() & b.keys())[-5:]
    diffs=[{'date':d,'primary':a[d],'secondary':b[d],'absolute_difference':round(abs(a[d]-b[d]),10)} for d in common]
    bad=[r for r in diffs if r['absolute_difference']>tolerance]
    state='no_common_date' if not common else 'mismatch' if bad else 'matched_overlap'
    if state=='matched_overlap' and max(a)>max(b):state='matched_overlap_primary_newer'
    return {'status':state,'tolerance':tolerance,'checked':diffs,'mismatches':bad,'primary_latest':max(a),'secondary_latest':max(b),'independent_origin':False,'note':'원작성자와 FRED 재배포 경로 대조. 독립된 가격 산출기관 두 곳의 검증은 아님.'}
