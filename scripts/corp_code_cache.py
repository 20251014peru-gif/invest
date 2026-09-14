# v 20260915-WaveB  corp_code_cache.py — OpenDART /api/corpCode.xml 로 stock_code→corp_code 캐시.
# 원칙: endpoint 추측 금지(공식 /api/corpCode.xml). API Key 는 출력·파일·로그에 절대 남기지 않는다.
# 쓰기: data/corp_codes.json   읽기: data/sectors.json(관심종목만 캐시), DART_API_KEY(env)
import os, io, json, zipfile, urllib.request, datetime as dt, xml.etree.ElementTree as ET
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__))); P=lambda *a:os.path.join(ROOT,*a)
KST=dt.timezone(dt.timedelta(hours=9))
def _key(): return os.environ.get("DART_API_KEY","").strip()

def _watch_codes():
    try: sec=json.load(open(P("data","sectors.json"),encoding="utf-8"))
    except FileNotFoundError: return set()
    return {(c.get("code") or "").strip() for s in sec.get("sectors",[]) for c in s.get("companies",[])
            if (c.get("code") or "").strip().isdigit()}

def fetch_corp_xml(key):
    url="https://opendart.fss.or.kr/api/corpCode.xml?crtfc_key="+key
    with urllib.request.urlopen(url, timeout=60) as r: blob=r.read()
    zf=zipfile.ZipFile(io.BytesIO(blob)); name=zf.namelist()[0]
    return zf.read(name).decode("utf-8")

def build():
    key=_key()
    if not key: return {"ok":False,"reason":"DART_API_KEY 미설정"}
    watch=_watch_codes()
    root=ET.fromstring(fetch_corp_xml(key)); now=dt.datetime.now(KST).replace(microsecond=0).isoformat()
    rows={}
    for it in root.iter("list"):
        sc=(it.findtext("stock_code") or "").strip()
        if len(sc)==6 and (not watch or sc in watch):
            rows[sc]={"stock_code":sc,"corp_code":(it.findtext("corp_code") or "").strip(),
                      "corp_name":(it.findtext("corp_name") or "").strip(),
                      "modify_date":(it.findtext("modify_date") or "").strip(),"updated_at":now}
    out={"schema":"corp_codes/1","updated":now,"count":len(rows),"map":rows}
    with open(P("data","corp_codes.json"),"w",encoding="utf-8",newline="\n") as f: json.dump(out,f,ensure_ascii=False,indent=2)
    return {"ok":True,"count":len(rows),"watch":len(watch)}

def load_map():
    try: return json.load(open(P("data","corp_codes.json"),encoding="utf-8")).get("map",{})
    except FileNotFoundError: return {}

if __name__=="__main__":
    r=build(); print("corp_code cache:", {k:v for k,v in r.items()})
