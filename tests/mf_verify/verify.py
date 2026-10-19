# -*- coding: utf-8 -*-
"""
멀티팩터 입력값 대조 시험 (1회성 · 읽기 전용)
목적: 우리 점수가 쓰는 입력값(FinanceDataReader=네이버 분기 재무, 주가)을 독립된 출처와 대조한다.
  1) 분기 매출액·영업이익·당기순이익: 네이버(FDR) vs 금융감독원 OpenDART 공시(fnlttSinglAcntAll, 연결)
  2) 주가 모멘텀 입력: FDR(네이버) 종가 vs yfinance(야후) 종가로 계산한 모멘텀 주가 평균 등락률
대조하지 않는 것(미검증): PER·PBR·ROE(공시 원자료로 같은 정의를 재현하기 어려움), 거래량.

원칙: DART_API_KEY 는 환경변수로만 받고 출력·파일·로그에 남기지 않는다(주소·예외 원문도 출력하지 않는다).
      저장소에는 아무것도 쓰지 않고 결과는 tests/mf_verify/out/ (Actions 아티팩트)에만 둔다.
공식 가이드(2026-10-19 확인): https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS003&apiId=2019020
  - 요청 https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json  인자 crtfc_key, corp_code, bsns_year, reprt_code, fs_div(CFS 연결/OFS 별도)
  - reprt_code 11013=1분기, 11012=반기, 11014=3분기, 11011=사업. 분기·반기 손익계산서의 thstrm_amount 는 3개월, thstrm_add_amount 는 누적.
  - account_id 목록은 가이드에 없다 → 응답에서 실제로 맞춘 계정(id/이름)을 결과에 기록해 잘못 맞췄는지 볼 수 있게 한다.
종료코드: 0 = 시험이 끝까지 실행됨(일치 여부와 무관) · 2 = 실행 실패(키 없음, import 실패 등)
"""
import os, sys, io, json, time, math, zipfile, urllib.request, urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
SCRIPTS = os.path.abspath(os.path.join(HERE, "..", "..", "scripts"))
sys.path.insert(0, SCRIPTS)
import multifactor_kr as mf          # 이 import 가 scripts 폴더를 import 경로에서 뺀다(calendar.py 가림 방지)

BASE = "https://opendart.fss.or.kr/api/"
N_STOCKS = int(os.environ.get("VERIFY_N", "20"))
SLEEP = 0.4
TIMEOUT = 30
TOL_ABS_EOK = 1.0        # 네이버는 억 원 단위로 반올림해 보여 주므로 ±1억 원까지는 일치로 본다
TOL_REL = 0.003          # 또는 ±0.3%
REPRT = {1: "11013", 2: "11012", 3: "11014"}   # 분기 → 보고서 코드 (4분기는 사업보고서 − 3분기 누적)
ACC = {
    "rev": {"ids": {"ifrs-full_Revenue", "ifrs_Revenue"}, "names": ("매출액", "수익(매출액)", "영업수익", "매출", "수익")},
    "op": {"ids": {"dart_OperatingIncomeLoss"}, "names": ("영업이익", "영업이익(손실)", "영업손익", "영업이익 (손실)")},
    "ni": {"ids": {"ifrs-full_ProfitLoss", "ifrs_ProfitLoss"}, "names": ("당기순이익", "당기순이익(손실)", "분기순이익", "반기순이익", "분기순이익(손실)", "반기순이익(손실)", "당기순손익", "분기연결당기순이익", "반기연결당기순이익")},
    "ni_owner": {"ids": {"ifrs-full_ProfitLossAttributableToOwnersOfParent", "ifrs_ProfitLossAttributableToOwnersOfParent"}, "names": ()},
}
RESULTS = {"stocks": [], "price": []}


def now_iso(): return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def key():
    return os.environ.get("DART_API_KEY", "").strip()


def http_json(path, params):
    """OpenDART 호출. 실패해도 주소·키가 담긴 원문은 돌려주지 않는다."""
    url = BASE + path + "?" + urllib.parse.urlencode(dict(params, crtfc_key=key()))
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8")), None
    except Exception as ex:
        return None, type(ex).__name__


def load_corp_map(wanted):
    """corpCode.xml(zip) → {stock_code: corp_code}. 공식 /api/corpCode.xml (저장소의 corp_code_cache.py 와 같은 방식)."""
    url = BASE + "corpCode.xml?" + urllib.parse.urlencode({"crtfc_key": key()})
    try:
        with urllib.request.urlopen(url, timeout=60) as r: blob = r.read()
        zf = zipfile.ZipFile(io.BytesIO(blob))
        root = ET.fromstring(zf.read(zf.namelist()[0]).decode("utf-8"))
    except Exception as ex:
        return None, type(ex).__name__
    out = {}
    for el in root.iter("list"):
        sc = (el.findtext("stock_code") or "").strip()
        if sc in wanted: out[sc] = (el.findtext("corp_code") or "").strip()
    return out, None


def to_num(s):
    try: return float(str(s).replace(",", "").strip())
    except Exception: return None


def pick_amount(rows, item, field):
    """rows(IS/CIS) 에서 계정을 찾아 field 금액(원)과 맞춘 계정(id, 이름)을 돌려준다. 못 찾으면 (None, None)."""
    spec = ACC[item]
    cand = [r for r in rows if r.get("sj_div") in ("IS", "CIS")]
    for r in cand:                                   # 1순위: 표준계정ID
        if r.get("account_id") in spec["ids"]:
            v = to_num(r.get(field))
            if v is not None: return v, (r.get("account_id"), r.get("account_nm"))
    for r in cand:                                   # 2순위: 계정명
        if (r.get("account_nm") or "").strip() in spec["names"]:
            v = to_num(r.get(field))
            if v is not None: return v, (r.get("account_id"), r.get("account_nm"))
    return None, None


def fetch_statement(corp, year, reprt):
    """연결(CFS) 먼저, 자료가 없으면(013) 별도(OFS). → (rows, fs_div, error)"""
    for fs in ("CFS", "OFS"):
        d, err = http_json("fnlttSinglAcntAll.json", {"corp_code": corp, "bsns_year": str(year), "reprt_code": reprt, "fs_div": fs})
        time.sleep(SLEEP)
        if err: return None, fs, err
        st = str(d.get("status"))
        if st == "000": return d.get("list", []), fs, None
        if st == "013": continue                    # 조회된 데이터 없음 → 다음 구분 시도
        return None, fs, "status_" + st
    return None, None, "no_data"


def quarter_amounts(corp, year, q):
    """해당 분기의 3개월 금액(원) {rev, op, ni, ni_owner} 과 맞춘 계정, 사용한 재무제표 구분. 4분기는 연간 − 3분기 누적."""
    if q in REPRT:
        rows, fs, err = fetch_statement(corp, year, REPRT[q])
        if err: return None, None, fs, err
        vals, accs = {}, {}
        for it in ACC:
            v, a = pick_amount(rows, it, "thstrm_amount")
            vals[it], accs[it] = v, a
        return vals, accs, fs, None
    ann, fs1, e1 = fetch_statement(corp, year, "11011")
    q3, fs2, e2 = fetch_statement(corp, year, "11014")
    if e1 or e2: return None, None, fs1 or fs2, e1 or e2
    vals, accs = {}, {}
    for it in ACC:
        a_v, a_acc = pick_amount(ann, it, "thstrm_amount")
        c_v, _ = pick_amount(q3, it, "thstrm_add_amount")
        vals[it] = (a_v - c_v) if (a_v is not None and c_v is not None) else None
        accs[it] = a_acc
    return vals, accs, fs1, None


def close_enough(naver_eok, dart_won):
    if naver_eok is None or dart_won is None: return None
    d = dart_won / 1e8
    diff = abs(naver_eok - d)
    return diff <= TOL_ABS_EOK or diff <= TOL_REL * abs(d)


def growth(cur, prev):
    return mf.growth_pct(cur, prev, False)[0]


def verify_stock(fdr, code, name, corp):
    rec = {"code": code, "name": name, "corp_code_found": bool(corp), "quarters": []}
    try:
        q = fdr.SnapDataReader("NAVER/FINSTATE-2Q/%s" % code).dropna(subset=["영업이익"])
    except Exception as ex:
        rec["error"] = "naver_" + type(ex).__name__
        return rec
    if len(q) < 2:
        rec["error"] = "naver_quarters_lt_2"; return rec
    last2 = q.iloc[-2:]
    naver_vals, dart_vals = [], []
    for idx, row in last2.iterrows():
        year, month = idx.year, idx.month
        qq = (month - 1) // 3 + 1
        item = {"period": "%d-%02d" % (year, month), "quarter": qq}
        nv = {"rev": float(row["매출액"]), "op": float(row["영업이익"]), "ni": float(row["당기순이익"])}
        item["naver_eok"] = nv
        if not corp:
            item["error"] = "no_corp_code"; rec["quarters"].append(item); naver_vals.append(nv); dart_vals.append(None); continue
        dv, accs, fs, err = quarter_amounts(corp, year, qq)
        item["fs_div"] = fs
        if err:
            item["error"] = err; rec["quarters"].append(item); naver_vals.append(nv); dart_vals.append(None); continue
        item["dart_eok"] = {k: (None if v is None else round(v / 1e8, 1)) for k, v in dv.items()}
        item["matched_accounts"] = {k: (list(a) if a else None) for k, a in accs.items()}
        item["match"] = {"rev": close_enough(nv["rev"], dv["rev"]), "op": close_enough(nv["op"], dv["op"]),
                         "ni_total": close_enough(nv["ni"], dv["ni"]), "ni_owner": close_enough(nv["ni"], dv["ni_owner"])}
        rec["quarters"].append(item); naver_vals.append(nv); dart_vals.append(dv)
    # 증가율(우리 점수의 입력): 같은 두 분기로 계산한 값 비교
    if len(dart_vals) == 2 and dart_vals[0] and dart_vals[1]:
        g = {}
        for k in ("rev", "op", "ni"):
            gn = growth(naver_vals[1][k], naver_vals[0][k])
            gd = growth(dart_vals[1][k] / 1e8 if dart_vals[1][k] is not None else None, dart_vals[0][k] / 1e8 if dart_vals[0][k] is not None else None)
            g[k] = {"naver": None if gn is None else round(gn, 1), "dart": None if gd is None else round(gd, 1),
                    "diff_pp": None if (gn is None or gd is None) else round(abs(gn - gd), 1)}
        rec["growth"] = g
    return rec


def verify_price(fdr, code, market):
    import yfinance as yf
    out = {"code": code}
    try:
        a = fdr.DataReader(code, (datetime.now()).replace(year=datetime.now().year - 2).strftime("%Y%m%d"))
        sym = code + (".KS" if market == "KOSPI" else ".KQ")
        h = yf.Ticker(sym).history(period="2y", auto_adjust=False)
        if h is None or len(h) < 250: out["error"] = "yfinance_rows_lt_250"; return out
        ya = h["Close"].dropna()
        out["last_dates"] = [str(a.index[-1].date()), str(ya.index[-1].date())]
        ma, _ = mf.momentum_price(a["Close"])
        mb, _ = mf.momentum_price(ya)
        out["mom_fdr"] = None if ma is None else round(ma, 2); out["mom_yf"] = None if mb is None else round(mb, 2)
        out["diff_pp"] = None if (ma is None or mb is None) else round(abs(ma - mb), 2)
        # 같은 날짜끼리 종가 비교(마지막 행은 장 마감 후에도 바뀔 수 있어 제외)
        ya.index = ya.index.tz_localize(None).normalize()
        j = a["Close"].iloc[:-1].to_frame("fdr").join(ya.to_frame("yf"), how="inner").tail(120)
        rel = ((j["fdr"] - j["yf"]).abs() / j["yf"])
        out["same_date_rows"] = int(len(j)); out["close_within_0p5pct"] = int((rel <= 0.005).sum())
    except Exception as ex:
        out["error"] = type(ex).__name__
    return out


def save():
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "result.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump({"generated_at": now_iso(), "tolerance": {"abs_eok": TOL_ABS_EOK, "rel": TOL_REL}, **RESULTS}, f, ensure_ascii=False, indent=1)
    L = ["## 멀티팩터 입력값 대조 (네이버·야후 vs 금감원 OpenDART)", "",
         "- 실행: %s · 대상 시가총액 상위 %d종목(우선주 등 제외) · 허용오차 ±%g억 또는 ±%.1f%%" % (now_iso(), len(RESULTS["stocks"]), TOL_ABS_EOK, TOL_REL * 100),
         "- **미검증**: PER·PBR·ROE·거래량은 대조하지 않았다. 공시와 일치해도 값의 정의(지배주주/총이익 등)는 아래 표에서 확인해야 한다.", ""]
    tot = {"rev": [0, 0], "op": [0, 0], "ni_total": [0, 0], "ni_owner": [0, 0]}
    for s in RESULTS["stocks"]:
        for q in s["quarters"]:
            for k, v in (q.get("match") or {}).items():
                if v is None: continue
                tot[k][1] += 1; tot[k][0] += 1 if v else 0
    L += ["### 분기 금액 일치 (분기 단위 건수)", "", "| 항목 | 일치/비교 |", "|---|---|"]
    names = {"rev": "매출액", "op": "영업이익", "ni_total": "당기순이익(총)", "ni_owner": "당기순이익(지배주주)"}
    for k, (a, b) in tot.items(): L.append("| %s | %d / %d |" % (names[k], a, b))
    L += ["", "### 종목별 (네이버 억 원 → DART 억 원)", "", "| 종목 | 분기 | 매출 N→D | 영업이익 N→D | 순이익 N→D(총/지배) | 일치(매출/영업/순총/순지배) | 오류 |", "|---|---|---|---|---|---|---|"]
    for s in RESULTS["stocks"]:
        if s.get("error"): L.append("| %s | - | - | - | - | - | %s |" % (s["name"], s["error"])); continue
        for q in s["quarters"]:
            n, d, m = q["naver_eok"], q.get("dart_eok") or {}, q.get("match") or {}
            f = lambda v: "-" if v is None else ("O" if v else "X")
            L.append("| %s | %s | %g→%s | %g→%s | %g→%s/%s | %s/%s/%s/%s | %s |" % (
                s["name"], q["period"], n["rev"], d.get("rev", "-"), n["op"], d.get("op", "-"), n["ni"], d.get("ni", "-"), d.get("ni_owner", "-"),
                f(m.get("rev")), f(m.get("op")), f(m.get("ni_total")), f(m.get("ni_owner")), q.get("error", "")))
    L += ["", "### 증가율 대조 (점수의 직접 입력, %p 차이)", "", "| 종목 | 매출 N/D | 영업이익 N/D | 순이익 N/D |", "|---|---|---|---|"]
    for s in RESULTS["stocks"]:
        g = s.get("growth")
        if not g: continue
        L.append("| %s | %s/%s | %s/%s | %s/%s |" % (s["name"], g["rev"]["naver"], g["rev"]["dart"], g["op"]["naver"], g["op"]["dart"], g["ni"]["naver"], g["ni"]["dart"]))
    acc = {}
    for s in RESULTS["stocks"]:
        for q in s["quarters"]:
            for k, a in (q.get("matched_accounts") or {}).items():
                if a: acc[(k, a[0], a[1])] = acc.get((k, a[0], a[1]), 0) + 1
    L += ["", "### 맞춘 계정(ID 가이드가 없어 응답에서 찾은 계정. 엉뚱한 계정을 맞췄는지 확인용)", "", "| 항목 | account_id | account_nm | 건수 |", "|---|---|---|---|"]
    for (k, i, n), c in sorted(acc.items()): L.append("| %s | %s | %s | %d |" % (k, i, n, c))
    L += ["", "### 주가 모멘텀 입력 (FDR=네이버 vs yfinance=야후)", "", "| 종목 | 모멘텀(FDR) | 모멘텀(야후) | 차이 %p | 같은 날 종가 0.5% 이내 | 오류 |", "|---|---|---|---|---|---|"]
    for p in RESULTS["price"]:
        L.append("| %s | %s | %s | %s | %s/%s | %s |" % (p.get("name", p["code"]), p.get("mom_fdr", "-"), p.get("mom_yf", "-"), p.get("diff_pp", "-"), p.get("close_within_0p5pct", "-"), p.get("same_date_rows", "-"), p.get("error", "")))
    with open(os.path.join(OUT, "result.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L) + "\n")


def main():
    if not key():
        print("DART_API_KEY 가 설정되지 않았다(키 값은 출력하지 않는다)."); return 2
    try:
        import FinanceDataReader as fdr
    except BaseException as ex:
        print("FinanceDataReader import 실패:", type(ex).__name__); return 2
    rows = mf.FdrFetcher().listing()
    targets, _ = mf.pre_filter(rows, N_STOCKS)
    codes = {r["code"] for r in targets}
    cmap, err = load_corp_map(codes)
    if cmap is None:
        print("corpCode.xml 실패:", err); RESULTS["corp_map_error"] = err; save(); return 0
    for r in targets:
        RESULTS["stocks"].append(verify_stock(fdr, r["code"], r["name"], cmap.get(r["code"])))
        save()
    for r in targets[: min(10, len(targets))]:
        p = verify_price(fdr, r["code"], r["market"]); p["name"] = r["name"]
        RESULTS["price"].append(p); save(); time.sleep(0.5)
    save(); print("완료: %d종목 대조(결과 일치 여부는 result.md 참고)" % len(RESULTS["stocks"]))
    return 0


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    os._exit(code)
