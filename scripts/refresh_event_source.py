"""Refresh one already indexed disclosure source, without AI or notifications."""
import argparse, os, re
import event_runtime as ER
import disclosure_source as DS
import disclosure_facts as DF

def run(rcept_no):
    if not re.fullmatch(r'\d{14}',rcept_no): raise ValueError('Invalid receipt number')
    index=ER._load(ER.P('facts','events','index.json'),{})
    row=next((x for x in index.get('events',[]) if x.get('rcept_no')==rcept_no),None)
    if not row: raise ValueError('Receipt not indexed')
    date=row['date']; file=ER.P('facts','events',f'{date[:4]}-{date[4:6]}-{date[6:8]}.json')
    daily=ER._load(file,{})
    event=next((x for x in daily.get('events',[]) if ER._rcept(x)==rcept_no),None)
    if not event: raise ValueError('Event details missing')
    if event.get('sourceDocument',{}).get('status')!='AVAILABLE':
        key=os.environ.get('DART_API_KEY','')
        if not key: raise ValueError('DART_API_KEY missing')
        event['sourceDocument']=DS.fetch(rcept_no,key)
        event['sourceAttempts']=int(event.get('sourceAttempts',0))+1
        ER._save(file,daily)
        row.update(ER._summary(event));ER._save(ER.P('facts','events','index.json'),index)
    event['sourceDocument'].update(DF.extract(event['sourceDocument'].get('text','')))
    ER._save(file,daily)
    print('Source status:',event['sourceDocument']['status'])
    print('Source reason:',event['sourceDocument'].get('reason','OK'))
    print('Extracted characters:',len(event['sourceDocument'].get('text','')))
def pending(limit=30):
    if not 1 <= limit <= 30: raise ValueError('Limit must be 1..30')
    index=ER._load(ER.P('facts','events','index.json'),{})
    candidates=[r for r in index.get('events',[]) if r.get('sourceStatus')!='AVAILABLE' and int(r.get('sourceAttempts',0))<2]
    # Give never-attempted documents priority over retrying a failed endpoint.
    candidates.sort(key=lambda r:int(r.get('sourceAttempts',0)))
    selected=candidates[:limit]
    for row in selected: run(row['rcept_no'])
    print('Pending documents processed:',len(selected))
    return len(selected)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('rcept_no');p.add_argument('--limit',type=int,default=30);args=p.parse_args()
    pending(args.limit) if args.rcept_no=='pending' else run(args.rcept_no)
