import unittest, pathlib, sys, copy
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
import refresh_event_source as R

class Refresh(unittest.TestCase):
    def test_bounded_reason_without_secret_leak(self):
        for error,expected in [(ValueError('DOCUMENT_TOO_LARGE'),'DOCUMENT_TOO_LARGE'),(ValueError('secret-url'),'DOCUMENT_FORMAT')]:
            with patch.object(R.DS.urllib.request,'urlopen',side_effect=error):
                self.assertEqual(R.DS.fetch('20260914800398','FAKE')['reason'],expected)
    def test_pending_bounded_order_and_retries(self):
        rows=[{'rcept_no':'retry','sourceAttempts':1},{'rcept_no':'done','sourceStatus':'AVAILABLE'},{'rcept_no':'exhausted','sourceAttempts':2},{'rcept_no':'new','sourceAttempts':0}]
        with patch.object(R.ER,'_load',return_value={'events':rows}),patch.object(R,'run') as run:
            self.assertEqual(R.pending(1),1);run.assert_called_once_with('new')
        with self.assertRaises(ValueError):R.pending(31)
    def test_reuses_available_source_without_key_or_network(self):
        receipt='20260914800398'
        event={'rcept_no':receipt,'sourceDocument':{'status':'AVAILABLE','text':'existing'}}
        index={'events':[{'rcept_no':receipt,'date':'20260914'}]};daily={'events':[event]}
        with patch.object(R.ER,'_load',side_effect=[index,daily]),patch.object(R.ER,'_rcept',return_value=receipt),patch.object(R.ER,'_save') as save,patch.object(R.DS,'fetch') as fetch,patch.dict(R.os.environ,{},clear=True):
            R.run(receipt);fetch.assert_not_called();save.assert_called_once();self.assertIn('comparisons',event['sourceDocument'])
    def test_missing_source_fetches_once_and_updates_index(self):
        receipt='20260914800401';event={'rcept_no':receipt};row={'rcept_no':receipt,'date':'20260914'}
        with patch.object(R.ER,'_load',side_effect=[{'events':[row]},{'events':[event]}]),patch.object(R.ER,'_rcept',return_value=receipt),patch.object(R.ER,'_save'),patch.object(R.ER,'_summary',return_value={'sourceStatus':'UNAVAILABLE','sourceAttempts':1}),patch.object(R.DS,'fetch',return_value={'status':'UNAVAILABLE','reason':'DART_014'}) as fetch,patch.dict(R.os.environ,{'DART_API_KEY':'FAKE'}):
            R.run(receipt);fetch.assert_called_once_with(receipt,'FAKE');self.assertEqual(row['sourceAttempts'],1);self.assertEqual(event['sourceDocument']['reason'],'DART_014')
if __name__=='__main__':unittest.main()
