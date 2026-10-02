# kr_investor.py — KRX 시장별 투자자별 순매수(현물) 수집기. 직전 영업일 확정값을 facts/kr_investor.json 에 저장한다.
# 실행: python -P scripts/kr_investor.py   (-P: scripts/calendar.py 가 표준 calendar 를 가리지 않게 함. 코드에서도 한 번 더 막는다)
# 원천: KRX 정보데이터시스템(pykrx 가 KRX_ID·KRX_PW 환경변수로 로그인). 계정 값은 출력·저장하지 않는다.
# 기존 macro.py 등은 건드리지 않는다. 실패하면 어제 값을 새 값처럼 쓰지 않고 status=fail 로 남긴다.
import datetime as dt, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
KST = dt.timezone(dt.timedelta(hours=9))
OUT = P("facts", "kr_investor.json")
STATUS = P("data", "status.json")
FINAL_AFTER = 18          # KST 시각. 이 시각 이후에야 '오늘' 값을 확정으로 본다 (추정값 — 시험 로그로 조정)
MARKETS = ("KOSPI", "KOSDAQ")
KEYS = ("외국인", "기타외국인", "기관합계", "기타법인", "개인")
INST = ("금융투자", "보험", "투신", "사모", "은행", "기타금융", "연기금 등")
UNIT = "억원, 순매수 거래대금(현물)"


def kst_now():
    return dt.datetime.now(KST).replace(microsecond=0)


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def target_day(now):
    """조회 목표일: 마감 후(FINAL_AFTER 시 이후)면 오늘, 아니면 어제 — 주말이면 직전 금요일."""
    d = now.date()
    if now.hour < FINAL_AFTER:
        d -= dt.timedelta(days=1)
    while d.weekday() >= 5:
        d -= dt.timedelta(days=1)
    return d


def day_record(stock, d, mkt_names=MARKETS):
    """한 날짜의 시장별 순매수(억원). 둘 다 비면 휴장 → None. 하나만 비면 오류."""
    ds = d.strftime("%Y%m%d")
    rec = {"date": d.isoformat()}
    empty = 0
    for m in mkt_names:
        df = stock.get_market_trading_value_by_investor(ds, ds, m)
        if df is None or df.empty:
            empty += 1
            continue
        col = "순매수" if "순매수" in df.columns else df.columns[-1]
        v = lambda k: round(float(df.loc[k, col]) / 1e8, 1) if k in df.index else None
        one = {k: v(k) for k in KEYS}
        top = [one[k] for k in ("기관합계", "기타법인", "개인", "외국인", "기타외국인")]
        one["합계검사"] = round(sum(top), 1) if all(x is not None for x in top) else None   # 0 이어야 정상(시장 전체 순매수 합)
        sub = [v(k) for k in INST]
        one["기관세부차"] = round(sum(sub) - one["기관합계"], 1) if all(x is not None for x in sub) and one["기관합계"] is not None else None
        rec[m] = one
    if empty == len(mkt_names):
        return None
    if empty:
        raise RuntimeError(f"{ds} 시장 일부만 비어 있음")
    return rec


def collect(stock, target, want=2, max_back=12):
    """목표일부터 거슬러 올라가며 영업일 want 개를 모은다(휴장일은 건너뜀)."""
    days, d, tried = [], target, 0
    while len(days) < want and tried < max_back:
        if d.weekday() < 5:
            tried += 1
            r = day_record(stock, d)
            if r:
                days.append(r)
        d -= dt.timedelta(days=1)
    if not days:
        raise RuntimeError("조회된 영업일이 없음(로그인 실패이거나 접속 차단 가능)")
    return days


def next_due(base_date, now):
    """다음 영업일 18시 + 12시간. 앱이 '늦음'을 띄우는 기준."""
    nd = dt.date.fromisoformat(base_date) + dt.timedelta(days=1)
    while nd.weekday() >= 5:
        nd += dt.timedelta(days=1)
    return (dt.datetime(nd.year, nd.month, nd.day, 18, tzinfo=KST) + dt.timedelta(hours=12)).isoformat()


def write_status(status, base_date, cause, now):
    st = load(STATUS, {"schema": "status/1", "jobs": []})
    job = {"id": "kr_investor", "name": "외국인 수급", "status": status, "ran": now.isoformat(),
           "due": next_due(base_date, now) if base_date else (now + dt.timedelta(hours=30)).isoformat(),
           "cause": cause[:300], "fix": "" if status == "ok" else "Actions 로그와 KRX_ID·KRX_PW Secrets 확인. 막히면 수동 입력으로 대체",
           "link": "", "note": f"기준일 {base_date}" if base_date else ""}
    st["jobs"] = [j for j in st.get("jobs", []) if j.get("id") != "kr_investor"] + [job]
    st["updated"] = now.isoformat()
    save(STATUS, st)


def run(now=None, stock=None, out=OUT, status_path=None):
    global STATUS
    if status_path:
        STATUS = status_path
    now = now or kst_now()
    target = target_day(now)
    prev = load(out, {})
    if prev.get("status") == "ok" and prev.get("target") == target.isoformat():
        print(f"건너뜀: 목표일 {target} 값이 이미 저장됨(기준일 {prev.get('base_date')})")
        return 0
    try:
        if stock is None:
            sdir = os.path.dirname(os.path.abspath(__file__))
            sys.path[:] = [p for p in sys.path if os.path.abspath(p or ".") != sdir]   # scripts/calendar.py 충돌 방지
            from pykrx import stock as stock
        days = collect(stock, target)
    except Exception as e:
        err = f"{type(e).__name__}: {str(e)}"[:200]
        obj = dict(prev) if prev else {"schema": "kr_investor/1", "days": []}
        obj.update({"status": "fail", "error": err, "target": target.isoformat(), "collected_at": now.isoformat(), "unit": UNIT})
        save(out, obj)
        write_status("fail", obj.get("base_date"), err, now)
        print("실패:", err)
        return 1
    obj = {"schema": "kr_investor/1", "version": "v 20261002", "collected_at": now.isoformat(), "status": "ok", "error": "",
           "target": target.isoformat(), "base_date": days[0]["date"], "unit": UNIT,
           "source": "KRX 정보데이터시스템(pykrx 로그인 경유)", "days": days}
    save(out, obj)
    write_status("ok", obj["base_date"], "", now)
    print(f"수집 완료: 기준일 {obj['base_date']} (목표 {target}), {len(days)}일치")
    return 0


if __name__ == "__main__":
    sys.exit(run())
