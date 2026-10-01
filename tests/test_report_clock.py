import copy
import datetime as dt
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import report_clock as c
ROOT=Path(__file__).resolve().parents[1]
P=json.loads((ROOT/'data/report_clock_policy.json').read_text(encoding='utf-8'))

def item(id='US_SPX_CLOSE',date='2026-09-30',previous='2026-09-29',received='2026-09-30T22:55:00Z'):
    return dict(id=id,connection_status='connected',observation_date=date,previous_observation_date=previous,retrieved_at=received,value=100,change=1)
def snapshot(at): return dict(completed_at=at,items=[item(received=at)])

class ClockTests(unittest.TestCase):
    def test_cutoff_excludes_even_one_second_late(self):
        at=c.stamp('2026-10-01T08:20:00+09:00')
        self.assertTrue(c.assess(item(received=at.isoformat()),P,at)['data_eligible'])
        self.assertEqual(c.assess(item(received='2026-10-01T08:20:01+09:00'),P,at)['freshness_status'],'after_cutoff')
    def test_normal_nyfed_lag_not_stale(self):
        at=c.stamp('2026-10-01T08:20:00+09:00')
        for id in ('FUND_SOFR','FUND_EFFR'):
            r=c.assess(item(id,'2026-09-29','2026-09-28'),P,at)
            self.assertTrue(r['data_eligible'])
            self.assertEqual(r['expected_observation_date'],'2026-09-29')
    def test_effr_9am_and_sofr_8am_differ(self):
        at=c.stamp('2026-09-30T08:30:00-04:00')
        self.assertEqual(c.expected(P['profiles']['FUND_SOFR'],P,at)[0].isoformat(),'2026-09-29')
        self.assertEqual(c.expected(P['profiles']['FUND_EFFR'],P,at)[0].isoformat(),'2026-09-28')
    def test_bank_holiday_does_not_equal_equity_holiday(self):
        at=c.stamp('2026-10-13T08:20:00+09:00')
        self.assertEqual(c.expected(P['profiles']['US_SPX_CLOSE'],P,at)[0].isoformat(),'2026-10-12')
        self.assertEqual(c.expected(P['profiles']['FUND_EFFR'],P,at)[0].isoformat(),'2026-10-08')
    def test_weekend_uses_completed_friday(self):
        self.assertEqual(c.expected(P['profiles']['US_SPX_CLOSE'],P,c.stamp('2026-10-05T08:20:00+09:00'))[0].isoformat(),'2026-10-02')
    def test_kr_chuseok_and_substitute_holiday(self):
        at=c.stamp('2026-09-28T08:20:00+09:00')
        self.assertEqual(c.expected(P['profiles']['KR_KOSPI_CLOSE'],P,at)[0].isoformat(),'2026-09-23')
        at=c.stamp('2026-10-06T08:20:00+09:00')
        self.assertEqual(c.expected(P['profiles']['KR_KOSPI_CLOSE'],P,at)[0].isoformat(),'2026-10-02')
    def test_early_close_and_dst_use_local_clock(self):
        policy=copy.deepcopy(P);policy['calendar_review_due']='2027-01-01'
        for at,day in [('2026-11-27T18:30:00Z','2026-11-27'),('2026-11-27T17:59:00Z','2026-11-25'),('2026-03-09T20:01:00Z','2026-03-09'),('2026-03-06T20:30:00Z','2026-03-05')]:
            self.assertEqual(c.expected(P['profiles']['US_SPX_CLOSE'],policy,c.stamp(at))[0].isoformat(),day)
    def test_unknown_sla_does_not_mean_outage(self):
        r=c.assess(item(date='2026-09-29',previous='2026-09-28'),P,c.stamp('2026-10-01T08:20:00+09:00'))
        self.assertEqual(r['freshness_status'],'latest_session_not_received_publication_time_unknown')
        self.assertIsNone(r['display_change'])
    def test_gap_never_reported_as_one_day_return(self):
        r=c.assess(item(previous='2026-09-25'),P,c.stamp('2026-10-01T08:20:00+09:00'))
        self.assertTrue(r['data_eligible']);self.assertFalse(r['comparison_eligible']);self.assertIsNone(r['display_change'])
    def test_unknown_calendar_and_expired_review_fail_closed(self):
        r=c.assess(item('CREDIT_HY_OAS'),P,c.stamp('2026-10-01T08:20:00+09:00'))
        self.assertEqual(r['freshness_status'],'calendar_unverified')
        r=c.assess(item(),P,c.stamp('2026-11-01T08:20:00+09:00'))
        self.assertEqual(r['freshness_status'],'calendar_review_due');self.assertFalse(r['data_eligible'])
    def test_freeze_is_immutable_and_revisions_do_not_backfill(self):
        with tempfile.TemporaryDirectory() as d:
            c.run(snapshot('2026-09-30T23:05:00Z'),P,d)
            _,state=c.run(snapshot('2026-10-01T00:05:00Z'),P,d)
            f=Path(d)/state['frozen_path'];before=f.read_bytes()
            revised=snapshot('2026-10-01T01:05:00Z');revised['items'][0]['value']=999
            c.run(revised,P,d)
            self.assertEqual(before,f.read_bytes());self.assertEqual(json.loads(before)['items'][0]['value'],100)
    def test_first_after_cutoff_cannot_create_morning(self):
        with tempfile.TemporaryDirectory() as d:
            _,state=c.run(snapshot('2026-10-01T00:05:00Z'),P,d)
            self.assertEqual(state['status'],'no_pre_cutoff_snapshot')
            self.assertIsNone(state['frozen_path'])
    def test_tamper_is_detected(self):
        with tempfile.TemporaryDirectory() as d:
            c.run(snapshot('2026-09-30T23:05:00Z'),P,d)
            _,state=c.run(snapshot('2026-10-01T00:05:00Z'),P,d)
            f=Path(d)/state['frozen_path'];text=json.loads(f.read_text());text['items'][0]['value']=999;c.save(f,text)
            with self.assertRaisesRegex(ValueError,'hash_mismatch'): c.run(snapshot('2026-10-01T01:05:00Z'),P,d)

if __name__=='__main__': unittest.main()
