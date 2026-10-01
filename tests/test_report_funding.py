import json,sys,unittest,datetime as dt
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import report_funding as f

class FundingTests(unittest.TestCase):
    def test_iorb_daily_policy_rate_allows_weekends(self):
        r=f.parse_iorb(b'observation_date,IORB\n2026-09-26,3.90\n2026-09-27,3.90\n')
        self.assertEqual(len(r),2)
    def test_duplicate_operation_is_not_double_counted(self):
        r=dict(auctionStatus='Results',operationId='a',lastUpdated='2026-09-30 13:45:27',operationDate='2026-09-30',operationType='Repo',totalAmtAccepted=1200000000)
        at=dt.datetime(2026,10,1,tzinfo=dt.timezone.utc)
        one=f.parse_operations(json.dumps({'repo':{'operations':[r]}}),at)
        self.assertEqual(one['totals_usd']['Repo'],1200000000)
        self.assertEqual(one['classification'],'all_reported_operations_not_srf_only')
        with self.assertRaises(ValueError):f.parse_operations(json.dumps({'repo':{'operations':[r,r]}}),at)
    def test_future_result_rejected(self):
        r=dict(auctionStatus='Results',operationId='a',lastUpdated='2026-09-30 13:45:27',operationDate='2026-09-30',operationType='Repo',totalAmtAccepted=1)
        with self.assertRaises(ValueError):f.parse_operations(json.dumps({'repo':{'operations':[r]}}),dt.datetime(2026,9,29,tzinfo=dt.timezone.utc))

if __name__=='__main__':unittest.main()
