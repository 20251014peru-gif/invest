"""Dated, definition-locked inputs for the morning report; no trading decisions.

Secrets are only read from the runner environment. Original response bodies are
stored in an Actions artifact, never in logs. Observation dates are not run dates.
"""
import argparse
import concurrent.futures
import csv
import datetime as dt
import hashlib
import io
import json
import math
import os
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request
import report_clock
import report_sources
import report_funding

ROOT = Path(__file__).resolve().parents[1]
UTC = dt.timezone.utc
KST = dt.timezone(dt.timedelta(hours=9))


def now():
    return dt.datetime.now(UTC).isoformat(timespec="seconds")


def safe_error(error):
    # Request URLs can contain ECOS/FRED keys. Never serialize exception text.
    if isinstance(error, urllib.error.HTTPError):
        return f"HTTP {error.code}"
    if isinstance(error, DataError):
        return str(error)
    return type(error).__name__


class DataError(ValueError):
    pass


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "invest-report-feeds/1.0"})
    return urllib.request.urlopen(req, timeout=25).read()


def normalized(rows, cutoff):
    values = {}
    for date, value in rows:
        day = dt.date.fromisoformat(date)
        number = float(value)
        if not math.isfinite(number):
            raise DataError("non_finite_value")
        if day > cutoff:
            raise DataError("future_observation")
        if date in values and values[date] != number:
            raise DataError("conflicting_duplicate_date")
        values[date] = number
    if len(values) < 2:
        raise DataError("comparison_pair_missing")
    return [{"date": d, "value": v} for d, v in sorted(values.items())]


def parse_fred(raw, symbol, api=False):
    if api:
        payload = json.loads(raw)
        if "error_code" in payload:
            raise DataError("fred_api_error")
        return [(r["date"], r["value"]) for r in payload.get("observations", [])
                if r.get("value") not in (None, "", ".")]
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    if symbol not in (reader.fieldnames or []):
        raise DataError("fred_series_column_mismatch")
    return [(r.get("observation_date") or r.get("DATE"), r[symbol]) for r in reader
            if r.get(symbol) not in (None, "", ".")]


def parse_ecos(raw, spec):
    payload = json.loads(raw)
    if "RESULT" in payload:
        raise DataError("ecos_api_error")
    rows = payload.get("StatisticSearch", {}).get("row", [])
    result = []
    for r in rows:
        if r.get("STAT_CODE") != spec["stat"] or r.get("ITEM_CODE1") != spec["item"]:
            raise DataError("ecos_series_code_mismatch")
        if r.get("ITEM_NAME1", "").strip() != spec["item_name"]:
            raise DataError("ecos_item_name_changed")
        if r.get("UNIT_NAME", "").strip() != spec["source_unit"]:
            raise DataError("ecos_unit_changed")
        stamp = r["TIME"]
        date = dt.date(int(stamp[:4]), int(stamp[4:6]), int(stamp[6:8])).isoformat()
        if r.get("DATA_VALUE") not in (None, "", "."):
            result.append((date, r["DATA_VALUE"]))
    return result


def parse_nyfed(raw, symbol):
    rows = json.loads(raw).get("refRates", [])
    if any(r.get("type") != symbol for r in rows):
        raise DataError("nyfed_rate_type_mismatch")
    return [(r["effectiveDate"], r["percentRate"]) for r in rows]


def fetch(spec, config, sample_ecos=False):
    provider = spec["provider"]
    today = dt.datetime.now(KST).date()
    start = (today - dt.timedelta(days=45)).isoformat()
    symbol = spec.get("series")
    if provider in ('treasury','nasdaq_eod'):
        try:
            return report_sources.retrieve(spec,today,get)
        except Exception as exc:
            # Registered same-instrument redistribution remains an explicit fallback.
            fallback=dict(provider='fred',series=spec['comparison_series'])
            rows,raw,public,transport,warnings=fetch(fallback,config,sample_ecos)
            return rows,raw,public,transport+'_fallback',['official_primary_unavailable:'+safe_error(exc)]+warnings
    if provider == "fred":
        key = os.environ.get("FRED_API_KEY", "").strip()
        if key:
            public = "https://api.stlouisfed.org/fred/series/observations?" + urllib.parse.urlencode({
                "series_id": symbol, "file_type": "json", "observation_start": start})
            raw = get(public + "&api_key=" + urllib.parse.quote(key, safe=""))
            return parse_fred(raw, symbol, True), raw, public, "fred_api", []
        public = "https://fred.stlouisfed.org/graph/fredgraph.csv?" + urllib.parse.urlencode({
            "id": symbol, "cosd": start})
        raw = get(public)
        return parse_fred(raw, symbol), raw, public, "fred_csv", []
    if provider == "nyfed":
        segment = "secured/sofr" if symbol == "SOFR" else "unsecured/effr"
        public = f"https://markets.newyorkfed.org/api/rates/{segment}/last/30.json"
        raw = get(public)
        return parse_nyfed(raw, symbol), raw, public, "nyfed_api", []
    if provider == "ecos":
        key = "sample" if sample_ecos else os.environ.get("ECOS_KEY", "").strip()
        if not key:
            raise DataError("ECOS_KEY_missing")
        # Sample access is explicitly limited to ten days/ten rows for local probes.
        begin = (today-dt.timedelta(days=10)).strftime("%Y%m%d") if sample_ecos else start.replace("-", "")
        limit = 10 if sample_ecos else 100
        tail = f"/json/kr/1/{limit}/{spec['stat']}/D/{begin}/{today:%Y%m%d}/{spec['item']}"
        url = f"https://ecos.bok.or.kr/api/StatisticSearch/{key}" + tail
        public = "https://ecos.bok.or.kr/api/StatisticSearch/{ECOS_KEY}" + tail
        warnings = []
        try:
            raw = get(url)
            transport = "ecos_direct_sample" if sample_ecos else "ecos_direct"
        except (TimeoutError, urllib.error.URLError) as exc:
            # Retain the pre-existing, owner-configured network relay. Do not use
            # it to bypass an HTTP authentication/access-denied response.
            if isinstance(exc, urllib.error.HTTPError) or not config.get("ecos_relay"):
                raise
            relay = config["ecos_relay"].rstrip("/") + "/?url=" + urllib.parse.quote(url, safe="")
            raw = get(relay)
            transport = "ecos_existing_relay"
            warnings.append("direct_network_unavailable_existing_relay_used")
        return parse_ecos(raw, spec), raw, public, transport, warnings
    raise DataError("unsupported_provider")


def collect_one(spec, config, raw_dir, sample_ecos=False):
    rec = {k: spec[k] for k in ("id", "label", "group", "definition", "unit", "price_type", "source_url")}
    rec.update({"connection_status": "blocked", "value": None, "previous_value": None,
                "observation_date": None, "previous_observation_date": None,
                "change": None, "change_unit": spec.get("change_unit"), "last_five": [],
                "published_at": None, "retrieved_at": None, "signal_eligible": False,
                "signal_note": "자동 매매·위험등급 판정은 하지 않음. 달력·사건시각 검증은 별도 단계.",
                "error": None, "warnings": []})
    if spec["provider"] == "blocked":
        rec["error"] = spec["blocker"]
        rec["next_action"] = spec["next_action"]
        return rec
    try:
        rows, raw, public, transport, warnings = fetch(spec, config, sample_ecos)
        retrieved = now()
        points = normalized(rows, dt.datetime.now(KST).date())
        last, previous = points[-1], points[-2]
        # All changes use two dated observations from the same response/series.
        if spec["change_unit"] == "bp":
            change = (last["value"] - previous["value"]) * 100
        else:
            if previous["value"] == 0:
                raise DataError("zero_comparison_denominator")
            change = (last["value"] / previous["value"] - 1) * 100
        name = spec["id"] + (".csv" if transport.startswith("fred_csv") else ".xml" if transport=='treasury_xml' else ".json")
        (raw_dir / name).write_bytes(raw)
        rec.update({"connection_status": "connected", "provider": spec["provider"],
                    "series": spec.get("series") or f"{spec.get('stat')}/{spec.get('item')}",
                    "transport": transport, "request_url_redacted": public,
                    "value": last["value"], "previous_value": previous["value"],
                    "observation_date": last["date"], "previous_observation_date": previous["date"],
                    "change": round(change, 8), "last_five": points[-5:], "recent_observations":points[-45:],
                    "observation_count": len(points), "retrieved_at": retrieved,
                    "first_proven_available_at": retrieved,
                    "source_quality": "official_or_official_redistribution",
                    "raw_sha256": hashlib.sha256(raw).hexdigest(), "raw_file": name,
                    "age_calendar_days": (dt.datetime.now(KST).date()-dt.date.fromisoformat(last["date"])).days,
                    "freshness_status": "observation_date_shown_calendar_not_yet_verified",
                    "warnings": warnings})
        if spec.get('comparison_series') and not transport.endswith('_fallback'):
            try:
                other,body,uri,kind,_=fetch(dict(provider='fred',series=spec['comparison_series']),config,sample_ecos)
                other=normalized(other,dt.datetime.now(KST).date())
                audit=report_sources.compare(points,other,spec.get('comparison_tolerance',0.00501))
                audit.update(source_url=uri,retrieved_at=now(),raw_sha256=hashlib.sha256(body).hexdigest())
                (raw_dir/(spec['id']+'_comparison'+('.csv' if kind=='fred_csv' else '.json'))).write_bytes(body)
                rec['source_comparison']=audit
            except Exception as exc:
                rec['source_comparison']={'status':'unavailable','error':safe_error(exc),'independent_origin':False}
        elif transport.endswith('_fallback'):
            rec['source_comparison']={'status':'primary_unavailable_using_registered_fred','independent_origin':False}
            rec['source_url']='https://fred.stlouisfed.org/series/'+spec['comparison_series']
        if spec['provider']=='nyfed':
            rows=json.loads(raw)['refRates']
            match=next(x for x in rows if x['effectiveDate']==last['date'])
            rec['rate_context']={k:match.get(k) for k in ('percentPercentile1','percentPercentile25','percentPercentile75','percentPercentile99','volumeInBillions','targetRateFrom','targetRateTo','revisionIndicator')}
        # A connection proves a dated response, not that the latest session has
        # been published or that this response existed at an earlier report cutoff.
    except Exception as exc:
        rec["connection_status"] = "error"
        rec["error"] = safe_error(exc)
        rec["retrieved_at"] = now()
    return rec


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample-ecos", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "facts")
    parser.add_argument("--raw-dir", type=Path, default=ROOT / "raw/market-report-run")
    args = parser.parse_args()
    config = json.loads((ROOT / "data/report_feed_registry.json").read_text(encoding="utf-8"))
    started = now()
    args.raw_dir.mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        items = list(pool.map(lambda s: collect_one(s, config, args.raw_dir, args.sample_ecos), config["items"]))
    counts = {s: sum(i["connection_status"] == s for i in items) for s in ("connected", "blocked", "error")}
    run_id = os.environ.get("GITHUB_RUN_ID")
    funding=report_funding.collect(get,args.raw_dir)
    snapshot = {"schema": "market_report_feeds/1", "version": config["version"],
                "started_at": started, "completed_at": now(), "status": "partial" if counts["blocked"] or counts["error"] else "complete",
                "collector_health": "error" if counts["error"] else "ok", "counts": {"registered": len(items), **counts},
                "run_url": f"https://github.com/20251014peru-gif/invest/actions/runs/{run_id}" if run_id else None,
                "commit": os.environ.get("GITHUB_SHA"),
                "point_in_time_note": "이번 조회에서 처음 보존한 자료. 과거 08:17 판의 당시 이용 가능 자료로 소급하지 않음.",
                "items": items,"funding_context":funding}
    write_json(args.output_dir / "market_report_feeds.json", snapshot)
    write_json(args.raw_dir / "snapshot.json", snapshot)
    policy = json.loads((ROOT / "data/report_clock_policy.json").read_text(encoding="utf-8"))
    snapshot, clock_state = report_clock.run(snapshot, policy, args.output_dir)
    write_json(args.raw_dir / "clock.json", clock_state)
    quality_counts={k:sum(bool(i.get(k)) for i in snapshot['items']) for k in ('window_calendar_conflicts','source_value_conflicts')}
    audit = {"schema": "market_report_validation/1", "started_at": started, "completed_at": snapshot["completed_at"],
             "status": snapshot["status"], "counts": snapshot["counts"], "run_url": snapshot["run_url"],
             "checks": ["exact_series_code", "exact_ecos_name_unit", "finite_values", "unique_dates", "no_future_dates", "same_source_comparison_pair", "raw_sha256"],
             "clock_policy_version": policy["version"], "morning_edition": clock_state, "quality_counts":quality_counts,"supplemental_funding_counts":funding['counts'],
             "not_verified": ["unregistered_calendar_profiles", "intraday_actual_publication_time", "independent_second_source", "trading_signal"],
             "items": [{k: i.get(k) for k in ("id", "connection_status", "observation_date", "retrieved_at", "raw_sha256", "error", "warnings", "next_action", "freshness_status", "expected_observation_date", "expected_publication_at", "data_eligible", "comparison_eligible","source_comparison","window_calendar_conflicts","source_value_conflicts","window_eligible")} for i in snapshot["items"]]}
    write_json(args.output_dir / "market_report_validation.json", audit)
    print(json.dumps({"status": snapshot["status"], "collector_health": snapshot["collector_health"], "counts": snapshot["counts"]}))
    for i in items:
        print(f"{i['id']}: {i['connection_status']} | {i['observation_date'] or '-'} | {i['error'] or '-'}")
    return 1 if counts["error"] else 0


if __name__ == "__main__":
    sys.exit(main())
