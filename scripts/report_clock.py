"""Versioned session checks and immutable pre-cutoff morning snapshots.

No network calls. An unknown publishing SLA is not an outage. A response first
received after cutoff can never be used to reconstruct that morning's edition.
"""
import copy
import datetime as dt
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

UTC=dt.timezone.utc
KST=ZoneInfo('Asia/Seoul')

def stamp(value):
    result=dt.datetime.fromisoformat(value.replace('Z','+00:00'))
    if result.tzinfo is None: raise ValueError('timezone_required')
    return result

def is_session(day,cal):
    if not cal['coverage_start']<=day.isoformat()<=cal['coverage_end']:
        raise ValueError('calendar_outside_coverage')
    if cal.get('month_end_observations') and (day+dt.timedelta(days=1)).month!=day.month:
        return True
    return day.weekday()<5 and day.isoformat() not in cal['holidays']

def audit_window(r,cal):
    points=r.get('recent_observations') or r.get('last_five') or []
    # Only inspect the recent five-observation window; older rows remain in raw data.
    recent=points[-5:]
    r['window_calendar_conflicts']=[p['date'] for p in recent if not is_session(dt.date.fromisoformat(p['date']),cal)]
    day=dt.date.fromisoformat(r['observation_date'])
    wanted=[day.isoformat()]
    for _ in range(4):
        day=prior(day,cal);wanted.append(day.isoformat())
    by_date={p['date']:p for p in points}
    r['window_missing_dates']=[d for d in wanted if d not in by_date]
    r['window_eligible']=not r['window_calendar_conflicts'] and not r['window_missing_dates']
    r['validated_window']=[by_date[d] for d in reversed(wanted)] if r['window_eligible'] else []
    r['window_note']='최근 5개 관측일 달력 검증. 최신성 적격은 별도.'

def prior(day,cal):
    for _ in range(20):
        day-=dt.timedelta(days=1)
        if is_session(day,cal): return day
    raise ValueError('calendar_gap')

def expected(profile,policy,cutoff):
    cal=policy['calendars'][profile['calendar']]
    if cutoff.astimezone(KST).date().isoformat()>=policy['calendar_review_due']:
        raise ValueError('calendar_review_due')
    local=cutoff.astimezone(ZoneInfo(cal['timezone']))
    day=local.date()
    if profile['mode']=='next_business_day':
        if not is_session(day,cal) or local.strftime('%H:%M')<profile['publication_time']:
            day=prior(day,cal)
        obs=prior(day,cal)
        return obs,dt.datetime.combine(day,dt.time.fromisoformat(profile['publication_time']),ZoneInfo(cal['timezone'])),cal
    close=cal['early_closes'].get(day.isoformat(),cal['close'])
    if not is_session(day,cal) or local.strftime('%H:%M')<close: day=prior(day,cal)
    return day,None,cal

def assess(item,policy,cutoff):
    r=copy.deepcopy(item)
    r.update(asof=cutoff.isoformat(),freshness_status='not_connected',data_eligible=False,
             comparison_eligible=False,display_change=None,expected_observation_date=None,
             expected_publication_at=None,missing_sessions=None,signal_eligible=False,
             window_eligible=False,validated_window=[],window_calendar_conflicts=[],source_value_conflicts=[],
             signal_note='자료 적격과 매매 판단은 별개. 매매 신호 자동 생성 없음.')
    if r['connection_status']!='connected': return r
    if not r.get('retrieved_at') or stamp(r['retrieved_at'])>cutoff:
        r['freshness_status']='after_cutoff'; return r
    profile=policy['profiles'].get(r['id'],{})
    if not profile.get('calendar'):
        r['freshness_status']='calendar_unverified'; return r
    try:
        obs,due,cal=expected(profile,policy,cutoff)
        r['expected_observation_date']=obs.isoformat()
        r['expected_publication_at']=due.isoformat() if due else None
        audit_window(r,cal)
        comparison=r.get('source_comparison',{})
        if comparison.get('status')=='mismatch':
            r['source_value_conflicts']=comparison.get('mismatches',[]) or ['same_date_value_mismatch']
            r['freshness_status']='source_value_conflict'
            r['window_eligible']=False;r['validated_window']=[]
            return r
        actual=dt.date.fromisoformat(r['observation_date'])
        if not is_session(actual,cal):
            r['freshness_status']='observation_calendar_conflict'; return r
        if actual>obs:
            r['freshness_status']='unexpected_observation_date'; return r
        if actual<obs:
            days=(obs-actual).days
            r['missing_sessions']=sum(is_session(actual+dt.timedelta(days=i),cal) for i in range(1,days+1))
            r['freshness_status']='publication_overdue' if due else 'latest_session_not_received_publication_time_unknown'
            return r
        r['freshness_status']='current_for_schedule'
        r['data_eligible']=True
        r['missing_sessions']=0
        r['comparison_eligible']=r.get('previous_observation_date')==prior(actual,cal).isoformat()
        if r['comparison_eligible']: r['display_change']=r.get('change')
        else: r['freshness_status']='current_comparison_gap'
    except (ValueError,KeyError) as error:
        r['freshness_status']=str(error) if isinstance(error,ValueError) else 'calendar_configuration_missing'
    return r

def canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()

def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def run(snapshot,policy,output_dir,at=None):
    at=at or stamp(snapshot['completed_at'])
    if stamp(snapshot['completed_at'])>at: raise ValueError('snapshot_from_future')
    output_dir=Path(output_dir)
    day=at.astimezone(KST).date()
    cutoff=dt.datetime.combine(day,dt.time.fromisoformat(policy['cutoff']),KST)
    live=copy.deepcopy(snapshot)
    live['clock_policy_version']=policy['version']
    live['items']=[assess(i,policy,at) for i in live['items']]
    live['eligibility_counts']={k:sum(bool(i[k]) for i in live['items']) for k in ('data_eligible','comparison_eligible')}
    candidate=output_dir/'report_candidates'/f'{day}.json'
    frozen=output_dir/'report_editions'/str(day)/'snapshot.json'
    state={'schema':'report_clock/1','policy_version':policy['version'],'cutoff':cutoff.isoformat(),'checked_at':at.isoformat(),'frozen_path':None,'status':'collecting_before_cutoff','eligible_counts':live['eligibility_counts']}
    if at<=cutoff:
        # Prevent delayed/retried older jobs from replacing a newer candidate.
        old=json.loads(candidate.read_text(encoding='utf-8')) if candidate.exists() else None
        if old is None or stamp(snapshot['completed_at'])>stamp(old['completed_at']): save(candidate,snapshot)
    else:
        if not frozen.exists() and candidate.exists():
            selected=json.loads(candidate.read_text(encoding='utf-8'))
            if stamp(selected['completed_at'])>cutoff: raise ValueError('candidate_after_cutoff')
            selected['items']=[assess(i,policy,cutoff) for i in selected['items']]
            selected.update(edition_date=str(day),edition_kind='morning',cutoff=cutoff.isoformat(),frozen_at=at.isoformat(),clock_policy_version=policy['version'])
            selected['content_sha256']=hashlib.sha256(canonical(selected)).hexdigest()
            save(frozen,selected)
        if frozen.exists():
            edition=json.loads(frozen.read_text(encoding='utf-8'))
            saved_hash=edition.pop('content_sha256')
            if hashlib.sha256(canonical(edition)).hexdigest()!=saved_hash: raise ValueError('frozen_snapshot_hash_mismatch')
            state.update(status='frozen',frozen_path=str(frozen.relative_to(output_dir)).replace('\\','/'),content_sha256=saved_hash)
        else:
            state['status']='no_pre_cutoff_snapshot'
            state['reason']='마감 전 보존 자료 없음. 현재 값을 오늘 아침 수치로 소급하지 않음.'
    save(output_dir/'market_report_clock.json',state)
    save(output_dir/'market_report_feeds.json',live)
    return live,state
