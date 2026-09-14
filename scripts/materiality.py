# v 20260915-WaveB4 materiality.py — 공식값(reported) vs 프로그램 계산값(computed) + Decimal parser.
import os, json
from decimal import Decimal, InvalidOperation
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__))); P=lambda *a:os.path.join(ROOT,*a)
RATIO_TOLERANCE_PP = Decimal("0.5")

def _load():
    try: return json.load(open(P("data","opendart_field_map.json"),encoding="utf-8"))
    except FileNotFoundError: return {"maps":{}}
def load_field_map(): return _load().get("maps",{})

def num(v):
    if v is None: return None
    s=str(v).replace(",","").strip()
    if s in ("","-","N/A","null","None"): return None
    try: return Decimal(s)
    except InvalidOperation: return None

def _resolve(spec, row, external):
    if "field" in spec: return num(row.get(spec["field"])), None
    if "external" in spec:
        v=num((external or {}).get(spec["external"]))
        return v, (None if v is not None else "EXTERNAL_MISSING")
    if "fields" in spec:
        parts=[num(row.get(f)) for f in spec["fields"]]
        if any(p is None for p in parts): return None, "COMPONENT_MISSING"
        return sum(parts), None
    if "prefix" in spec:
        parts=[num(v) for k,v in row.items() if k.startswith(spec["prefix"])]
        parts=[p for p in parts if p is not None]
        return (sum(parts) if parts else None), (None if parts else "NO_COMPONENT")
    return None, "BAD_SPEC"

def _status(reported, computed, den_zero):
    if den_zero: return "UNKNOWN", "UNKNOWN", "ZERO_DENOMINATOR"
    if reported is not None and computed is not None:
        return (("VERIFIED", computed, None) if abs(reported-computed)<=RATIO_TOLERANCE_PP
                else ("CONFLICT", computed, "OVER_TOLERANCE"))
    if computed is not None: return "CALCULATED", computed, None
    if reported is not None: return "REPORTED_ONLY", reported, None
    return "UNKNOWN", "UNKNOWN", "NO_VALUE"

def compute(event_type, detail_row, external, rcept_no, field_map=None):
    fm=field_map if field_map is not None else load_field_map()
    entry=fm.get(event_type)
    if not entry: return [], "UNKNOWN"
    if entry.get("materialityStatus")=="NOT_REQUIRED": return [], "NOT_REQUIRED"
    if entry.get("status")=="PENDING_GUIDE_READ":
        return [{"metric":"_pending","status":"UNKNOWN","reason":"공식 가이드 필드 미확인(자동계산 비활성)","rcept_no":rcept_no}], "UNKNOWN"
    row=detail_row or {}; ext=external or {}; out=[]
    for m in entry.get("metrics",[]):
        reported=num(row.get(m["reported_field"])) if m.get("reported_field") else None
        n,_=_resolve(m["numerator"],row,ext)
        d,_=_resolve(m["denominator"],row,ext)
        den_zero = (d is not None and d==0)
        computed_pct=(round(n/d*100,2) if (n is not None and d is not None and not den_zero) else None)
        st,_,reason=_status(reported, computed_pct, den_zero)
        out.append({
            "metric":m["name"],"unit":m.get("unit","%"),
            "reportedValue":(float(reported) if reported is not None else None),
            "reportedSource":(f"OpenDART:{entry['endpoint']}.{m['reported_field']}" if m.get("reported_field") else None),
            "computedValue":(float(computed_pct) if computed_pct is not None else None),
            "numerator":(float(n) if n is not None else None),"denominator":(float(d) if d is not None else None),
            "formula":m["formula"],"source":f"OpenDART:{entry['endpoint']}","rcept_no":rcept_no,
            "tolerance_pp":float(RATIO_TOLERANCE_PP),
            "diff_pp":(float(abs(reported-computed_pct)) if (reported is not None and computed_pct is not None) else None),
            "status":st,"reason":reason,"direction":"UNKNOWN"})
    if not out: return [], "UNKNOWN"
    if any(x["status"]=="CONFLICT" for x in out): overall="CONFLICT"
    elif all(x["status"]=="UNKNOWN" for x in out): overall="UNKNOWN"
    elif any(x["status"]=="UNKNOWN" for x in out): overall="PARTIAL"
    else: overall="CALCULATED"
    return out, overall

def extract_facts(event_type, detail_row, field_map=None):
    fm=field_map if field_map is not None else load_field_map()
    keys=(fm.get(event_type,{}) or {}).get("facts",[])
    return {k:(detail_row or {}).get(k) for k in keys if (detail_row or {}).get(k) not in (None,"")}

def worst_band(metrics):
    vals=[x.get("computedValue") if x.get("computedValue") is not None else x.get("reportedValue")
          for x in metrics if x.get("status") in ("VERIFIED","CALCULATED","REPORTED_ONLY")]
    vals=[v for v in vals if isinstance(v,(int,float))]
    if not vals: return "UNKNOWN"
    v=max(vals); return "M3" if v>=10 else "M2" if v>=3 else "M1" if v>=1 else "M0"
