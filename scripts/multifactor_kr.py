# -*- coding: utf-8 -*-
# v 20261019-1  multifactor_kr.py — 국내 멀티팩터 종합점수 (책 「데이터와 AI로 앞서가는 주식투자」 2장 방식)
# 읽기: FinanceDataReader(KRX 종목목록 · 주가 · 네이버 재무 스냅샷 — 모두 비공식/서드파티 경로, 약관은 미확인)
# 쓰기: analysis/multifactor_kr.json (schema multifactor_kr/1). 실패·차단 시 기존 파일을 덮어쓰지 않는다.
#
# 학습·점검용 지표다. 매수·매도 권유가 아니며 수치의 정확성은 공식 자료와 대조하지 않았다.
#
# 계산(책 2장과 같은 방식, 아래 '책과 다른 점'만 제외):
#   모멘텀 주가  = (전일+주간+월간+연간 등락률)/4        (거래일 기준 1/5/20/240일 전 종가 대비, iloc[-2/-6/-21/-241])
#   모멘텀 거래량 = 5일 평균거래량 / 20일 평균거래량 - 1  (%)
#   밸류        = PER, PBR (연간 K-IFRS 연결, 영업이익이 비어 있는 추정치 행 제외, 최신 확정값)
#   퀄리티      = 전분기 대비 매출·영업이익·당기순이익 증가율 + ROE (분기 연결, 추정치 행 제외, 최신)
#   순위(%)     = 대상 N개 안의 순위 / N × 100  (모멘텀·퀄리티는 클수록, PER·PBR은 작을수록 1등에 가까움)
#   종합점수    = 선택한 지표 순위의 평균(낮을수록 상위). 스타일별 점수는 같은 8개 순위 중 해당 지표만 평균한다.
# 책과 다른 점(의도적, 문서화):
#   1) PER·PBR이 비었거나 0 이하(적자·자본잠식)면 '최하위'로 둔다(책은 처리 방식을 밝히지 않음).
#   2) 전분기 값이 0 이하이면 증가율 분모에 절댓값을 쓰고 flag 'base_nonpositive' 를 남긴다(부호 뒤집힘 방지).
#   3) 동점은 같은 순위(작은 쪽)로 둔다. 순위가 없는 값(None)은 최하위.
#   4) 상장 1년(242거래일) 미만은 연간 등락률을 계산할 수 없어 제외한다.
#   5) 벤처투자사는 종목명 키워드로만 근사해 제외한다(정확한 분류 아님).
import os, sys, json, time, math, threading, argparse, datetime as dt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DEFAULT = os.path.join(ROOT, "analysis", "multifactor_kr.json")
KST = dt.timezone(dt.timedelta(hours=9))
VERSION = "v 20261019-1"

DEFAULT_N = 200
MAX_CONSEC_FAIL = 10        # 연속 실패가 이 횟수면 차단으로 보고 중단(기존 결과는 보존)
MIN_OK_RATIO = 0.6          # 대상 대비 정상 종목이 이보다 적으면 결과를 쓰지 않는다
MIN_OK_ABS = 5
CALL_TIMEOUT_SEC = 90
SLEEP_SEC = 0.5
MIN_MARCAP = 1e11           # 시가총액 1천억 원 미만 제외
MIN_PRICE = 1000            # 주가 1천 원 미만(동전주) 제외
MIN_AVG_VOL = 2000          # 20일 평균 거래량 2천 주 미만 제외
MIN_HISTORY = 242           # iloc[-241] 계산에 필요한 최소 거래일 수
VENTURE_KEYWORDS = ("벤처투자", "창업투자", "기술투자", "벤처스")

FACTORS = ["mom_price", "mom_vol", "per", "pbr", "rev", "op", "ni", "roe"]
FACTOR_LABELS = {"mom_price": "모멘텀 주가", "mom_vol": "모멘텀 거래량", "per": "밸류 PER", "pbr": "밸류 PBR",
                 "rev": "퀄리티 매출증가", "op": "퀄리티 영업이익증가", "ni": "퀄리티 순이익증가", "roe": "퀄리티 ROE"}
STYLES = {
    "base": {"label": "기본(8개 지표)", "factors": list(FACTORS)},
    "value_growth": {"label": "가치 성장(밸류+퀄리티)", "factors": ["per", "pbr", "roe", "rev", "op", "ni"]},
    "trend_growth": {"label": "추세 성장(모멘텀+퀄리티)", "factors": ["mom_price", "mom_vol", "roe", "rev", "op", "ni"]},
    "contrarian": {"label": "역발상(밸류+모멘텀)", "factors": ["mom_price", "mom_vol", "per", "pbr"]},
}
DISCLAIMER = ("학습·점검용 지표입니다. 매수·매도 권유가 아니며, 데이터는 비공식 경로에서 가져와 공식 자료와 대조하지 않았습니다. "
              "상대 순위는 대상 종목 안에서의 위치일 뿐 미래 수익을 보장하지 않습니다.")


def kst_now():
    return dt.datetime.now(KST)


def isnum(v):
    return v is not None and isinstance(v, (int, float)) and not (isinstance(v, float) and (math.isnan(v) or math.isinf(v)))


def tofloat(v):
    """숫자로 바꾸되 NaN/inf/변환 실패는 None."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if isnum(f) else None


# ---------------------------------------------------------------- 종목 선정 (순수 함수)
def pre_filter(rows, n_target):
    """rows: [{'code','name','market','dept','close','volume','marcap'}] → (대상 리스트(시총 내림차순 상위 n_target), 제외 사유별 개수)."""
    excluded = {}
    keep = []

    def drop(reason):
        excluded[reason] = excluded.get(reason, 0) + 1

    for r in rows:
        code, name = str(r.get("code") or ""), str(r.get("name") or "")
        dept = str(r.get("dept") or "")
        if r.get("market") not in ("KOSPI", "KOSDAQ", "KOSDAQ GLOBAL"): drop("시장(코넥스 등)"); continue
        if not code.endswith("0"): drop("우선주"); continue
        if "스팩" in name or "SPAC" in dept.upper(): drop("스팩"); continue
        if "리츠" in name or "REIT" in name.upper(): drop("리츠"); continue
        if any(k in name for k in VENTURE_KEYWORDS): drop("벤처투자사(이름 근사)"); continue
        if not isnum(r.get("marcap")) or r["marcap"] < MIN_MARCAP: drop("소형주(시총 1천억 미만)"); continue
        if not isnum(r.get("close")) or r["close"] < MIN_PRICE: drop("동전주(1천 원 미만)"); continue
        keep.append(r)
    keep.sort(key=lambda r: r["marcap"], reverse=True)
    return keep[:n_target], excluded


# ---------------------------------------------------------------- 지표 계산 (순수 함수, pandas 객체를 받는다)
def growth_pct(cur, prev):
    """(cur-prev)/|prev|*100. prev 가 0/None 이면 (None, flag). prev<=0 이면 flag 'base_nonpositive'."""
    if not (isnum(cur) and isnum(prev)) or prev == 0:
        return None, None
    flag = "base_nonpositive" if prev < 0 else None
    return (cur - prev) / abs(prev) * 100.0, flag


def compute_metrics(price_df, annual_df, quarter_df):
    """→ (metrics dict, flags list, drop_reason). drop_reason 이 있으면 종목을 제외한다."""
    flags = []
    if price_df is None or len(price_df) < MIN_HISTORY:
        return None, flags, "상장 1년 미만 또는 주가 부족"
    for c in ("Close", "Volume"):
        if c not in price_df.columns: return None, flags, "주가 열 없음"
    close, vol = price_df["Close"], price_df["Volume"]
    chg = lambda k: (float(close.iloc[-1]) / float(close.iloc[-k]) - 1) * 100
    try:
        mom_price = (chg(2) + chg(6) + chg(21) + chg(241)) / 4
    except Exception:
        return None, flags, "주가 계산 실패"
    ma5, ma20 = float(vol.rolling(5).mean().iloc[-1]), float(vol.rolling(20).mean().iloc[-1])
    if not isnum(ma20) or ma20 < MIN_AVG_VOL: return None, flags, "저유동성(20일 평균 거래량 2천 주 미만)"
    mom_vol = (ma5 / ma20 - 1) * 100

    per = pbr = None
    try:
        a = annual_df.dropna(subset=["영업이익"])
        if len(a):
            per, pbr = tofloat(a["PER(배)"].iloc[-1]), tofloat(a["PBR(배)"].iloc[-1])
    except Exception:
        per = pbr = None
        flags.append("annual_missing")
    if per is None or per <= 0: flags.append("per_unavailable")
    if pbr is None or pbr <= 0: flags.append("pbr_unavailable")

    rev = op = ni = roe = None
    try:
        q = quarter_df.dropna(subset=["영업이익"])
        if len(q) >= 2:
            last, prev = q.iloc[-1], q.iloc[-2]
            for key, col in (("rev", "매출액"), ("op", "영업이익"), ("ni", "당기순이익")):
                g, f = growth_pct(tofloat(last[col]), tofloat(prev[col]))
                if key == "rev": rev = g
                elif key == "op": op = g
                else: ni = g
                if f and f not in flags: flags.append(f)
            roe = tofloat(last["ROE(%)"])
            qdate = str(q.index[-1])[:10]
        else:
            flags.append("quarter_missing"); qdate = None
    except Exception:
        flags.append("quarter_missing"); qdate = None
    if rev is None and op is None and ni is None and roe is None:
        return None, flags, "분기 재무 없음"

    def r2(v, n=2): return None if v is None else round(float(v), n)
    m = {"mom_price": r2(mom_price), "mom_vol": r2(mom_vol), "per": r2(per), "pbr": r2(pbr),
         "rev": r2(rev), "op": r2(op), "ni": r2(ni), "roe": r2(roe)}
    m["_price_date"] = str(price_df.index[-1])[:10]
    m["_quarter_date"] = qdate
    return m, flags, None


# ---------------------------------------------------------------- 순위·점수 (순수 함수)
def rank_pct(values, higher_better, bad=None):
    """values: 숫자/None 리스트 → [순위(%)]. 순위=1+더 좋은 값의 개수(동점은 같은 순위), None·bad 는 최하위. pct=순위/N*100."""
    n = len(values)
    good = []
    for v in values:
        ok = isnum(v) and not (bad and bad(v))
        good.append(v if ok else None)
    scored = [v for v in good if v is not None]
    out = []
    for v in good:
        if v is None:
            rank = len(scored) + 1
        else:
            rank = 1 + sum(1 for w in scored if (w > v if higher_better else w < v))
        out.append(round(rank / n * 100, 1))
    return out


def composite(ranks, factors):
    xs = [ranks[f] for f in factors]
    return sum(xs) / len(xs)


def score_items(items):
    """items: [{'raw':{...}}] → 각 item 에 ranks, scores(스타일별 score/rank/pct) 추가."""
    n = len(items)
    cols = {}
    for f in FACTORS:
        vals = [it["raw"][f] for it in items]
        if f in ("per", "pbr"):
            cols[f] = rank_pct(vals, False, bad=lambda v: v <= 0)
        else:
            cols[f] = rank_pct(vals, True)
    for i, it in enumerate(items):
        it["ranks"] = {f: cols[f][i] for f in FACTORS}
    for key, st in STYLES.items():
        scores = [composite(it["ranks"], st["factors"]) for it in items]
        for i, it in enumerate(items):
            rk = 1 + sum(1 for s in scores if s < scores[i] - 1e-9)
            it.setdefault("scores", {})[key] = {"score": round(scores[i], 2), "rank": rk, "pct": round(rk / n * 100, 1)}
    return items


# ---------------------------------------------------------------- 데이터 수집 (실제 구현, 시험에서는 가짜로 교체)
class FdrFetcher:
    def __init__(self):
        import FinanceDataReader as fdr
        self.fdr = fdr
        import importlib.metadata as md
        try: self.version = md.version("finance-datareader")
        except Exception: self.version = "?"
        today = dt.datetime.now()
        self.start = (today - dt.timedelta(days=370)).strftime("%Y%m%d")
        self.end = today.strftime("%Y%m%d")

    @staticmethod
    def _call(fn, sec=CALL_TIMEOUT_SEC):
        box = {}
        def run():
            try: box["v"] = fn()
            except BaseException as ex: box["e"] = ex
        t = threading.Thread(target=run, daemon=True); t.start(); t.join(sec)
        if t.is_alive(): raise TimeoutError("timeout")
        if "e" in box: raise box["e"]
        return box.get("v")

    def listing(self):
        df = self._call(lambda: self.fdr.StockListing("KRX"))
        rows = []
        for r in df.to_dict("records"):
            rows.append({"code": str(r.get("Code")), "name": r.get("Name"), "market": r.get("Market"),
                         "dept": r.get("Dept") if isinstance(r.get("Dept"), str) else "",
                         "close": r.get("Close"), "volume": r.get("Volume"), "marcap": r.get("Marcap")})
        return rows

    def price(self, code): return self._call(lambda: self.fdr.DataReader(code, self.start, self.end))
    def annual(self, code): return self._call(lambda: self.fdr.SnapDataReader("NAVER/FINSTATE-2Y/%s" % code))
    def quarter(self, code): return self._call(lambda: self.fdr.SnapDataReader("NAVER/FINSTATE-2Q/%s" % code))


def classify(ex):
    name = type(ex).__name__
    resp = getattr(ex, "response", None)
    status = getattr(resp, "status_code", None) if resp is not None else None
    low = name.lower()
    if "timeout" in low or isinstance(ex, TimeoutError): return "timeout"
    if status is not None: return "http_%s" % status
    if "connection" in low or "ssl" in low or "proxy" in low: return "network"
    if isinstance(ex, (KeyError, IndexError, ValueError)): return "data_shape"
    return "other"


# ---------------------------------------------------------------- 실행
def run(fetcher, n_target=DEFAULT_N, out_path=OUT_DEFAULT, sleep=SLEEP_SEC, log=print):
    """→ 종료코드. 0 정상(파일 작성) · 3 차단/데이터 부족으로 결과를 쓰지 않음."""
    rows = fetcher.listing()
    targets, pre_excluded = pre_filter(rows, n_target)
    log("대상 %d개 (목록 %d개, 사전 제외 %s)" % (len(targets), len(rows), pre_excluded))
    items, post_excluded, failed = [], {}, []
    consec = 0
    for idx, t in enumerate(targets):
        code = t["code"]
        try:
            p, a, q = fetcher.price(code), fetcher.annual(code), fetcher.quarter(code)
            consec = 0
        except BaseException as ex:
            kind = classify(ex)
            failed.append({"code": code, "name": t["name"], "kind": kind})
            consec += 1
            log("실패 %s %s (%s)" % (code, t["name"], kind))
            if consec >= MAX_CONSEC_FAIL:
                log("연속 %d회 실패 — 차단으로 보고 중단(기존 결과 보존)" % consec)
                return 3
            time.sleep(sleep)
            continue
        m, flags, reason = compute_metrics(p, a, q)
        if reason:
            post_excluded[reason] = post_excluded.get(reason, 0) + 1
        else:
            pd_, qd_ = m.pop("_price_date"), m.pop("_quarter_date")
            items.append({"code": code, "name": t["name"], "market": t["market"], "marcap": t["marcap"],
                          "close": t["close"], "raw": m, "flags": flags, "price_date": pd_, "quarter_date": qd_})
        if (idx + 1) % 25 == 0: log("진행 %d/%d" % (idx + 1, len(targets)))
        time.sleep(sleep)

    need = max(MIN_OK_ABS, int(len(targets) * MIN_OK_RATIO))
    if len(items) < need:
        log("정상 종목 %d개 < 필요 %d개 — 결과를 쓰지 않음(기존 결과 보존)" % (len(items), need))
        return 3

    score_items(items)
    items.sort(key=lambda it: it["scores"]["base"]["rank"])
    out = {
        "schema": "multifactor_kr/1", "version": VERSION, "generated_at": kst_now().replace(microsecond=0).isoformat(),
        "price_date": max(it["price_date"] for it in items),
        "quarter_date": max([it["quarter_date"] for it in items if it["quarter_date"]] or [None]),
        "n": len(items), "n_target": n_target,
        "universe": {"listing_total": len(rows), "pre_excluded": pre_excluded, "post_excluded": post_excluded,
                     "failed": failed, "requested": len(targets)},
        "source": {"library": "finance-datareader", "library_version": getattr(fetcher, "version", "?"),
                   "note": "KRX 종목목록 · 주가 · 네이버 재무 스냅샷(비공식 경로). 공식 자료와 대조하지 않음."},
        "factors": FACTOR_LABELS, "styles": STYLES, "disclaimer": DISCLAIMER,
        "items": items,
    }
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    tmp = out_path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, out_path)   # 완성된 파일만 교체한다
    log("완료: %d종목 → %s" % (len(items), out_path))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=int(os.environ.get("MF_N", DEFAULT_N)))
    ap.add_argument("--out", default=OUT_DEFAULT)
    args = ap.parse_args(argv)
    try:
        fetcher = FdrFetcher()
    except BaseException as ex:
        print("FinanceDataReader import 실패:", type(ex).__name__); return 2
    return run(fetcher, args.n, args.out)


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    os._exit(code)   # 시간 초과로 남은 데몬 스레드가 종료를 막지 않게 한다
