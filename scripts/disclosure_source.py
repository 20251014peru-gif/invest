"""Bounded official DART original-document extraction; no model calls.
Guide: https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019003
"""
import io, re, zipfile, urllib.request, urllib.parse, datetime as dt
from html.parser import HTMLParser
MAX_BYTES=4_000_000
MAX_TEXT=16000
class Text(HTMLParser):
    def __init__(self): super().__init__(convert_charrefs=True); self.parts=[]; self.skip=0
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style'): self.skip+=1
        if tag in ('tr','p','div','br','title','section'): self.parts.append('\n')
        if tag in ('td','th'): self.parts.append(' | ')
    def handle_endtag(self,tag):
        if tag in ('script','style'): self.skip=max(0,self.skip-1)
        if tag in ('tr','p','div','title','section'): self.parts.append('\n')
    def handle_data(self,data):
        if not self.skip: self.parts.append(data)
def extract(blob,rcept_no):
    if len(blob)>MAX_BYTES: raise ValueError('DOCUMENT_TOO_LARGE')
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        files=[x for x in z.infolist() if not x.is_dir() and x.filename.lower().endswith(('.xml','.html','.htm'))]
        exact=[x for x in files if x.filename.rsplit('/',1)[-1].split('.')[0]==rcept_no]
        selected=exact if len(exact)==1 else files if len(files)==1 else []
        if len(selected)!=1: raise ValueError('AMBIGUOUS_DOCUMENT')
        info=selected[0]
        if info.file_size>MAX_BYTES: raise ValueError('DOCUMENT_TOO_LARGE')
        data=z.read(info)
    text=None
    for encoding in ('utf-8-sig','euc-kr'):
        try: text=data.decode(encoding); break
        except UnicodeDecodeError: pass
    if text is None: raise ValueError('DOCUMENT_ENCODING')
    parser=Text(); parser.feed(text)
    lines=[re.sub(r'[\t \r\f\v]+',' ',line).strip(' |') for line in ''.join(parser.parts).split('\n')]
    plain='\n'.join(line for line in lines if line)
    if len(plain)<100: raise ValueError('EMPTY_DOCUMENT')
    return {'text':plain[:MAX_TEXT],'truncated':len(plain)>MAX_TEXT,'extraction':'text-with-table-cell-separators'}
def fetch(rcept_no,key):
    result={'status':'UNAVAILABLE','rceptNo':rcept_no,'url':'https://dart.fss.or.kr/dsaf001/main.do?rcpNo='+rcept_no,'fetchedAt':dt.datetime.now(dt.timezone.utc).isoformat()}
    if not re.fullmatch(r'\d{14}',rcept_no) or not key: return {**result,'reason':'INVALID_REQUEST'}
    url='https://opendart.fss.or.kr/api/document.xml?'+urllib.parse.urlencode({'crtfc_key':key,'rcept_no':rcept_no})
    try:
        with urllib.request.urlopen(url,timeout=20) as r: blob=r.read(MAX_BYTES+1)
        if not blob.startswith(b'PK'):
            match=re.search(rb'<status>(\d+)</status>',blob)
            return {**result,'reason':'DART_'+(match.group(1).decode() if match else 'UNAVAILABLE')}
        return {**result,**extract(blob,rcept_no),'status':'AVAILABLE'}
    except Exception as e:
        # Never serialize an exception URL, because it contains the DART API key.
        return {**result,'reason':type(e).__name__}
