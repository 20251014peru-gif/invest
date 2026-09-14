# -*- coding: utf-8 -*-
"""
T3-1 자막 확보 프로브 (v2 보완 · 클라우드 미실행)
목적: '지정된 클라우드 실행환경(GitHub-hosted runner)' 에서 현행 자막 경로(youtube-transcript-api)가
      시간정보가 포함된 자막을 실제로 받는지 확인한다.

원칙: 운영 app.py 를 import 하지 않는다 · 키·Firestore·AI·프록시·쿠키 없음 · 공개 결과에 자막 본문·예외 원문 없음.

판정은 세 겹으로 나눈다 (v2):
  received  = 라이브러리가 자막 목록·조각을 돌려줬다              (수신 여부)
  valid     = 조각 ≥ MIN_SEGMENTS · 실질 글자 ≥ MIN_CHARS · 시각이 유한·비음수·비감소 (자막 유효성)
  coverage  = 수신 마지막 start / 기준 자막 마지막 start (끝시각 도달 비율만 비교)
  overall_content_completeness = 항상 "미검증" (중간 누락·본문 일치 여부는 검사하지 않음)
'received' 나 'valid' 만으로 "자막 확보 성공" 이라고 하지 않는다. 표의 '확보' 열은 valid 기준이다.

사용: python tests/t3_1/probe.py tests/t3_1/videos.json  → tests/t3_1/out/result.json + result.md (영상마다 즉시 저장)
"""
import os, sys, json, time, math, hashlib, platform, traceback
from datetime import datetime, timezone
import multiprocessing
import tempfile

HTTP_TIMEOUT_SEC = 60           # HTTP 연결·읽기 타임아웃 (요청 1건)
PER_VIDEO_BUDGET_SEC = 150      # 영상 1개의 전체 처리시간 상한 (목록+본문+재시도 포함). 넘으면 '영상별 처리시간 초과'
RETRY_ON_NETWORK = 1            # 네트워크 오류일 때만 1회 재시도
SLEEP_BETWEEN_SEC = 5           # 영상 사이 대기 (요청 제한 예방)
MAX_VIDEOS = 5
MIN_SEGMENTS = 5                # 이보다 적으면 '유효' 아님
MIN_CHARS = 200                 # 공백 제외 실질 글자 수. 이보다 적으면 '유효' 아님
PROCESS_CLEANUP_SEC = 3        # terminate 및 kill 후 각각 회수 대기. 회수 실패 시 시험 중단.

PUBLIC_ERROR_FIELDS = ("error_kind", "error_class", "http_status")   # 공개 결과에 남기는 오류 정보 전부

def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def lib_version():
    """실제 설치된 배포 버전 — importlib.metadata 가 1순위, 모듈 __version__ 이 2순위."""
    try:
        from importlib.metadata import version
        return version("youtube-transcript-api")
    except Exception:
        pass
    try:
        import youtube_transcript_api as m
        return getattr(m, "__version__", "?")
    except Exception:
        return "미설치"

def classify(exc):
    """오류 분류 — 예외 클래스 계층으로만 판정. 예외 메시지(원문)는 공개 결과에 넣지 않는다."""
    names = [c.__name__ for c in type(exc).__mro__]
    if "IpBlocked" in names:                 return "IP 차단"
    if "RequestBlocked" in names:            return "요청 차단"
    if "PoTokenRequired" in names:           return "PO 토큰 요구"
    if "TranscriptsDisabled" in names:       return "자막 없음(비활성)"
    if "NoTranscriptFound" in names:         return "자막 없음(요청 언어 없음)"
    if "VideoUnavailable" in names or "VideoUnplayable" in names or "AgeRestricted" in names:
        return "영상 접근 불가"
    if "InvalidVideoId" in names:            return "영상 ID 오류"
    if "YouTubeRequestFailed" in names:      return "요청 제한/HTTP 오류"
    if "YouTubeDataUnparsable" in names:     return "도구·버전 문제(응답 파싱 실패)"
    if isinstance(exc, ImportError):         return "도구·버전 문제(import 실패)"
    if "Timeout" in names or "ConnectionError" in names or "ConnectTimeout" in names or "ReadTimeout" in names or isinstance(exc, (TimeoutError, OSError)):
        return "네트워크 오류"
    return "원인 미확정"

def http_status_of(exc):
    try:
        r = getattr(exc, "response", None)
        return int(getattr(r, "status_code", None)) if r is not None else None
    except Exception:
        return None

def is_network(kind):
    return kind == "네트워크 오류"

def make_session():
    import requests
    s = requests.Session()
    orig = s.request
    def req(method, url, **kw):
        kw.setdefault("timeout", HTTP_TIMEOUT_SEC)
        return orig(method, url, **kw)
    s.request = req
    return s

def pick_transcript(tlist, prefer):
    items = list(tlist)
    for lang in prefer:
        for gen in (False, True):
            for t in items:
                if t.language_code.split("-")[0] == lang and bool(t.is_generated) == gen:
                    return t, items
    return (items[0] if items else None), items

def finite_nonneg(x):
    try:
        f = float(x)
        return math.isfinite(f) and f >= 0
    except Exception:
        return False

def analyze(snips):
    """조각 목록 → 유효성 판정. 본문은 해시·글자 수로만 남긴다."""
    starts, durs, texts = [], [], []
    for s in snips:
        starts.append(getattr(s, "start", None)); durs.append(getattr(s, "duration", None)); texts.append(str(getattr(s, "text", "") or ""))
    n = len(snips)
    text_joined = " ".join(texts)
    eff_chars = sum(1 for ch in text_joined if not ch.isspace())
    t_ok = n > 0 and all(finite_nonneg(x) for x in starts) and all(finite_nonneg(x) for x in durs) \
           and all(float(starts[i]) <= float(starts[i + 1]) for i in range(n - 1))
    reasons = []
    if n < MIN_SEGMENTS: reasons.append("조각 %d개 < %d" % (n, MIN_SEGMENTS))
    if eff_chars < MIN_CHARS: reasons.append("실질 글자 %d < %d" % (eff_chars, MIN_CHARS))
    if not t_ok: reasons.append("시간정보 무효(비유한·음수·역순)")
    fs = [float(x) for x in starts] if t_ok else []
    return {
        "segments": n, "effective_chars": eff_chars,
        "sha256_text16": hashlib.sha256(text_joined.encode("utf-8")).hexdigest()[:16] if n else None,
        "time_valid": t_ok,
        "received_span": {"first_start": fs[0], "mid_start": fs[len(fs) // 2], "last_start": fs[-1]} if fs else None,
        "valid": not reasons, "invalid_reasons": reasons,
    }

def coverage_vs_reference(analysis, ref_last):
    """끝시각 도달 비율만 보고한다. 100%라도 전체 내용 완전성은 미검증."""
    if not analysis.get("valid") or not analysis.get("received_span"):
        return {"status": "판정 불가(유효 자막 아님)", "ratio": None}
    if ref_last is None:
        return {"status": "미검증(비교 기준 없음)", "ratio": None}
    if not finite_nonneg(ref_last) or float(ref_last) == 0:
        return {"status": "미검증(비교 기준 무효)", "ratio": None}
    last = analysis["received_span"]["last_start"]
    return {"status": "기준 자막 마지막 시각 대비 도달 비율", "ratio": last / float(ref_last),
            "received_last_start_sec": last, "reference_last_start_sec": float(ref_last),
            "reference": "집 IP cache 마지막 start %.1f초" % float(ref_last)}


def probe_one_inner(api, v):
    vid = v["id"]; prefer = v.get("prefer_langs") or ["ko", "en"]
    res = {"id": vid, "purpose": v.get("purpose"), "title_known": v.get("title"), "attempts": 0,
           "received": False, "valid": False, "lang": None, "kind": None, "available_tracks": None,
           "segments": 0, "effective_chars": 0, "sha256_text16": None, "time_valid": None,
           "received_span": None, "invalid_reasons": [], "coverage": None,
           "elapsed_sec": None, "error_kind": None, "error_class": None, "http_status": None}
    for attempt in range(1 + RETRY_ON_NETWORK):
        res["attempts"] = attempt + 1
        t0 = time.time()
        try:
            tlist = api.list(vid)
            chosen, items = pick_transcript(tlist, prefer)
            res["available_tracks"] = ["%s%s" % (t.language_code, "(auto)" if t.is_generated else "") for t in items]
            if chosen is None:
                res["received"] = True; res["error_kind"] = "자막 없음(트랙 0개)"; res["error_class"] = "EmptyTrackList"
                res["elapsed_sec"] = round(time.time() - t0, 2); return res
            fetched = chosen.fetch()
            snips = list(getattr(fetched, "snippets", fetched))
            res["received"] = True
            res["lang"] = chosen.language_code; res["kind"] = "자동(auto)" if chosen.is_generated else "수동/직접"
            a = analyze(snips); res.update(a)
            res["coverage"] = coverage_vs_reference(a, v.get("reference_last_start_sec"))
            if not a["valid"]:
                res["error_kind"] = "수신했으나 유효하지 않음"; res["error_class"] = "InvalidTranscript"
            res["elapsed_sec"] = round(time.time() - t0, 2)
            return res
        except Exception as e:
            res["elapsed_sec"] = round(time.time() - t0, 2)
            kind = classify(e)
            res["error_kind"] = kind; res["error_class"] = type(e).__name__; res["http_status"] = http_status_of(e)
            if is_network(kind) and attempt < RETRY_ON_NETWORK:
                time.sleep(5); continue
            return res
    return res

def _probe_worker(v, result_path):
    # 세션과 API는 자식 안에서만 생성. 종료 시 진행 중 요청도 함께 종료된다.
    from youtube_transcript_api import YouTubeTranscriptApi
    with make_session() as session:
        result = probe_one_inner(YouTubeTranscriptApi(http_client=session), v)
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False)


def _reap_process(process):
    """종료 요청 후 join으로 회수. 회수 실패 시 다음 영상 진행 금지."""
    if process.is_alive():
        process.terminate()
        process.join(PROCESS_CLEANUP_SEC)
    if process.is_alive():
        process.kill()
        process.join(PROCESS_CLEANUP_SEC)
    if process.is_alive() or process.exitcode is None:
        raise RuntimeError("WorkerCleanupFailed")
    process.join()
    process.close()


def probe_one(v):
    """별도 프로세스로 영상별 예산 적용. 반환 전에 종료·회수, 실패 시 시험 중단."""
    with tempfile.TemporaryDirectory(prefix="t3-1-") as tmp:
        result_path = os.path.join(tmp, "result.json")
        process = multiprocessing.get_context("spawn").Process(
            target=_probe_worker, args=(v, result_path))
        process.start()
        try:
            process.join(PER_VIDEO_BUDGET_SEC)
            if process.is_alive():
                result = {"id": v["id"], "purpose": v.get("purpose"), "title_known": v.get("title"), "attempts": None,
                          "received": False, "valid": False, "error_kind": "영상별 처리시간 초과", "error_class": "PerVideoBudget",
                          "http_status": None, "elapsed_sec": PER_VIDEO_BUDGET_SEC, "segments": 0, "coverage": None}
            else:
                if process.exitcode != 0:
                    raise RuntimeError("WorkerProcessFailed")
                with open(result_path, encoding="utf-8") as f:
                    result = json.load(f)
        finally:
            _reap_process(process)
        result["overall_content_completeness"] = "미검증"
        return result


def render_md(report):
    env, results, cfg = report["env"], report["results"], report["config"]
    n_all = len(results); n_valid = sum(1 for r in results if r.get("valid")); n_recv = sum(1 for r in results if r.get("received"))
    n_block = sum(1 for r in results if str(r.get("error_kind") or "").startswith(("IP 차단", "요청 차단", "PO 토큰")))
    lines = ["# T3-1 결과 (%s · %s · youtube-transcript-api %s)" % (env["when_utc"], "GitHub-hosted runner" if env["is_github_hosted"] else "로컬", env.get("lib_version")), "",
             "**실행 상태: %s** · 시험 영상 %d개(%s) · 수신 %d · **유효 자막 확보 %d** · 차단류 %d" % (
                 report["run_status"], n_all, cfg["control_slot"], n_recv, n_valid, n_block), "",
             "**전체 내용 완전성: 미검증** — 끝시각 비율이 100% 이상이어도 중간 누락·본문 일치 여부는 확인하지 않았습니다.", "",
             "| 영상 ID | 언어·종류 | 수신 | 유효 | 조각 | 실질 글자 | 시각 유효 | 수신 범위(첫/중/끝 초) | 기준 자막 마지막 시각 대비 도달 비율 | 소요(초) | 오류 종류 | 시도 |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in results:
        sp = r.get("received_span") or {}
        cov = r.get("coverage") or {}
        lines.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            r.get("id"), ("%s %s" % (r.get("lang"), r.get("kind"))) if r.get("lang") else "-",
            "✅" if r.get("received") else "❌", "✅" if r.get("valid") else "❌",
            r.get("segments", 0), r.get("effective_chars", 0), r.get("time_valid"),
            ("%.0f/%.0f/%.0f" % (sp["first_start"], sp["mid_start"], sp["last_start"])) if sp else "-",
            ("%.3f초 / %.3f초 = %.2f%%" % (cov["received_last_start_sec"], cov["reference_last_start_sec"], cov["ratio"] * 100)) if cov.get("ratio") is not None else (cov.get("status") or "미검증"),
            r.get("elapsed_sec"), (r.get("error_kind") or "-") + ((" · " + r["error_class"]) if r.get("error_class") else ""), r.get("attempts", "-")))
    lines += ["", "- 실행환경: %s / Python %s / 러너=%s" % (env["os"], env["python"], env.get("runner")),
              "- 판정 규칙: 유효 = 조각 ≥ %d · 실질 글자 ≥ %d · 시각 유한·비음수·비감소. '수신 범위' 는 받은 조각의 첫/중/끝일 뿐 영상 전체가 아니다. 도달 비율 = 수신 마지막 start / videos.json 기준 자막 마지막 start. 영상 길이나 본문 확보 비율이 아니며, 전체 내용 완전성은 미검증." % (MIN_SEGMENTS, MIN_CHARS),
              "- ⚠ 워크플로가 초록(성공)이어도 '실행이 끝났다' 는 뜻이지 '자막을 확보했다' 는 뜻이 아니다. 확보 여부는 위 **유효** 열과 굵은 숫자로만 판정한다.",
              "- ⚠ 이 결과는 'GitHub-hosted runner · 이 라이브러리 버전 · 이 시각' 에서만 유효하다. 다른 클라우드로 일반화하지 않는다.",
              "- 공개 결과에는 자막 본문·예외 메시지 원문을 넣지 않았다(해시·글자 수·오류 종류·예외 클래스명만)."]
    return "\n".join(lines)

def save(report, out_dir):
    with open(os.path.join(out_dir, "result.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    with open(os.path.join(out_dir, "result.md"), "w", encoding="utf-8") as f:
        f.write(render_md(report))

def main():
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "videos.json")
    out_dir = os.path.join(os.path.dirname(os.path.abspath(src)), "out"); os.makedirs(out_dir, exist_ok=True)
    cfg = json.load(open(src, encoding="utf-8"))
    all_v = cfg["videos"]
    videos = [v for v in all_v if v.get("id") and v["id"] != "REPLACE_ME"][:MAX_VIDEOS]
    skipped = [v for v in all_v if not v.get("id") or v["id"] == "REPLACE_ME"]
    control_slot = ("대조군(영어/자막없음) 미지정 — %d개 슬롯 비어 있음, 대조군 시험은 하지 않음" % len(skipped)) if skipped else "대조군 지정됨"
    env = {"when_utc": now_iso(), "runner": os.environ.get("RUNNER_NAME") or platform.node(), "os": platform.platform(),
           "python": platform.python_version(), "github_run": os.environ.get("GITHUB_RUN_ID"),
           "is_github_hosted": bool(os.environ.get("GITHUB_ACTIONS")), "lib_version": lib_version()}
    report = {"env": env, "run_status": "진행 중", "overall_content_completeness": "미검증",
              "config": {"http_timeout_sec": HTTP_TIMEOUT_SEC, "per_video_budget_sec": PER_VIDEO_BUDGET_SEC, "retry_on_network": RETRY_ON_NETWORK,
                         "sleep_between_sec": SLEEP_BETWEEN_SEC, "min_segments": MIN_SEGMENTS, "min_chars": MIN_CHARS,
                         "ai_calls": 0, "firestore": "none", "proxy": "none", "cookies": "none", "videos_tested": len(videos),
                         "control_slot": control_slot},
              "results": []}
    save(report, out_dir)
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except Exception as e:
        report["run_status"] = "실행 실패(라이브러리 import 실패: %s)" % type(e).__name__
        save(report, out_dir); print(render_md(report)); return 2
    for i, v in enumerate(videos):
        try:
            r = probe_one(v)
        except Exception as e:
            report["run_status"] = "실행 실패(작업 종료·회수 또는 결과 오류: %s)" % type(e).__name__
            save(report, out_dir); print(render_md(report)); return 2
        report["results"].append(r)
        save(report, out_dir)                      # 영상마다 즉시 저장 — 전체 시간초과 시에도 완료분 보존
        if i < len(videos) - 1:
            time.sleep(SLEEP_BETWEEN_SEC)
    report["run_status"] = "실행 완료(정상 종료)"
    save(report, out_dir)
    print(render_md(report))
    n_valid = sum(1 for r in report["results"] if r.get("valid"))
    if os.environ.get("GITHUB_ACTIONS"):
        print("::warning title=T3-1::유효 자막 확보 %d / %d — 워크플로 성공 표시는 실행 완료를 뜻할 뿐 확보 성공이 아님" % (n_valid, len(videos)))
    return 0   # 0 = 프로브 실행 완료. 자막 미확보는 '시험 결과' 이지 '실행 실패' 가 아니다(실행 실패는 2)

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc(); sys.exit(2)
