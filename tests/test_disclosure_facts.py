import unittest,pathlib,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
import disclosure_facts as F
class Facts(unittest.TestCase):
    def setUp(self):self.text=(pathlib.Path(__file__).parent/'fixtures/monthly-sales-20260914800398.txt').read_text(encoding='utf-8')
    def test_real_receipt(self):
        r=F.extract(self.text);self.assertEqual(len(r['reportedFacts']),5);self.assertEqual(r['reportedFacts'][0]['value'],1606222);self.assertEqual([x['computed'] for x in r['comparisons']],[-22.63,19.37,47.52]);self.assertTrue(all(x['status']=='일치' for x in r['comparisons']))
    def test_units_required(self):self.assertEqual(F.extract(self.text.replace('백만원','억원'))['reportedFacts'],[])
    def test_missing_headers(self):self.assertEqual(F.extract(self.text.replace('당해실적','잘못된 헤더'))['reportedFacts'],[])
    def test_mismatch(self):self.assertEqual(F.extract(self.text.replace('-22.63','-99.99'))['comparisons'][0]['status'],'확인 필요')
    def test_zero_denominator(self):self.assertIsNone(F.extract(self.text.replace('2,075,919','0'))['comparisons'][0]['computed'])
if __name__=='__main__':unittest.main()
