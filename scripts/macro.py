# v 20260904-1810  macro.py — CYGNUS 정적판의 수집기. data/indicators.json 을 읽어 FRED(공식)·Yahoo(보조) 값을 모은다.
# 쓰기: facts/macro.json(최신), facts/macro_history.json(일별 누적), data/status.json(job macro)
# 규칙: 시각 3칸(as_of=시장 기준일, published=출처 발표 시각(모르면 빈칸), collected_at=수집 KST). 실패한 지표는 값 대신 error 를 남긴다(조용한 실패 금지).
import json, os, sys, csv, io, datetime as dt, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
KST = dt.timezone(dt.timedelta(hours=9))
def kst_now(): return dt.datetime.now(KST)
def kst_iso(d=None): return (d or kst_now()).replace(microsecond=0).isoformat()

def load(p, default):
    try:
        with open(p, encoding="utf-8") as f: return json.load(f)
    except FileNotFoundError: return default
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
    return rows[-5:]

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
               "value": None, "prev": None, "change_pct": None, "as_of": "", "published": "", "collected_at": kst_iso(), "judge": "", "error": ""}
        try:
            if ind["source"] == "manual":
                m = manual.get(ind["id"])
                if m: rec.update({"value": float(m["value"]), "as_of": m.get("as_of", ""), "published": m.get("published", "")})
                else: rec["error"] = "수동 입력 없음(raw/manual_macro.json)"
            else:
                try:
                    rows = fetch_map[ind["source"]](ind["symbol"])
                    if len(rows) < 1: raise RuntimeError("데이터 없음")
                except Exception as e1:                                  # 1순위 실패 → 예비 출처(있으면) 한 번 더
                    fb = ind.get("fallback")
                    if not fb or fb["source"] not in fetch_map: raise
                    rows = fetch_map[fb["source"]](fb["symbol"])
                    if len(rows) < 1: raise RuntimeError(f"1순위 {e1} / 예비도 데이터 없음")
                    rec["source"] = fb["source"] + "(예비)"; rec["symbol"] = fb["symbol"]
                rec["as_of"], rec["value"] = rows[-1]
                if len(rows) >= 2:
                    rec["prev"] = rows[-2][1]
                    rec["change_pct"] = round((rec["value"] - rec["prev"]) / rec["prev"] * 100, 2) if rec["prev"] else None
            if rec["value"] is not None:
                rec["value"] = round(rec["value"], 4); rec["judge"] = judge(ind, rec["value"], rec["change_pct"])
        except Exception as e:
            rec["error"] = f"{type(e).__name__}: {e}"[:200]; errors.append(f"{ind['id']}: {rec['error']}")
        out.append(rec)
    # 파생: 장단기차(10y-2y)
    v = {r["id"]: r for r in out}
    if v.get("us10y", {}).get("value") is not None and v.get("us2y", {}).get("value") is not None:
        out.append({"id": "spread_10_2", "name": "장단기차 10y−2y", "unit": "%p", "axis": "bond_curve", "source": "derived", "symbol": "DGS10-DGS2",
                    "official": True, "rule": "0 아래=역전", "value": round(v["us10y"]["value"] - v["us2y"]["value"], 3), "prev": None, "change_pct": None,
                    "as_of": v["us10y"]["as_of"], "published": "", "collected_at": kst_iso(), "judge": "역전" if v["us10y"]["value"] < v["us2y"]["value"] else "정상", "error": ""})
    ok = sum(1 for r in out if r["value"] is not None)
    save(P("facts", "macro.json"), {"schema": "macro/1", "version": "v 20260904-1810", "collected_at": kst_iso(), "ok": ok, "total": len(out), "items": out})
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
