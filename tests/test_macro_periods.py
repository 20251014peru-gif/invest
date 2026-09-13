import unittest, importlib.util, pathlib, sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
import macro, macro_extra
spec=importlib.util.spec_from_file_location('periods',pathlib.Path(__file__).resolve().parents[1]/'scripts/macro_periods.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Periods(unittest.TestCase):
    def test_missing_month_not_shifted(self):
        rows=[('2025-01-01',100),('2025-03-01',200),('2026-01-01',110),('2026-02-01',500),('2026-03-01',220)]
        self.assertEqual(m.transform(rows,'yoy'),[{'period':'2026-01-01','value':10},{'period':'2026-03-01','value':10}])
    def test_missing_prev_month_not_invented(self):
        self.assertEqual(m.transform([('2026-01-01',5),('2026-03-01',8)],'diff'),[])
    def test_zero_denominator_and_missing_value(self):
        self.assertEqual(m.transform([('2026-01-01',0),('2026-02-01',5)],'mom_pct'),[])
    def test_both_collectors_match_calendar_month(self):
        rows=[('2025-07-01',100),('2025-08-01',200),('2026-07-01',110),('2026-08-01',220)]
        self.assertEqual(macro.derive_yoy(rows),[('2026-07-01',10),('2026-08-01',10)])
        self.assertEqual(macro_extra.yoy(rows),('2026-08-01',10,10))
if __name__=='__main__':unittest.main()
