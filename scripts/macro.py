# v 20260907-1740  macro.py — CYGNUS 정적판의 수집기. data/indicators.json 을 읽어 FRED(공식)·ECOS(공식, ECOS_KEY)·Yahoo(보조) 값을 모은다. derive=yoy 는 12개월 전 대비 %. derived=차이 파생(신용 스프레드). key_stats=ECOS 100대 지표 한 판(facts/kr_key.json).
# 쓰기: facts/macro.json(최신), facts/macro_history.json(일별 누적), data/status.json(job macro)
# 규칙: 시각 3칸(as_of=시장 기준일, published=출처 발표 시각(모르면 빈칸), collected_at=수집 KST). 실패한 지표는 값 대신 error 를 남긴다(조용한 실패 금지).
import json, os, sys, csv, io, datetime as dt, urllib.request, urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
KST = dt.timezone(dt.timedelta(hours=9))
def kst_now(): return dt.datetime.now(KST)
def kst_iso(d=None): return (d or kst_now()).replace(microsecond=0).isoformat()

def load(p, default):
    try:
        with open(p, encoding="utf-8") as f: return json.load(f)
    except FileNotFoundError: return default
    except (json.JSONDecodeError, ValueError):
        print(f"[경고] {p} JSON 손상 — 기본값으로 진행(자동 복구)"); return default
def save(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f: json.dump(obj, f, ensure_ascii=False, indent=2)

# ---- 출처별 fetch: [(date, value)] 오름차순, 최근 2개 이상 ----
def fetch_fred(series):
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"
    raw = urllib.request.urlopen(url, timeout=20).read().decode("utf-8")
    rows = []
    for r in csv.DictReader(io.StringIO(raw)):
        v = r.get(series) or r.get("VALUE") or ""
        if v.strip() in ("", "."): continue
        rows.append((r["observation_date"] if "observation_date" in r else r["DATE"], float(v)))
    return rows[-20:]                                                    # yoy 파생(13개월)에 충분히

def fetch_yahoo(symbol):
    import yfinance as yf
    h = yf.Ticker(symbol).history(period="10d", auto_adjust=False)
    if h is None or len(h) == 0: return []
    return [(i.to_pydatetime().date().isoformat(), float(v)) for i, v in h["Close"].dropna().items()][-5:]

def fetch_stooq(symbol):
    """stooq.com 일봉 CSV(무키). 열: Date,Open,High,Low,Close,Volume"""
    url = f"https://stooq.com/q/d/l/?s={symbol}&i=d"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (invest macro collector)"})
    raw = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "replace")
    rows = [(r["Date"], float(r["Close"])) for r in csv.DictReader(io.StringIO(raw)) if r.get("Close") not in (None, "", "N/D")]
    if not rows: raise RuntimeError("stooq 응답 비어 있음(심볼 확인)")
    return rows[-5:]

def fetch_yahoo_relay(symbol, relay):
    """중계서버(Cloudflare Worker) 경유 야후 차트 1일 — GitHub 서버가 야후에 직접 막혀도 중계로 우회.
    반환: [(전일자, 전일종가), (오늘, 현재가)] — run() 의 change_pct 계산에 맞춤."""
    yurl = "https://query1.finance.yahoo.com/v8/finance/chart/%s?range=1d&interval=1d" % symbol
    url = relay.rstrip("/") + "/?url=" + urllib.parse.quote(yurl, safe="")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (macro)"})
    d = json.loads(urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "replace"))
    m = d["chart"]["result"][0]["meta"]
    price = m.get("regularMarketPrice")
    pv = m.get("chartPreviousClose") or m.get("previousClose")
    if price is None:
        raise RuntimeError("야후 응답에 가격 없음")
    today = kst_now().date().isoformat()
    rows = []
    if pv is not None:
        rows.append(((kst_now().date() - dt.timedelta(days=1)).isoformat(), float(pv)))
    rows.append((today, float(price)))
    return rows

def fetch_ecos(ecos, relay=""):
    """한국은행 ECOS OpenAPI(무료 키, GitHub Secret ECOS_KEY). ecos={stat,item,cycle(M|D|A)}. 응답 row[].TIME/DATA_VALUE.
    반환 [(YYYY-MM-DD|YYYY-MM, value)] 최근 20개. 키 없거나 코드 틀리면 예외(조용한 실패 금지)."""
    key = os.environ.get("ECOS_KEY", "").strip()
    if not key: raise RuntimeError("ECOS_KEY 없음(GitHub Secret)")
    cyc = ecos.get("cycle", "M"); now = kst_now()
    fmt = {"D": "%Y%m%d", "M": "%Y%m", "A": "%Y"}[cyc]
    start = (now - dt.timedelta(days={"D": 60, "M": 800, "A": 3650}[cyc])).strftime(fmt); end = now.strftime(fmt)
    url = f"https://ecos.bok.or.kr/api/StatisticSearch/{key}/json/kr/1/100/{ecos['stat']}/{cyc}/{start}/{end}/{ecos['item']}"
    if relay:                                                             # GitHub(미국 IP)는 ecos.bok.or.kr 에 직접 못 붙음(2026-09-07 timeout 확인) → 중계서버 경유
        url = relay.rstrip("/") + "/?url=" + urllib.parse.quote(url, safe="")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (macro)"})
    d = json.loads(urllib.request.urlopen(req, timeout=40).read().decode("utf-8", "replace"))
    if "RESULT" in d: raise RuntimeError("ECOS: " + str(d["RESULT"].get("MESSAGE", d["RESULT"]))[:120])
    rows = []
    for r in d.get("StatisticSearch", {}).get("row", []):
        t, v = str(r.get("TIME", "")), str(r.get("DATA_VALUE", "")).strip()
        if not v: continue
        t = t[:4] + "-" + t[4:6] + ("-" + t[6:8] if len(t) >= 8 else "")
        rows.append((t, float(v)))
    if not rows: raise RuntimeError("ECOS 응답 비어 있음(통계표·항목 코드 확인)")
    return rows[-20:]

def derive_yoy(rows):
    """월간 지수 → 전년동월비 %. rows 오름차순, 13개 이상 필요. 반환 [(전월, 전월yoy), (최신, yoy)]"""
    if len(rows) < 14: raise RuntimeError(f"yoy 계산에 14개월 필요, {len(rows)}개")
    yoy = lambda i: round((rows[i][1] / rows[i - 12][1] - 1) * 100, 2)
    return [(rows[-2][0], yoy(-2)), (rows[-1][0], yoy(-1))]

FETCH = {"fred": fetch_fred, "yahoo": fetch_yahoo, "stooq": fetch_stooq}

def judge(ind, value, change_pct):
    """달님 규칙(indicators.json thresholds)으로 우호/주의/부담 판정. 규칙 없으면 빈칸."""
    t = ind.get("thresholds") or {}
    if not t or value is None: return ""
    if "strong_pct" in t and change_pct is not None:
        return "강" if change_pct >= t["strong_pct"] else "약" if change_pct <= t["weak_pct"] else "중립"
    if "bad_min" in t and value >= t["bad_min"]: return "부담" if "warn_min" not in t else "위험"
    if "warn_min" in t and value >= t["warn_min"]: return "주의"
    if "good_max" in t and value <= t["good_max"]: return "우호" if "warn_min" not in t else "안정"
    if "good_min" in t: return "확장" if value >= t["good_min"] else "수축"
    return "중립"

def run(fetch_map=None, manual=None):
    fetch_map = fetch_map or FETCH
    cfg = load(P("data", "indicators.json"), None)
    if not cfg or cfg.get("schema") != "indicators/1": raise SystemExit("data/indicators.json 규격(indicators/1) 아님")
    manual = manual if manual is not None else load(P("raw", "manual_macro.json"), {"items": {}}).get("items", {})
    out, errors = [], []
    for ind in cfg["items"]:
        rec = {"id": ind["id"], "name": ind["name"], "unit": ind["unit"], "axis": ind["axis"], "source": ind["source"],
               "symbol": ind["symbol"], "official": ind["official"], "rule": ind.get("rule", ""),
               "value": None, "prev": None, "change_pct": None, "as_of": "", "published": "", "collected_at": kst_iso(), "judge": "", "error": "", "pending": False}
        rows = None
        try:
            if ind["source"] == "manual":
                m = manual.get(ind["id"])
                if m: rec.update({"value": float(m["value"]), "as_of": m.get("as_of", ""), "published": m.get("published", "")})
                elif ind.get("optional"): rec["pending"] = True          # 참고 지표 미입력 = 오류 아님
                else: rec["error"] = "수동 입력 없음(raw/manual_macro.json)"
            elif ind["source"] == "yahoo_relay":
                relay = cfg.get("relay", "")
                try:
                    if not relay: raise RuntimeError("relay 주소 없음(indicators.json)")
                    rows = fetch_yahoo_relay(ind["yahoo"], relay)
                    if len(rows) < 1: raise RuntimeError("데이터 없음")
                except Exception as e1:                                  # 중계 실패 → FRED 예비(있으면)
                    fbc = ind.get("fred_fallback")
                    if not fbc: raise
                    rows = fetch_fred(fbc)
                    if len(rows) < 1: raise RuntimeError(f"중계 {e1} / FRED 예비도 없음")
                    rec["source"] = "fred(예비)"; rec["symbol"] = fbc
            elif ind["source"] == "ecos":
                if not os.environ.get("ECOS_KEY", "").strip() and ind.get("optional"):
                    rec["pending"] = True                                 # 키 없음 = 미설정(경고 띠 아님, 화면엔 '미설정')
                else:
                    rows = fetch_ecos(ind["ecos"], cfg.get("relay", ""))
            else:
                rows = fetch_map[ind["source"]](ind["symbol"])
                if len(rows) < 1: raise RuntimeError("데이터 없음")
            if rows is not None and ind.get("derive") == "yoy":
                rows = derive_yoy(rows)
            if rows is not None:                                          # yahoo_relay·else 공통: 받아온 값을 rec 에 넣는다
                rec["as_of"], rec["value"] = rows[-1]
                if len(rows) >= 2:
                    rec["prev"] = rows[-2][1]
                    rec["change_pct"] = round((rec["value"] - rec["prev"]) / rec["prev"] * 100, 2) if rec["prev"] else None
            if rec["value"] is not None:
                rec["value"] = round(rec["value"], 4); rec["judge"] = judge(ind, rec["value"], rec["change_pct"])
        except Exception as e:
            rec["error"] = f"{type(e).__name__}: {e}"[:200]; errors.append(f"{ind['id']}: {rec['error']}")
        out.append(rec)
    # 파생(설정 data/indicators.json.derived): a−b 차이. 예: 신용 스프레드 AA-−국고3년
    v = {r["id"]: r for r in out}
    for dv in cfg.get("derived", []):
        a, b = v.get(dv["a"], {}), v.get(dv["b"], {})
        rec = {"id": dv["id"], "name": dv["name"], "unit": dv.get("unit", "%p"), "axis": dv["axis"], "source": "derived", "symbol": f"{dv['a']}-{dv['b']}",
               "official": dv.get("official", True), "rule": dv.get("rule", ""), "value": None, "prev": None, "change_pct": None, "as_of": "", "published": "",
               "collected_at": kst_iso(), "judge": "", "error": "", "pending": False}
        if a.get("value") is not None and b.get("value") is not None:
            rec["value"] = round(a["value"] - b["value"], 3); rec["as_of"] = a.get("as_of", "")
            if a.get("prev") is not None and b.get("prev") is not None: rec["prev"] = round(a["prev"] - b["prev"], 3)
            rec["judge"] = judge(dv, rec["value"], None)
        else:
            rec["error"] = f"재료 없음({dv['a']} 또는 {dv['b']})"; errors.append(f"{dv['id']}: {rec['error']}")
        out.append(rec)
    if v.get("us10y", {}).get("value") is not None and v.get("us2y", {}).get("value") is not None:
        out.append({"id": "spread_10_2", "name": "장단기차 10y−2y", "unit": "%p", "axis": "bond_curve", "source": "derived", "symbol": "DGS10-DGS2",
                    "official": True, "rule": "0 아래=역전", "value": round(v["us10y"]["value"] - v["us2y"]["value"], 3), "prev": None, "change_pct": None,
                    "as_of": v["us10y"]["as_of"], "published": "", "collected_at": kst_iso(), "judge": "역전" if v["us10y"]["value"] < v["us2y"]["value"] else "정상", "error": ""})
    # 한국 경제 한 판: ECOS 100대 통계지표 1회 호출 → facts/kr_key.json (판정 없음, 참고표). 실패해도 축 수집은 계속
    ks = cfg.get("key_stats") or {}
    if ks.get("enabled"):
        try:
            key = os.environ.get("ECOS_KEY", "").strip()
            if not key: raise RuntimeError("ECOS_KEY 없음")
            url = f"https://ecos.bok.or.kr/api/KeyStatisticList/{key}/json/kr/1/200"
            relay = cfg.get("relay", "")
            if relay: url = relay.rstrip("/") + "/?url=" + urllib.parse.quote(url, safe="")
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (macro)"})
            kd = json.loads(urllib.request.urlopen(req, timeout=40).read().decode("utf-8", "replace"))
            if "RESULT" in kd: raise RuntimeError("ECOS: " + str(kd["RESULT"].get("MESSAGE", ""))[:120])
            rows = kd.get("KeyStatisticList", {}).get("row", [])
            if not rows: raise RuntimeError("KeyStatisticList 비어 있음")
            items_k = [{"class": r.get("CLASS_NAME", ""), "name": r.get("KEYSTAT_NAME", ""), "value": r.get("DATA_VALUE", ""), "as_of": r.get("CYCLE", ""), "unit": r.get("UNIT_NAME", "")} for r in rows]
            save(P(ks.get("file", "facts/kr_key.json").split("/")[0], *ks.get("file", "facts/kr_key.json").split("/")[1:]),
                 {"schema": "kr_key/1", "source": "ECOS KeyStatisticList(100대 통계지표)", "collected_at": kst_iso(), "count": len(items_k), "items": items_k})
            print(f"한국 경제 한 판 {len(items_k)}개 저장")
        except Exception as e:
            errors.append(f"kr_key: {type(e).__name__}: {e}"[:200])
    ok = sum(1 for r in out if r["value"] is not None)
    save(P("facts", "macro.json"), {"schema": "macro/1", "version": "v 20260907-1740", "collected_at": kst_iso(), "ok": ok, "total": len(out), "items": out})
    # 이력: 날짜(KST) 키로 값만
    hist = load(P("facts", "macro_history.json"), {"schema": "macro_history/1", "days": {}})
    today = kst_now().date().isoformat()
    hist["days"][today] = {r["id"]: r["value"] for r in out if r["value"] is not None}
    keep = sorted(hist["days"])[-int(cfg.get("history_days", 400)):]
    hist["days"] = {k: hist["days"][k] for k in keep}; hist["updated"] = kst_iso()
    save(P("facts", "macro_history.json"), hist)
    # status
    st = load(P("data", "status.json"), {"schema": "status/1", "jobs": []})
    status = "ok" if not errors else ("fail" if ok == 0 else "ok")
    job = {"id": "macro", "name": "매크로 수집", "status": status, "ran": kst_iso(), "due": kst_iso(kst_now() + dt.timedelta(hours=30)),
           "cause": ("; ".join(errors)[:300] if errors else ""), "fix": ("출처 주소·심볼(data/indicators.json) 확인. 전부 실패면 FRED/Yahoo 접속 문제" if errors else ""),
           "link": "cygnus.html", "note": f"{ok}/{len(out)} 지표"}
    st["jobs"] = [j for j in st.get("jobs", []) if j.get("id") != "macro"] + [job]; st["updated"] = kst_iso()
    save(P("data", "status.json"), st)
    print(f"매크로 {ok}/{len(out)} 지표 수집" + (f" · 실패 {len(errors)}: " + "; ".join(errors) if errors else ""))
    return ok, errors

if __name__ == "__main__":
    ok, errors = run()
    if ok == 0: sys.exit(1)
