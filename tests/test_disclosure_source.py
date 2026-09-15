import io, zipfile, sys, pathlib, unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
import disclosure_source as D
class SourceTests(unittest.TestCase):
    def blob(self,text,name='20260914800398.xml'):
        b=io.BytesIO()
        with zipfile.ZipFile(b,'w') as z:z.writestr(name,text)
        return b.getvalue()
    def test_table_units_and_script(self):
        x=D.extract(self.blob('<html><script>secret script</script><p>잠정 실적 단위 백만원</p>'+('<tr><td>매출액</td><td>2026년 8월</td><td>1,234</td></tr>'*10)+'</html>'),'20260914800398')
        self.assertIn('매출액 | 2026년 8월 | 1,234',x['text']);self.assertNotIn('secret script',x['text'])
    def test_empty(self):
        with self.assertRaises(ValueError):D.extract(self.blob('<p>없음</p>'),'20260914800398')
    def test_truncation(self):
        x=D.extract(self.blob('<p>'+'내용 '*10000+'</p>'),'20260914800398');self.assertTrue(x['truncated']);self.assertEqual(len(x['text']),D.MAX_TEXT)
    def test_request_validation(self):self.assertEqual(D.fetch('../x','')['reason'],'INVALID_REQUEST')
if __name__=='__main__':unittest.main()
