# v 20260915-WaveA2  event_normalizer.py — raw item → 표준 Event.
import re
import event_dictionary as D
import event_schema as S
_BRACKET = re.compile(r"^\s*(\[[^\]]*\])+")

def _unify_dots(s):
    return "".join(D.DOT_CANON if ch in D.DOT_VARIANTS else ch for ch in (s or ""))

def normalize_title(raw):
    s = _unify_dots(raw)
    s = s.replace("（", "(").replace("）", ")").replace("\u3000", " ")
    s = _BRACKET.sub("", s)
    return re.sub(r"\s+", " ", s).strip()

def detect_version(raw):
    m = _BRACKET.match(_unify_dots(raw)); scope = m.group(0) if m else (raw or "")
    for kw, vt in D.VERSION_MARKERS:
        if kw in scope: return vt
    for kw, vt in D.VERSION_MARKERS:
        if kw in (raw or ""): return vt
    return D.DEFAULT_VERSION

def detect_channel(raw):
    hits = [c for c in D.CHANNEL_MARKERS if c in (raw or "")]
    return " · ".join(hits) if hits else "정규"

def detect_axes(raw, version_type=None, family=None):
    raw=raw or ""
    source="S3"
    if "미확정" in raw: claim="UNCONFIRMED"
    elif "철회" in raw: claim="WITHDRAWN"
    else: claim="CONFIRMED"
    if "잠정" in raw: data="PRELIMINARY"
    elif version_type=="CORRECTION" and family=="EARNINGS": data="RESTATED"
    elif family=="EARNINGS": data="FINAL"
    else: data="NA"
    return source, claim, data

def classify(norm_title):
    for r in D.RULES:
        if r.get("none") and any(n in norm_title for n in r["none"]): continue
        for grp in r["groups"]:
            if all(tok in norm_title for tok in grp): return r, grp
    return D.FALLBACK, []

def normalize_item(it):
    raw = it.get("report_nm", "")
    norm = normalize_title(raw); vt = detect_version(raw); ch = detect_channel(raw)
    rule, matched = classify(norm)
    src, claim, data = detect_axes(raw, version_type=vt, family=rule["family"])
    risk = "FAST_RISK_TYPE" if rule.get("fast") else None
    return S.build_event(
        stock_code=it.get("stock_code",""), company=it.get("company",""), sector=it.get("sector",""),
        raw_title=raw.strip(), norm_title=norm, tokens=matched,
        family=rule["family"], etype=rule["type"], version_type=vt, channel=ch,
        urgency=rule.get("u","U0"), source_level=src, claim_status=claim, data_status=data,
        rcept_no=it.get("rcept_no",""), rcept_dt=it.get("rcept_dt",""), url=it.get("url",""), risk_class=risk)

def normalize_all(items): return [normalize_item(it) for it in items]

def is_new_order_alert(ev):
    return ev["family"]=="CONTRACT" and ev["type"]=="SUPPLY_CONTRACT" and ev["version_type"]=="ORIGINAL"
