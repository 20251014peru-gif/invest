# -*- coding: utf-8 -*-
# v 20261019-2  multifactor_kr.py — 국내 멀티팩터 종합점수 (책 「데이터와 AI로 앞서가는 주식투자」 2장 방식)
# 읽기: FinanceDataReader(KRX 종목목록 · 주가 · 네이버 재무 스냅샷 — 모두 비공식/서드파티 경로, 약관은 미확인)
# 쓰기: --out 경로(기본 private_out/multifactor_kr.json, git 제외) (schema multifactor_kr/1). 실패·차단 시 기존 파일을 덮어쓰지 않는다.
#       결과는 저장소·Pages·아티팩트에 올리지 않는다. 게시는 scripts/mf_publish.py(비공개 Firestore)가 한다.
#
# 학습·점검용 지표다. 매수·매도 권유가 아니며 수치의 정확성은 공식 자료와 대조하지 않았다.
#
# 기준: 책에 딸린 MultiFactor 0.3.3 패키지(PyPI) 소스를 2026-10-19 에 읽고, 같은 종목에 둘 다 돌려 비교했다(docs/multifactor-kr.md).
# 책 본문 설명과 패키지 코드는 서로 다르다. 숫자가 책에 실린 값과 같아야 하므로 기본은 패키지 코드 쪽을 따르고, 의도적으로 다르게 한 곳은 아래에 적는다.
#
#   모멘텀 주가  = 기간별 등락률의 평균. 기본(library)은 전일·주간·월간·3개월·연간 5개 기간, 거래일 2/5/20/60/240개 전 종가 대비,
#                 데이터가 모자란 기간은 빼고 평균(패키지 방식). 책 본문 설명은 4개 기간(3개월 없음, 2/6/21/241) → MOM_VARIANT="text" 로 선택.
#   모멘텀 거래량 = 5일 평균거래량 / 20일 평균거래량 - 1  (%)
#   밸류        = PER, PBR (연간 K-IFRS 연결, 영업이익이 비어 있는 추정치 행 제외, 최신 확정값)
#   퀄리티      = 전분기 대비 매출·영업이익·당기순이익 증가율 + ROE (분기 연결, 추정치 행 제외, 최신)
#   값이 없을 때 = 그 지표의 중앙값으로 채운다(패키지 방식).
#   순위(%)     = 대상 N개 안의 순위 / N × 100. 동점은 평균 순위(패키지의 pandas rank 기본값). 모멘텀·퀄리티는 클수록, PER·PBR은 작을수록 상위.
#   종합점수    = 선택한 지표 순위의 평균(낮을수록 상위). 스타일별 점수는 같은 8개 순위 중 해당 지표만 평균한다.
# 패키지와 의도적으로 다른 점(strict=True 로 돌리면 패키지와 똑같이 한다. 비교 시험용):
#   1) PER·PBR 이 0 이하(적자·자본잠식)이거나, 값이 비었는데 EPS·BPS 가 0 이하(적자 기업은 PER 이 빈 값으로 온다)면 '최하위'.
#      패키지는 음수를 가장 싼 값으로 보아 상위 순위를 주고, 빈 값은 중앙값으로 채워 적자 기업이 중간 순위를 받는다.
#   2) 전분기 값이 0 이하면 증가율 분모에 절댓값. 패키지는 (현재-전)/전 이라 적자→흑자가 음수(악화)로 나온다. flag base_nonpositive.
#   3) KOSDAQ GLOBAL 소속을 포함한다. 패키지는 Market in [KOSPI, KOSDAQ] 로 걸러 알테오젠·에코프로 등이 빠진다.
#   4) 이름에 '리츠' 가 들어가도 '메리츠' 는 제외하지 않는다. 패키지는 메리츠금융지주(시총 21조 원)를 리츠로 오인해 뺀다.
#   5) 재무가 전혀 없는 종목(매출·영업이익·순이익·ROE 모두 없음)은 제외한다. 패키지는 모두 중앙값으로 채워 남긴다.
import os, sys
# scripts/ 안에 calendar.py 등 표준 라이브러리와 같은 이름의 파일이 있다. `python scripts/x.py` 로 실행하면 이 폴더가
# import 경로 맨 앞에 올라가 requests·pandas 가 표준 `calendar` 대신 이 폴더의 파일을 읽고 실패한다(2026-10-19 Actions 실패 원인).
# 다른 import 보다 먼저 이 폴더를 경로에서 뺀다. (이 파일은 같은 폴더의 다른 모듈을 import 하지 않는다)
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.getcwd()) != _HERE]

import json, re, time, math, threading, argparse, datetime as dt

ROOT = os.path.dirname(_HERE)
OUT_DEFAULT = os.path.join(ROOT, "private_out", "multifactor_kr.json")   # 저장소 밖으로 나가지 않도록 .gitignore 처리. 운영은 --out 으로 러너 임시 폴더를 쓴다
KST = dt.timezone(dt.timedelta(hours=9))
VERSION = "v 20261019-2"

DEFAULT_N = 200
MAX_CONSEC_FAIL = 10        # 연속 실패가 이 횟수면 차단으로 보고 중단(기존 결과는 보존)
MIN_OK_RATIO = 0.6          # 대상 대비 정상 종목이 이보다 적으면 결과를 쓰지 않는다
MIN_OK_ABS = 5
CALL_TIMEOUT_SEC = 90
SLEEP_SEC = 0.5
MIN_MARCAP = 1e11           # 시가총액 1천억 원 미만 제외
MIN_PRICE = 1000            # 주가 1천 원 미만(동전주) 제외
MIN_VOLUME = 2000           # 종목 목록의 당일 거래량 2천 주 미만 제외(패키지와 같은 기준)
MARKETS = ("KOSPI", "KOSDAQ", "KOSDAQ GLOBAL")
PREFERRED_LAST = ("5", "7", "9", "K")   # 우선주 종목코드 끝자리(패키지와 같은 기준)
NAME_EXCLUDE = re.compile("스팩|리츠|리얼티|인프라|유전|벤처")   # 스팩·리츠·인프라펀드·벤처투자 등(패키지와 같은 키워드)

MOM_VARIANT = "library"
MOM_OFFSETS = {   # (이름, iloc[-k] 의 k)
    "library": [("1d", 2), ("1w", 5), ("1m", 20), ("3m", 60), ("1y", 240)],
    "text":    [("1d", 2), ("1w", 6), ("1m", 21), ("1y", 241)],
}
MOM_REQUIRED = ("1d", "1w", "1m")        # 이 기간이 없으면(상장 20거래일 미만 등) 종목 제외. 나머지 기간은 있는 것만 평균

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


def method_info(strict=False):
    """결과 JSON 에 넣는 계산 방식 설명(화면의 '계산 방식과 한계'가 이것을 읽는다)."""
    periods = MOM_OFFSETS[MOM_VARIANT]
    return {
        "reference": "MultiFactor 0.3.3 (PyPI) 소스를 읽고 같은 종목으로 비교(2026-10-19). 책 본문 설명과 패키지 코드가 달라 패키지 쪽을 기준으로 삼음",
        "strict_book": bool(strict),
        "momentum": {"variant": MOM_VARIANT, "periods": [{"name": n, "trading_days_back": k} for n, k in periods],
                     "note": "데이터가 모자란 기간은 빼고 평균. 책 본문은 3개월을 뺀 4개 기간(2/6/21/241)으로 설명하지만 패키지 코드는 5개 기간"},
        "ties": "평균 순위(공동 2위면 2.5)", "missing": "그 지표의 중앙값으로 채움",
        "nonpositive_per_pbr": "패키지와 같이 값 그대로(음수가 상위), 빈 값은 중앙값" if strict else "0 이하이거나 적자(EPS·BPS 0 이하)로 비어 있으면 최하위(패키지와 다름)",
        "growth_negative_base": "패키지와 같이 (현재-전)/전" if strict else "분모에 절댓값(패키지와 다름), flag 표시",
        "universe": {"markets": list(MARKETS if not strict else MARKETS[:2]), "min_marcap": MIN_MARCAP, "min_price": MIN_PRICE, "min_volume": MIN_VOLUME,
                     "preferred_last_char": list(PREFERRED_LAST), "name_exclude": NAME_EXCLUDE.pattern,
                     "note": "메리츠는 '리츠'로 보지 않음(패키지와 다름)" if not strict else "패키지와 같이 메리츠도 제외"},
        "deviations": [] if strict else [
            "PER·PBR 이 0 이하이거나 적자(EPS·BPS 0 이하)로 비어 있으면 최하위(패키지는 음수를 가장 싼 값으로 보고, 빈 값은 중앙값으로 채워 적자 기업이 중간 순위를 받음)",
            "전분기 값이 0 이하면 증가율 분모에 절댓값(패키지는 부호가 뒤집힘)",
            "KOSDAQ GLOBAL 소속 포함(패키지는 제외)",
            "이름의 '메리츠'는 리츠로 보지 않음(패키지는 메리츠금융지주를 제외)",
            "재무가 전혀 없는 종목은 제외(패키지는 중앙값으로 채워 남김)",
        ],
    }


# ---------------------------------------------------------------- 종목 선정 (순수 함수)
def name_excluded(name):
    """스팩·리츠·인프라펀드·벤처투자 등 이름 키워드. '메리츠'의 '리츠'는 무시한다."""
    return bool(NAME_EXCLUDE.search(str(name or "").replace("메리츠", "")))


def pre_filter(rows, n_target, strict=False):
    """rows: [{'code','name','market','dept','close','volume','marcap'}] → (대상 리스트(시총 내림차순 상위 n_target), 제외 사유별 개수)."""
    excluded = {}
    keep = []
    markets = MARKETS[:2] if strict else MARKETS

    def drop(reason):
        excluded[reason] = excluded.get(reason, 0) + 1

    for r in rows:
        code, name = str(r.get("code") or ""), str(r.get("name") or "")
        if r.get("market") not in markets: drop("시장(코넥스 등)"); continue
        if code[-1:] in PREFERRED_LAST: drop("우선주"); continue
        hit = NAME_EXCLUDE.search(name) if strict else NAME_EXCLUDE.search(name.replace("메리츠", ""))
        if hit: drop("스팩·리츠·인프라·벤처 등(이름)"); continue
        if not isnum(r.get("marcap")) or r["marcap"] < MIN_MARCAP: drop("소형주(시총 1천억 미만)"); continue
        if not isnum(r.get("close")) or r["close"] < MIN_PRICE: drop("동전주(1천 원 미만)"); continue
        if not isnum(r.get("volume")) or r["volume"] < MIN_VOLUME: drop("저유동성(당일 거래량 2천 주 미만)"); continue
        keep.append(r)
    keep.sort(key=lambda r: r["marcap"], reverse=True)
    return keep[:n_target], excluded


# ---------------------------------------------------------------- 지표 계산 (순수 함수, pandas 객체를 받는다)
def growth_pct(cur, prev, strict=False):
    """증가율(%). prev 가 0/None 이면 (None, None).
    strict(패키지 방식): (cur-prev)/prev*100 — prev<0 이면 부호가 뒤집힌다. 기본: 분모에 |prev| 를 써서 적자→흑자가 양수가 되게 한다(flag)."""
    if not (isnum(cur) and isnum(prev)) or prev == 0:
        return None, None
    flag = "base_nonpositive" if prev < 0 else None
    denom = prev if strict else abs(prev)
    return (cur - prev) / denom * 100.0, flag


def momentum_price(close):
    """기간별 등락률의 평균. 데이터가 모자란 기간은 빼고 평균한다. 필수 기간(1d·1w·1m)이 없으면 None."""
    vals, missing = {}, []
    for name, k in MOM_OFFSETS[MOM_VARIANT]:
        if len(close) >= k:
            vals[name] = (float(close.iloc[-1]) / float(close.iloc[-k]) - 1) * 100
        else:
            missing.append(name)
    if any(n not in vals for n in MOM_REQUIRED):
        return None, missing
    return sum(vals.values()) / len(vals), missing


def compute_metrics(price_df, annual_df, quarter_df, strict=False):
    """→ (metrics dict, flags list, drop_reason). drop_reason 이 있으면 종목을 제외한다."""
    flags = []
    if price_df is None or len(price_df) == 0:
        return None, flags, "주가 없음"
    for c in ("Close", "Volume"):
        if c not in price_df.columns: return None, flags, "주가 열 없음"
    close, vol = price_df["Close"], price_df["Volume"]
    mom_price, missing = momentum_price(close)
    if mom_price is None:
        return None, flags, "주가 부족(상장 20거래일 미만)"
    if missing: flags.append("short_history")
    ma5, ma20 = tofloat(vol.rolling(5).mean().iloc[-1]), tofloat(vol.rolling(20).mean().iloc[-1])
    mom_vol = (ma5 / ma20 - 1) * 100 if (ma5 is not None and ma20) else None

    per = pbr = eps = bps = None
    try:
        a = annual_df.dropna(subset=["영업이익"])
        if len(a):
            per, pbr = tofloat(a["PER(배)"].iloc[-1]), tofloat(a["PBR(배)"].iloc[-1])
            eps = tofloat(a["EPS(원)"].iloc[-1]) if "EPS(원)" in a.columns else None
            bps = tofloat(a["BPS(원)"].iloc[-1]) if "BPS(원)" in a.columns else None
    except Exception:
        per = pbr = None
        flags.append("annual_missing")
    if per is None or per <= 0: flags.append("per_unavailable")
    if pbr is None or pbr <= 0: flags.append("pbr_unavailable")
    # 적자 기업은 PER 이 0 이하의 숫자가 아니라 빈 값으로 온다(2026-10-19 확인: 삼성SDI·LG화학·SK이노베이션 모두 EPS<0 이고 PER 이 NaN).
    # 패키지처럼 중앙값으로 채우면 적자 기업이 '중간 순위'를 받는다 → EPS(BPS)가 0 이하이면 'loss' 표시를 남기고 최하위로 처리한다(strict 에서는 쓰지 않음).
    if per is None and eps is not None and eps <= 0: flags.append("per_loss")
    if pbr is None and bps is not None and bps <= 0: flags.append("pbr_loss")

    rev = op = ni = roe = None
    qdate = None
    try:
        q = quarter_df.dropna(subset=["영업이익"])
        if len(q) >= 2:
            last, prev = q.iloc[-1], q.iloc[-2]
            for key, col in (("rev", "매출액"), ("op", "영업이익"), ("ni", "당기순이익")):
                g, f = growth_pct(tofloat(last[col]), tofloat(prev[col]), strict)
                if key == "rev": rev = g
                elif key == "op": op = g
                else: ni = g
                if f and f not in flags: flags.append(f)
            roe = tofloat(last["ROE(%)"])
            qdate = str(q.index[-1])[:10]
        else:
            flags.append("quarter_missing")
    except Exception:
        flags.append("quarter_missing")
    if rev is None and op is None and ni is None and roe is None:
        return None, flags, "분기 재무 없음"

    # 반올림하지 않은 값을 돌려준다. 순위는 원래 값으로 매겨야 하고(반올림하면 다른 값이 동점이 된다), 표시용 반올림은 저장할 때만 한다.
    m = {"mom_price": tofloat(mom_price), "mom_vol": tofloat(mom_vol), "per": per, "pbr": pbr,
         "rev": tofloat(rev), "op": tofloat(op), "ni": tofloat(ni), "roe": roe}
    m["_price_date"] = str(price_df.index[-1])[:10]
    m["_quarter_date"] = qdate
    return m, flags, None


# ---------------------------------------------------------------- 순위·점수 (순수 함수)
def median(xs):
    s = sorted(xs)
    n = len(s)
    if not n: return None
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def avg_rank_pct(values, higher_better):
    """values: 숫자(또는 +inf=최하위) 리스트 → [순위(%)]. 순위 = 1 + 더 좋은 값의 개수 + (같은 값 개수-1)/2 (pandas rank 의 average 방식), pct = 순위/N*100."""
    n = len(values)
    out = []
    for v in values:
        better = sum(1 for w in values if (w > v if higher_better else w < v))
        equal = sum(1 for w in values if w == v)
        out.append((1 + better + (equal - 1) / 2.0) / n * 100.0)
    return out


def composite(ranks, factors):
    xs = [ranks[f] for f in factors]
    return sum(xs) / len(xs)


def score_items(items, strict=False):
    """items: [{'raw':{...}}] → 각 item 에 ranks, filled, scores(스타일별 score/rank/pct) 추가."""
    n = len(items)
    for it in items: it["_rk"] = {}; it["filled"] = []
    for f in FACTORS:
        bad_nonpositive = f in ("per", "pbr") and not strict
        valid = [it["raw"][f] for it in items if isnum(it["raw"][f]) and not (bad_nonpositive and it["raw"][f] <= 0)]
        med = median(valid)
        vals = []
        for it in items:
            v = it["raw"][f]
            if not isnum(v):
                if bad_nonpositive and (f + "_loss") in it["flags"]:
                    vals.append(float("inf"))                   # 적자·자본잠식인데 값이 빈 경우: 최하위(채우지 않음)
                    continue
                it["filled"].append(f)
                vals.append(med if med is not None else 0.0)
            elif bad_nonpositive and v <= 0:
                vals.append(float("inf"))                       # 적자·자본잠식: 최하위(동률끼리는 평균 순위)
            else:
                vals.append(v)
        higher = f not in ("per", "pbr")
        for it, r in zip(items, avg_rank_pct(vals, higher)): it["_rk"][f] = r
    for it in items:
        it["ranks"] = {f: round(it["_rk"][f], 2) for f in FACTORS}
        for f in it["filled"]: it["flags"].append("filled:" + f)
    for key, st in STYLES.items():
        scores = [composite(it["_rk"], st["factors"]) for it in items]
        for i, it in enumerate(items):
            better = sum(1 for s in scores if s < scores[i] - 1e-9)
            equal = sum(1 for s in scores if abs(s - scores[i]) <= 1e-9)
            rank = 1 + better + (equal - 1) / 2.0
            it.setdefault("scores", {})[key] = {"score": round(scores[i], 2), "rank": rank, "pct": round(rank / n * 100, 1)}
    for it in items: del it["_rk"]
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
def run(fetcher, n_target=DEFAULT_N, out_path=OUT_DEFAULT, sleep=SLEEP_SEC, log=print, strict=False):
    """→ 종료코드. 0 정상(파일 작성) · 3 차단/데이터 부족으로 결과를 쓰지 않음."""
    rows = fetcher.listing()
    targets, pre_excluded = pre_filter(rows, n_target, strict)
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
        m, flags, reason = compute_metrics(p, a, q, strict)
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

    score_items(items, strict)
    for it in items:   # 순위를 다 매긴 뒤에만 표시용으로 반올림
        it["raw"] = {k: (None if v is None else round(float(v), 2)) for k, v in it["raw"].items()}
    items.sort(key=lambda it: (it["scores"]["base"]["rank"], -it["marcap"]))
    out = {
        "schema": "multifactor_kr/1", "version": VERSION, "generated_at": kst_now().replace(microsecond=0).isoformat(),
        "price_date": max(it["price_date"] for it in items),
        "quarter_date": max([it["quarter_date"] for it in items if it["quarter_date"]] or [None]),
        "n": len(items), "n_target": n_target,
        "universe": {"listing_total": len(rows), "pre_excluded": pre_excluded, "post_excluded": post_excluded,
                     "failed": failed, "requested": len(targets)},
        "source": {"library": "finance-datareader", "library_version": getattr(fetcher, "version", "?"),
                   "note": "KRX 종목목록 · 주가 · 네이버 재무 스냅샷(비공식 경로). 공식 자료와 대조하지 않음."},
        "method": method_info(strict),
        "factors": FACTOR_LABELS, "styles": STYLES, "disclaimer": DISCLAIMER,
        "items": items,
    }
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    tmp = out_path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    os.replace(tmp, out_path)   # 완성된 파일만 교체한다
    log("완료: %d종목 → %s" % (len(items), out_path))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=int(os.environ.get("MF_N", DEFAULT_N)))
    ap.add_argument("--out", default=OUT_DEFAULT)
    ap.add_argument("--strict-book", action="store_true", help="책 패키지와 똑같이 계산(비교 시험용, 운영에는 쓰지 않음)")
    args = ap.parse_args(argv)
    try:
        fetcher = FdrFetcher()
    except BaseException as ex:
        print("FinanceDataReader import 실패:", type(ex).__name__); return 2
    return run(fetcher, args.n, args.out, strict=args.strict_book)


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    os._exit(code)   # 시간 초과로 남은 데몬 스레드가 종료를 막지 않게 한다
