import json,sys,unittest,tempfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import report_sources as s
import report_feeds as f
import report_clock as c
from test_report_clock import P,item

class SourceTests(unittest.TestCase):
    def test_nasdaq_value_and_new_york_date(self):
        rows=s.nasdaq_rows(json.dumps({'iTotalRecords':1,'aaData':[{'TimeStamp':'/Date(1790740800000)/','Value':12628.62375,'Close':None,'NetChange':999}]}))
        self.assertEqual(rows,[('2026-09-30',12628.62375)])
    def test_truncated_response_rejected(self):
        with self.assertRaises(ValueError):s.nasdaq_rows('{"iTotalRecords":2,"aaData":[]}')
    def test_treasury_exact_maturity(self):
        raw=b'<feed xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata" xmlns:d="http://schemas.microsoft.com/ado/2007/08/dataservices"><m:properties><d:NEW_DATE>2026-09-30T00:00:00</d:NEW_DATE><d:BC_2YEAR>4.88</d:BC_2YEAR><d:BC_10YEAR>5.29</d:BC_10YEAR></m:properties></feed>'
        self.assertEqual(s.treasury_rows(raw,'BC_10YEAR'),[('2026-09-30','5.29')])
        with self.assertRaises(ValueError):s.treasury_rows(raw,'BC_1YEAR')
    def test_rounding_vs_real_mismatch(self):
        p=[{'date':'2026-09-29','value':12629.1613},{'date':'2026-09-30','value':12628.62375}]
        b=[{'date':'2026-09-29','value':12629.16}]
        self.assertEqual(s.compare(p,b,.00501)['status'],'matched_overlap_primary_newer')
        b[0]['value']=12500
        self.assertEqual(s.compare(p,b,.00501)['status'],'mismatch')
    def test_mismatch_quarantines_analysis(self):
        r=item();r['source_comparison']={'status':'mismatch','mismatches':[{'date':'2026-09-29'}]}
        a=c.assess(r,P,c.stamp('2026-10-01T08:20:00+09:00'))
        self.assertFalse(a['data_eligible']);self.assertFalse(a['window_eligible']);self.assertEqual(a['freshness_status'],'source_value_conflict')
    def test_holiday_in_window_does_not_become_trading_trend(self):
        r=item('KR_KOSPI_CLOSE');r['last_five']=[{'date':d,'value':100} for d in ['2026-09-24','2026-09-25','2026-09-28','2026-09-29','2026-09-30']]
        a=c.assess(r,P,c.stamp('2026-10-01T08:20:00+09:00'))
        self.assertTrue(a['data_eligible']);self.assertTrue(a['comparison_eligible']);self.assertFalse(a['window_eligible'])
        self.assertEqual(a['window_calendar_conflicts'],['2026-09-24','2026-09-25'])
    def test_fx_holiday_is_not_equity_holiday(self):
        self.assertTrue(c.is_session(c.dt.date(2026,9,25),P['calendars']['KR_FX_1530']))
        self.assertFalse(c.is_session(c.dt.date(2026,9,25),P['calendars']['KR_EXCHANGE']))
    def test_ice_local_holiday_and_weekend_month_end(self):
        cal=P['calendars']['ICE_GLOBAL']
        for d in [(2026,10,12),(2026,5,31),(2026,4,3)]:self.assertTrue(c.is_session(c.dt.date(*d),cal))
        self.assertFalse(c.is_session(c.dt.date(2026,10,11),cal))
    def test_nyfed_context_collection(self):
        spec=dict(id='FUND_SOFR',label='SOFR',group='funding',definition='secured',unit='%',price_type='overnight',source_url='https://www.newyorkfed.org',provider='nyfed',series='SOFR',change_unit='bp')
        raw=json.dumps({'refRates':[{'effectiveDate':'2026-09-29','type':'SOFR','percentRate':3.88,'percentPercentile99':3.97,'volumeInBillions':2967},{'effectiveDate':'2026-09-28','type':'SOFR','percentRate':3.87}]}).encode()
        with tempfile.TemporaryDirectory() as d,patch.object(f,'get',return_value=raw):r=f.collect_one(spec,{},Path(d))
        self.assertEqual(r['connection_status'],'connected');self.assertEqual(r['rate_context']['volumeInBillions'],2967)
    def test_primary_failure_keeps_same_instrument_fallback(self):
        spec={'provider':'treasury','comparison_series':'DGS10'}
        with patch.object(s,'retrieve',side_effect=ValueError('bad')),patch.object(f,'get',return_value=b'observation_date,DGS10\n2026-09-28,5.24\n2026-09-29,5.26\n'):
            result=f.fetch(spec,{})
        self.assertEqual(result[3],'fred_csv_fallback');self.assertIn('DGS10',result[2])

if __name__=='__main__':unittest.main()
