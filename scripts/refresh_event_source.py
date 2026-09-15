"""Refresh one already indexed disclosure source, without AI or notifications."""
import argparse, os, re
import event_runtime as ER
import disclosure_source as DS
import disclosure_facts as DF

def run(rcept_no):
    if not re.fullmatch(r'\d{14}',rcept_no): raise ValueError('Invalid receipt number')
    key=os.environ.get('DART_API_KEY','')
    if not key: raise ValueError('DART_API_KEY missing')
    index=ER._load(ER.P('facts','events','index.json'),{})
    row=next((x for x in index.get('events',[]) if x.get('rcept_no')==rcept_no),None)
    if not row: raise ValueError('Receipt not indexed')
    date=row['date']; file=ER.P('facts','events',f'{date[:4]}-{date[4:6]}-{date[6:8]}.json')
    daily=ER._load(file,{})
    event=next((x for x in daily.get('events',[]) if ER._rcept(x)==rcept_no),None)
    if not event: raise ValueError('Event details missing')
    if event.get('sourceDocument',{}).get('status')!='AVAILABLE':
        event['sourceDocument']=DS.fetch(rcept_no,key)
        event['sourceAttempts']=int(event.get('sourceAttempts',0))+1
        ER._save(file,daily)
        row.update(ER._summary(event));ER._save(ER.P('facts','events','index.json'),index)
    event['sourceDocument'].update(DF.extract(event['sourceDocument'].get('text','')))
    ER._save(file,daily)
    print('Source status:',event['sourceDocument']['status'])
    print('Source reason:',event['sourceDocument'].get('reason','OK'))
    print('Extracted characters:',len(event['sourceDocument'].get('text','')))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('rcept_no');run(p.parse_args().rcept_no)
