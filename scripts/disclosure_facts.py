"""Strict adapter for the monthly preliminary-sales table; never guesses missing headers."""
import re
from decimal import Decimal, InvalidOperation

def number(text):
    if not re.fullmatch(r'-?\d[\d,]*(?:\.\d+)?',text): return None
    try: return Decimal(text.replace(',',''))
    except InvalidOperation: return None

def extract(text):
    lines=[x.strip() for x in re.split(r'\n|\|',text) if x.strip()]
    if not any(re.fullmatch(r'단위\s*:\s*백만원\s*,\s*%',x) for x in lines): return {'reportedFacts':[],'comparisons':[]}
    def period(key):
        try:
            i=lines.index(key);a,sep,b=lines[i+1:i+4]
            if sep=='~' and re.fullmatch(r'\d{4}-\d{2}-\d{2}',a) and re.fullmatch(r'\d{4}-\d{2}-\d{2}',b):return a+' ~ '+b
        except (ValueError,IndexError):pass
        return None
    periods={key:period(key) for key in ['당기실적','전기실적','전년동기실적','당기누계실적','전년동기누적실적']}
    if not all(periods.values()):return {'reportedFacts':[],'comparisons':[]}
    try:
        i=lines.index('매출액')
        if lines[i+1]!='당해실적' or lines[i+9]!='누계실적' or lines[i+17]!='영업이익':return {'reportedFacts':[],'comparisons':[]}
        current=[number(x) for x in lines[i+2:i+9]]
        total=[number(x) for x in lines[i+10:i+17]]
        if not all(x is not None for x in [current[0],current[1],current[2],current[4],current[5],total[0],total[4],total[5]]):return {'reportedFacts':[],'comparisons':[]}
    except (ValueError,IndexError):return {'reportedFacts':[],'comparisons':[]}
    facts=[]
    for label,value,p in [('당월 매출액',current[0],'당기실적'),('전월 매출액',current[1],'전기실적'),('전년 동월 매출액',current[4],'전년동기실적'),('누계 매출액',total[0],'당기누계실적'),('전년 동기 누계 매출액',total[4],'전년동기누적실적')]:
        facts.append({'label':label,'value':float(value),'unit':'백만원','period':periods[p],'status':'원문 기재·잠정'})
    comparisons=[]
    for label,a,b,reported in [('매출 전월 대비',current[0],current[1],current[2]),('매출 전년 동월 대비',current[0],current[4],current[5]),('누계 매출 전년 동기 대비',total[0],total[4],total[5])]:
        computed=(a-b)/b*100 if b else None
        comparisons.append({'label':label,'reported':float(reported),'computed':round(float(computed),2) if computed is not None else None,'unit':'%','status':'일치' if computed is not None and abs(computed-reported)<=Decimal('.02') else '확인 필요','formula':'(당기 − 비교기) ÷ 비교기 × 100'})
    return {'reportedFacts':facts,'comparisons':comparisons}
