# -*- coding: utf-8 -*-
"""
유튜브 요약기 서버 — 자막 추출 + AI 요약 전담
- 포트: 5055 (크롬 안전)
- 모델: claude-sonnet-4-6
- 저장은 하지 않음: 브라우저가 결과를 받아 Firestore(my-system-25497)에 저장
- 채널 프로필/기록/휴지통/관통분석 = 전부 브라우저+Firestore 담당 → v3 웹앱과 데이터 공유
버전: v38-c1-0914 (KST) — youtube.html 의 APP_VERSION 과 같은 값을 유지할 것
"""
import os, re, json, traceback, urllib.request, urllib.parse
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import Flask, request, jsonify, send_from_directory

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_VERSION = "v38-c1-0914"   # ★ youtube.html <head> 의 APP_VERSION 과 반드시 같게
MODEL = "claude-sonnet-4-6"
CAPTURE_DIR = os.path.join(BASE_DIR, "captures")
os.makedirs(CAPTURE_DIR, exist_ok=True)

# --- API 키: 환경변수가 없으면 같은 폴더의 key.txt 에서 읽는다 ---------------
#  창 없이(백그라운드) 실행할 때는 시작.bat 을 거치지 않으므로 이 폴백이 필요하다.
def _load_api_key():
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "env"
    kp = os.path.join(BASE_DIR, "key.txt")
    if os.path.exists(kp):
        try:
            k = open(kp, encoding="utf-8").read().strip()
            if k:
                os.environ["ANTHROPIC_API_KEY"] = k
                return "key.txt"
        except Exception as e:
            print(f"[경고] key.txt 를 읽지 못했습니다: {e}")
    return None

API_KEY_SOURCE = _load_api_key()

app = Flask(__name__)

# --- CORS: GitHub Pages(https) 등 다른 출처에서 오는 요청 허용 ---
@app.after_request
def _add_cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return resp

def kst_now():
    return datetime.now(ZoneInfo("Asia/Seoul"))

def extract_video_id(url):
    for p in [r"(?:v=|/videos/|embed/|youtu\.be/|/v/|/e/|watch\?v=|shorts/|live/)([0-9A-Za-z_-]{11})",
              r"^([0-9A-Za-z_-]{11})$"]:
        m = re.search(p, url.strip())
        if m: return m.group(1)
    return None

def fetch_oembed(url):
    try:
        q = urllib.parse.quote(url, safe="")
        req = urllib.request.Request(
            f"https://www.youtube.com/oembed?url={q}&format=json",
            headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.loads(r.read().decode("utf-8"))
        return d.get("title", "(제목 없음)"), d.get("author_name", "알수없는채널")
    except Exception:
        return "(제목 확인 실패)", "알수없는채널"

def fetch_publish_date(video_id):
    """영상 페이지에서 게시일(YYYY-MM-DD) 추출"""
    try:
        req = urllib.request.Request(
            f"https://www.youtube.com/watch?v={video_id}",
            headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "ko"})
        with urllib.request.urlopen(req, timeout=10) as r:
            html = r.read().decode("utf-8", "ignore")
        # uploadDate 또는 publishDate 메타 검색
        for pat in [r'"uploadDate":"(\d{4}-\d{2}-\d{2})',
                    r'"publishDate":"(\d{4}-\d{2}-\d{2})',
                    r'<meta itemprop="uploadDate" content="(\d{4}-\d{2}-\d{2})']:
            m = re.search(pat, html)
            if m:
                return m.group(1)
    except Exception:
        pass
    return ""

# --- 자막 캐시: 한 번 받은 자막은 파일로 남긴다 -----------------------------
#  같은 영상을 다시 요약할 때 유튜브를 또 찌르지 않는다.
#  유튜브가 일시적으로 막았을 때도 예전에 받아둔 자막으로 계속 쓸 수 있다.
CACHE_DIR = os.path.join(BASE_DIR, "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

def _cache_path(video_id):
    return os.path.join(CACHE_DIR, f"{video_id}.json")

def _cache_read(video_id):
    p = _cache_path(video_id)
    if not os.path.exists(p):
        return None
    try:
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        if d.get("segments"):
            return d
    except Exception as e:
        print(f"[자막캐시] 읽기 실패 {video_id}: {e}", flush=True)
    return None

def _cache_write(video_id, segments, lang):
    try:
        with open(_cache_path(video_id), "w", encoding="utf-8") as f:
            json.dump({"segments": segments, "lang": lang,
                       "savedAt": kst_now().strftime("%Y-%m-%d %H:%M")}, f, ensure_ascii=False)
    except Exception as e:
        print(f"[자막캐시] 쓰기 실패 {video_id}: {e}", flush=True)

def _norm_segments(fetched):
    """신·구 라이브러리 반환형(객체 / dict)을 모두 같은 모양으로 맞춘다"""
    out = []
    for x in fetched:
        if isinstance(x, dict):
            out.append({"start": float(x.get("start", 0)), "text": str(x.get("text", ""))})
        else:
            out.append({"start": float(getattr(x, "start", 0)), "text": str(getattr(x, "text", ""))})
    return out

def fetch_transcript_segments(video_id, use_cache=True):
    """자막을 ([{start(초), text}], 어떤자막인지) 로 반환.

    한 가지만 시도하고 실패하면 끝내지 말 것 — 채널마다 자막 상황이 다르다.
      수동 ko → 수동 en → 자동 ko → 자동 en → 그 외 아무 언어 → 옛 방식 직접호출
    실패 사유는 전부 모아서 예외 메시지에 담는다(조용히 삼키지 않는다).
    """
    if use_cache:
        c = _cache_read(video_id)
        if c:
            return c["segments"], (c.get("lang", "") + " · 캐시")

    from youtube_transcript_api import YouTubeTranscriptApi
    tried = []

    tl = None
    try:
        try:
            tl = YouTubeTranscriptApi().list(video_id)            # 1.x
        except AttributeError:
            tl = YouTubeTranscriptApi.list_transcripts(video_id)  # 0.6.x
    except Exception as e:
        tried.append(f"자막목록: {type(e).__name__}")

    def _done(segs, label):
        _cache_write(video_id, segs, label)
        # 2026-09-10: 콘솔이 cp949 면 em-dash(—) 를 못 찍어 UnicodeEncodeError -> 이 print 가
        # 바깥 try/except 에 걸려 "성공했는데 실패로 오인" 되던 버그. 로그 실패가 자막 fetch 성공을 삼키면 안 된다.
        try:
            print(f"[자막] {video_id} — {label} ({len(segs)}조각)", flush=True)
        except Exception:
            try:
                print(f"[자막] {video_id} - {label} ({len(segs)}segs)".encode("ascii", "replace").decode("ascii"), flush=True)
            except Exception:
                pass
        return segs, label

    if tl is not None:
        KO = ["ko", "ko-KR"]
        EN = ["en", "en-US", "en-GB"]
        plan = [("수동 ko", "manual", KO), ("수동 en", "manual", EN),
                ("자동 ko", "auto", KO),   ("자동 en", "auto", EN)]
        for label, kind, langs in plan:
            try:
                t = (tl.find_manually_created_transcript(langs) if kind == "manual"
                     else tl.find_generated_transcript(langs))
                segs = _norm_segments(t.fetch())
                if segs:
                    return _done(segs, label)
            except Exception as e:
                tried.append(f"{label}: {type(e).__name__}")
        # 한국어·영어가 아예 없는 영상 — 있는 자막을 그대로 쓴다
        try:
            for t in tl:
                try:
                    segs = _norm_segments(t.fetch())
                    if segs:
                        return _done(segs, f"기타({getattr(t, 'language_code', '?')})")
                except Exception as e:
                    tried.append(f"{getattr(t, 'language_code', '?')}: {type(e).__name__}")
        except Exception as e:
            tried.append(f"목록순회: {type(e).__name__}")

    # 목록 조회 자체가 막힌 경우 — 예전 방식으로 직접 요청
    for langs in (["ko"], ["en"], ["ko", "en"]):
        try:
            try:
                fetched = YouTubeTranscriptApi().fetch(video_id, languages=langs)
            except AttributeError:
                fetched = YouTubeTranscriptApi.get_transcript(video_id, languages=langs)
            segs = _norm_segments(fetched)
            if segs:
                return _done(segs, "직접 " + "/".join(langs))
        except Exception as e:
            tried.append(f"직접{langs}: {type(e).__name__}")

    blocked = any("Blocked" in t or "IpBlocked" in t for t in tried)
    msg = "자막을 찾지 못했습니다. 시도한 것 → " + " | ".join(tried[:8])
    if blocked:
        msg += "  ※ 유튜브가 이 PC의 요청을 일시 차단한 것으로 보입니다. 잠시 뒤 다시 해보세요."
    raise RuntimeError(msg)

def fetch_transcript(video_id):
    segs, _lang = fetch_transcript_segments(video_id)
    return " ".join(s["text"] for s in segs)

def build_timed_transcript(segs, bucket_sec=20, max_chars=None):
    """자막을 [MM:SS] 텍스트 형태로 압축 — 캡처 타이밍 판단용 (약 bucket_sec초 단위로 묶음)"""
    if not segs:
        return ""
    lines = []
    bucket_start = segs[0]["start"]
    bucket_text = []
    for s in segs:
        if s["start"] - bucket_start >= bucket_sec and bucket_text:
            mm, ss = divmod(int(bucket_start), 60)
            lines.append(f"[{mm}:{ss:02d}] {' '.join(bucket_text)}")
            bucket_start = s["start"]
            bucket_text = []
        bucket_text.append(s["text"])
    if bucket_text:
        mm, ss = divmod(int(bucket_start), 60)
        lines.append(f"[{mm}:{ss:02d}] {' '.join(bucket_text)}")
    text = "\n".join(lines)
    return text if max_chars is None else text[:max_chars]
def build_cue_transcript(segs, bucket_sec=20, max_chars=None):
    """자막을 [#번호 MM:SS] 텍스트로 압축 + 번호->실제시작초 매핑표 반환.
    AI 는 번호만 고르고, 실제 초는 이 매핑표에서 프로그램이 채운다(짐작 방지, 2026-09-10 cueId 개선).
    반환: (text, buckets)  buckets = [{"id":1,"start":12.3}, ...]"""
    if not segs:
        return "", []
    lines = []
    buckets = []
    bucket_start = segs[0]["start"]
    bucket_text = []
    cue_id = 1
    for s in segs:
        if s["start"] - bucket_start >= bucket_sec and bucket_text:
            mm, ss = divmod(int(bucket_start), 60)
            lines.append(f"[#{cue_id} {mm}:{ss:02d}] {' '.join(bucket_text)}")
            buckets.append({"id": cue_id, "start": round(bucket_start, 1)})
            cue_id += 1
            bucket_start = s["start"]
            bucket_text = []
        bucket_text.append(s["text"])
    if bucket_text:
        mm, ss = divmod(int(bucket_start), 60)
        lines.append(f"[#{cue_id} {mm}:{ss:02d}] {' '.join(bucket_text)}")
        buckets.append({"id": cue_id, "start": round(bucket_start, 1)})
    text = "\n".join(lines)
    if max_chars is not None and len(text) > max_chars:
        text = text[:max_chars]
        kept_ids = set(int(m) for m in re.findall(r"\[#(\d+)\s", text))
        buckets = [b for b in buckets if b["id"] in kept_ids]
    return text, buckets


def get_stream_url(video_id):
    """yt-dlp로 (다운로드 없이) 재생 가능한 직접 스트림 URL 추출. 화면 캡처용 — 480p 이하 우선.

    반환: (url, headers)  ← headers 가 반드시 필요하다.
    유튜브 스트림 URL 은 요청 헤더(User-Agent 등)가 없으면 403 Forbidden 을 준다.
    2026-09-09: ffmpeg 가 헤더 없이 열어서 'Server returned 403 Forbidden' 으로 캡처가 전부 실패했다.
    yt-dlp 가 알려주는 http_headers 를 그대로 ffmpeg 에 넘겨야 한다."""
    import yt_dlp
    ydl_opts = ydl_base_opts()
    ydl_opts.update({
        "skip_download": True,
        "format": CAP_FORMAT,
    })
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
        url = info.get("url")
        hdrs = dict(info.get("http_headers") or {})
        if not url:
            # 영상+음성이 따로인 경우 — 영상 쪽을 쓴다
            for f in (info.get("requested_formats") or info.get("formats") or []):
                if f.get("url") and (f.get("vcodec") or "none") != "none":
                    url = f["url"]
                    hdrs = dict(f.get("http_headers") or hdrs)
                    break
        if not hdrs.get("User-Agent"):
            hdrs["User-Agent"] = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")
        hdrs.setdefault("Referer", f"https://www.youtube.com/watch?v={video_id}")
        return url, hdrs

_FFDIR = None

def find_ffmpeg():
    """ffmpeg 실행 파일을 찾는다. 반환 (경로, 어디서 찾았는지). 못 찾으면 (None, 사유).

    찾는 순서: ① 이미 만들어 둔 cache/ffmpeg  ② PATH  ③ imageio_ffmpeg 가 내려받아 둔 것
    """
    import shutil
    name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    p = os.path.join(BASE_DIR, "cache", "ffmpeg", name)
    if os.path.exists(p):
        return p, "cache/ffmpeg"
    p = shutil.which("ffmpeg")
    if p:
        return p, "PATH"
    try:
        import imageio_ffmpeg
        p = imageio_ffmpeg.get_ffmpeg_exe()
        if p and os.path.exists(p):
            return p, "imageio_ffmpeg"
        return None, "imageio_ffmpeg 가 준 경로에 파일이 없음: %s" % p
    except Exception as e:
        return None, "ffmpeg 를 못 찾음 (PATH·cache·imageio_ffmpeg 모두 없음): %s" % e


def ffmpeg_dir_for_ytdlp(ffmpeg_exe):
    """yt-dlp 에게 알려줄 'ffmpeg 폴더' 를 만든다. 반환 (폴더, 사유설명).

    yt-dlp 는 알려준 폴더 안에서 정확히 'ffmpeg.exe' 라는 이름을 찾는다.
    imageio_ffmpeg 가 주는 파일은 'ffmpeg-win64-v4.2.2.exe' 라 이름이 달라서
    yt-dlp 가 "ffmpeg is not installed" 로 거부한다 (2026-09-09 실측 로그).
    그래서 cache/ffmpeg 폴더에 ffmpeg.exe 라는 이름으로 한 번만 복사해 그 폴더를 알려준다.

    🔴 2026-09-09: 여기서 BASE_DIR 을 BASE 라고 잘못 써서 NameError 가 났고,
       except 가 그것을 조용히 삼켜 imageio 폴더를 그대로 알려주고 있었다.
       그래서 v24·v25·v26 내내 캡처가 실패했다. 이제 이유를 반드시 로그로 남긴다."""
    global _FFDIR
    name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    if _FFDIR and os.path.exists(os.path.join(_FFDIR, name)):
        return _FFDIR, "이미 준비됨: %s" % _FFDIR
    if os.path.basename(ffmpeg_exe).lower() == name:
        _FFDIR = os.path.dirname(ffmpeg_exe)
        return _FFDIR, "이름이 이미 %s 라 그대로 사용: %s" % (name, _FFDIR)
    try:
        import shutil
        d = os.path.join(BASE_DIR, "cache", "ffmpeg")
        os.makedirs(d, exist_ok=True)
        dst = os.path.join(d, name)
        if (not os.path.exists(dst)) or os.path.getsize(dst) != os.path.getsize(ffmpeg_exe):
            shutil.copy2(ffmpeg_exe, dst)
        if os.name != "nt":
            os.chmod(dst, 0o755)
        _FFDIR = d
        print("[capture] ffmpeg 복사 완료: %s -> %s" % (ffmpeg_exe, dst), flush=True)
        return d, "복사해서 준비: %s" % dst
    except Exception as e:
        why = "ffmpeg 복사 실패(%s) — yt-dlp 가 거부할 수 있음" % e
        print("[capture] " + why, flush=True)
        return os.path.dirname(ffmpeg_exe), why


def ensure_ffmpeg_on_path(ffmpeg_exe):
    """🔴 진짜 원인 (2026-09-09 yt-dlp 소스 실측).

    yt-dlp 의 '구간 다운로드 가능?' 검사는 우리가 알려준 ffmpeg_location 을 보지 않는다.

        # yt_dlp/downloader/external.py
        class FFmpegFD(ExternalFD):
            @classmethod
            def available(cls, path=None):
                # TODO: Fix path for ffmpeg
                # Fixme: This may be wrong when --ffmpeg-location is used
                return FFmpegPostProcessor().available   <- 옵션 없이 새로 만든다

    옵션 없이 만들었으므로 시스템 PATH 만 본다. 그래서 PATH 에 ffmpeg 가 없으면
    무엇을 알려줘도 "ffmpeg is not installed" 로 거부한다 (v24~v27 실패의 전부).
    실측: PATH 에 없을 때 available=False / 폴더를 PATH 에 넣으면 True.
    → ffmpeg.exe 가 든 폴더를 PATH 맨 앞에 끼워 넣는다. 이름이 정확히 ffmpeg(.exe) 여야 한다."""
    try:
        d = os.path.dirname(os.path.abspath(ffmpeg_exe))
        cur = os.environ.get("PATH", "")
        if d and d not in cur.split(os.pathsep):
            os.environ["PATH"] = d + os.pathsep + cur
            print("[capture] PATH 에 ffmpeg 폴더 추가: %s" % d, flush=True)
        # 한 번 'ffmpeg 없음' 으로 판정한 것을 캐시하므로 지워서 다시 검사하게 한다
        try:
            from yt_dlp.postprocessor.ffmpeg import FFmpegPostProcessor
            FFmpegPostProcessor._version_cache = {None: None}
            FFmpegPostProcessor._features_cache = {}
        except Exception as e:
            print("[capture] yt-dlp 판정 캐시 초기화 건너뜀: %s" % e, flush=True)
        return d
    except Exception as e:
        print("[capture] PATH 주입 실패: %s" % e, flush=True)
        return None


# ══════════════════════════════════════════════════════════════════════
#  yt-dlp 환경 — JS 런타임(deno) · 경고를 삼키지 않는 로거 · ffmpeg 종료코드 해독
#
#  🔴 2026-09-09 v29 — 캡처 실패의 세 번째 겹.
#    v28 로 ffmpeg 문제는 끝났다 (로그에 'ffmpeg is not installed' 이 더는 안 뜬다).
#    그 다음 실패는 전부 "유튜브가 403 Forbidden" 이었다:
#      · 방법 A  : ffmpeg exited with code 3436169992
#                  = 0xCCCFCB08 = AVERROR_HTTP_FORBIDDEN (ffmpeg 가 스트림을 열다 403)
#      · 방법 A′ : ERROR: unable to download video data: HTTP Error 403: Forbidden
#    yt-dlp 소스(2026.08.19) 실측:
#      · 유튜브는 이제 서명/n 챌린지를 JS 로 풀어야 하고, yt-dlp 는 그 JS 를
#        외부 런타임(deno 기본 · node 22+ · bun · quickjs)으로 돌린다.
#      · 런타임이 없으면 "No supported JavaScript runtime could be found ...
#        some formats may be missing" 경고를 내고 제한된 클라이언트로 내려간다 → 403.
#      · 그런데 우리는 quiet+no_warnings 로 그 경고를 삼키고 있었다.
#    → ① 경고를 server.log 로 보내는 로거를 단다 (logger 가 있으면 no_warnings 와 무관하게 온다)
#      ② deno 를 찾아 PATH 와 js_runtimes 옵션 양쪽으로 알려준다
#      ③ 종료코드를 사람이 읽을 수 있게 푼다
#    deno 설치와 yt-dlp 갱신은 `도구_점검.bat` 이 한다 (cache/deno/deno.exe).
# ══════════════════════════════════════════════════════════════════════

# 🔴 v30 (2026-09-09 18:35 실측): 403 은 사라졌는데 세 방식 모두
#   "Requested format is not available" 로 실패. 서버 로그에 `Downloading player`·
#   `Solving JS challenges using deno` 줄이 없다 = 웹 클라이언트 포맷 없이 visionos 의 HLS 만 받았고,
#   그 안엔 `best`(영상+소리 합본) 조건에 맞는 것이 없다.
#   → 사진 한 장에는 소리가 필요 없다. 영상만 있는 포맷(bestvideo)도 받는다.
#   → 그리고 실패하면 '무슨 포맷이 있었는지' 와 'deno 판정' 을 로그에 남긴다 (추측 대신 증거).
CAP_FORMAT = ("bestvideo[height<=480][ext=mp4]/bestvideo[height<=480]/best[height<=480]/"
              "bestvideo/best")
LOWRES_FORMAT = ("18/best[height<=360][vcodec!=none][acodec!=none]/bestvideo[height<=360]/"
                 "worstvideo/bestvideo/best")   # 단일 파일이면 된다 — 합치기만 없으면 된다


def js_runtime_status(ydl):
    """yt-dlp 가 deno 를 어떻게 판정했는지 한 줄. (내부 속성이라 try 로 감싼다)"""
    try:
        rt = ydl._js_runtimes.get("deno")
        info = rt.info if rt else None
        if not info:
            return "deno 판정: 없음/실행실패 (yt-dlp 가 --version 을 못 받음)"
        return "deno 판정: %s v%s supported=%s" % (info.path, info.version, info.supported)
    except Exception as e:
        return "deno 판정 확인 불가: %s" % e


def log_formats(video_id):
    """실패했을 때만 — 유튜브가 준 포맷 목록을 로그에 남긴다. 어떤 조건이 안 맞았는지 보기 위해."""
    try:
        import yt_dlp
        opts = ydl_base_opts()
        opts["skip_download"] = True
        with yt_dlp.YoutubeDL(opts) as ydl:
            print("[capture] " + js_runtime_status(ydl), flush=True)
            info = ydl.extract_info("https://www.youtube.com/watch?v=%s" % video_id, download=False, process=False)
            fs = info.get("formats") or []
            print("[capture] 포맷 %d개 (id/ext/proto/해상도/v/a):" % len(fs), flush=True)
            for f in fs[:40]:
                print("[capture]   %s / %s / %s / %s / v=%s / a=%s%s" % (
                    f.get("format_id"), f.get("ext"), f.get("protocol"), f.get("resolution") or f.get("height"),
                    f.get("vcodec"), f.get("acodec"), "" if f.get("url") else " / URL없음"), flush=True)
    except Exception as e:
        print("[capture] 포맷 목록 확인 실패: %s" % e, flush=True)


_DENO = None
_ENV_REPORTED = False


class _YdlLog:
    """yt-dlp 의 메시지를 server.log 로 보낸다. 경고·오류를 절대 삼키지 않는다."""
    def debug(self, msg):
        # yt-dlp 는 info 도 debug 로 보낸다. [debug] 로 시작하는 것만 진짜 디버그.
        if msg.startswith("[debug] "):
            return
        if msg.startswith("[download] "):   # 진행률 줄은 시끄럽다
            return
        print("[capture][yt-dlp] " + msg, flush=True)
    def info(self, msg):
        print("[capture][yt-dlp] " + msg, flush=True)
    def warning(self, msg):
        print("[capture][yt-dlp 경고] " + msg, flush=True)
    def error(self, msg):
        print("[capture][yt-dlp 오류] " + msg, flush=True)


def find_deno():
    """deno 실행 파일을 찾는다. 반환 (경로, 어디서) / 없으면 (None, 사유).
    순서: ① cache/deno (도구_점검.bat 이 내려받는 곳) ② PATH ③ deno 공식 설치 위치(~/.deno/bin)"""
    import shutil
    name = "deno.exe" if os.name == "nt" else "deno"
    cands = [
        (os.path.join(BASE_DIR, "cache", "deno", name), "cache/deno"),
        (shutil.which("deno") or "", "PATH"),
        (os.path.join(os.path.expanduser("~"), ".deno", "bin", name), "~/.deno/bin"),
    ]
    for p, src in cands:
        if p and os.path.isfile(p):
            return p, src
    return None, "deno 없음 (cache/deno · PATH · ~/.deno/bin 모두 없음) → 도구_점검.bat 실행"


def ensure_deno():
    """deno 를 찾아 PATH 맨 앞에 넣는다. 반환 경로 또는 None. 한 번만 찾는다."""
    global _DENO
    if _DENO and os.path.isfile(_DENO):
        return _DENO
    p, src = find_deno()
    if not p:
        return None
    d = os.path.dirname(os.path.abspath(p))
    cur = os.environ.get("PATH", "")
    if d not in cur.split(os.pathsep):
        os.environ["PATH"] = d + os.pathsep + cur
        print("[capture] PATH 에 deno 폴더 추가: %s (%s)" % (d, src), flush=True)
    _DENO = p
    return p


def ydl_base_opts():
    """캡처에 쓰는 yt-dlp 공통 옵션. 조용하되(quiet) 경고·오류는 로거로 전부 남긴다."""
    opts = {"quiet": True, "logger": _YdlLog(), "noplaylist": True}
    deno = ensure_deno()
    if deno:
        # yt-dlp 2025.10+ 는 이 옵션으로 런타임 경로를 받는다. 옛 버전은 모르는 키를 무시한다.
        opts["js_runtimes"] = {"deno": {"path": deno}}
    return opts


def ytdlp_env_report(force=False):
    """yt-dlp 버전 · deno · 챌린지 해결 스크립트(yt_dlp_ejs) 유무를 한 줄로. 로그에는 처음 한 번만."""
    global _ENV_REPORTED
    rep = {}
    try:
        import yt_dlp
        rep["yt_dlp"] = getattr(yt_dlp.version, "__version__", "?")
    except Exception as e:
        rep["yt_dlp"] = "없음(%s)" % e
    p, src = find_deno()
    rep["deno"] = ("%s (%s)" % (p, src)) if p else "없음"
    try:
        import yt_dlp_ejs
        rep["ejs"] = getattr(yt_dlp_ejs, "version", "있음")
    except Exception:
        rep["ejs"] = "없음"
    if force or not _ENV_REPORTED:
        _ENV_REPORTED = True
        print("[capture] 환경: yt-dlp=%s / deno=%s / ejs=%s" % (rep["yt_dlp"], rep["deno"], rep["ejs"]), flush=True)
    return rep


_AVERR = {
    b"403": "유튜브가 403 Forbidden 으로 거부",
    b"404": "404 Not Found",
    b"4XX": "HTTP 4xx",
    b"5XX": "HTTP 5xx",
}

def ffmpeg_exit_reason(code):
    """ffmpeg 가 Windows 에서 남기는 큰 종료코드를 사람이 읽게 푼다.
    ffmpeg 는 음수 AVERROR 를 그대로 반환하고, Windows 가 부호 없는 32비트로 보여준다.
    예) 3436169992 = 0xCCCFCB08 → -(0x333034F8) → 바이트 F8 '4' '0' '3' = AVERROR_HTTP_FORBIDDEN"""
    try:
        code = int(code)
        if code < 0:
            code += 1 << 32
        if code < 256:
            return ""
        neg = (1 << 32) - code                 # AVERROR 는 -MKTAG(a,b,c,d)
        b = neg.to_bytes(4, "little")
        tag = b[1:]
        if b[0] == 0xF8 and tag in _AVERR:
            return _AVERR[tag]
        if all(32 <= x < 127 for x in b):
            return "AVERROR('%s')" % b.decode("ascii")
        return "AVERROR 0x%08X" % code
    except Exception:
        return ""


def decode_ffmpeg_exit_in(text):
    """'ffmpeg exited with code N' 이 들어 있으면 뒤에 해독을 붙인다."""
    m = re.search(r"exited with code (-?\d+)", str(text))
    if not m:
        return str(text)
    why = ffmpeg_exit_reason(m.group(1))
    return str(text) + (" [= %s]" % why if why else "")


def capture_hint(errors):
    """실패 사유 묶음을 보고 사람이 할 일을 한 줄로 낸다. 모르면 빈 문자열."""
    s = " / ".join(errors)
    rep = ytdlp_env_report()
    if "HTTP Error 403" in s or "403 Forbidden 으로 거부" in s:
        if rep.get("deno") == "없음":
            return ("유튜브가 403 으로 거부 — JS 런타임(deno)이 없어서 yt-dlp 가 서명을 못 풉니다. "
                    "폴더의 도구_점검.bat 을 두 번 클릭한 뒤 서버_재시작.bat")
        return ("유튜브가 403 으로 거부 — deno 는 있으니 yt-dlp 가 오래됐을 가능성. "
                "도구_점검.bat 으로 yt-dlp 를 갱신한 뒤 서버_재시작.bat (그래도 안 되면 server.log 의 [yt-dlp 경고] 줄)")
    if "Requested format is not available" in s:
        return ("유튜브가 준 포맷 중 맞는 것이 없음 — server.log 의 '[capture] 포맷 N개' 와 'deno 판정' 줄을 Claude 에게")
    if "ffmpeg is not installed" in s:
        return "ffmpeg 를 PATH 에서 못 찾음 — 서버_재시작.bat 후 다시 시도 (cache/ffmpeg/ffmpeg.exe 확인)"
    if "JavaScript runtime" in s:
        return "JS 런타임 없음 — 도구_점검.bat 실행"
    return ""


def prepare_ffmpeg():
    """캡처에 쓸 ffmpeg 를 준비한다. 반환 (실행파일, 설명). 못 찾으면 (None, 사유).

    ① 찾는다 ② 이름이 정확히 ffmpeg(.exe) 인 사본을 만든다 ③ 그 폴더를 PATH 에 넣는다"""
    exe, src = find_ffmpeg()
    if not exe:
        return None, src
    d, why = ffmpeg_dir_for_ytdlp(exe)
    name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    good = os.path.join(d, name)
    if not os.path.exists(good):
        good = exe
    ensure_ffmpeg_on_path(good)
    return good, "%s / %s" % (src, why)


def prune_video_cache(d, keep=3):
    """저화질 사본은 용량이 크다 — 최근 것 몇 개만 남긴다."""
    try:
        fs = [os.path.join(d, f) for f in os.listdir(d)]
        fs = [f for f in fs if os.path.isfile(f)]
        fs.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        for p in fs[keep:]:
            try:
                os.remove(p)
                print("[capture] 오래된 저화질 사본 삭제: %s" % os.path.basename(p), flush=True)
            except Exception:
                pass
    except Exception:
        pass


def cached_lowres(video_id):
    """저화질 '단일 파일' 을 cache/video 에 한 번만 받아 둔다. 반환 (경로, 사유).

    단일 파일 포맷(18번=360p mp4)만 쓰므로 yt-dlp 가 ffmpeg 로 합칠 필요가 없다
    → yt-dlp 의 ffmpeg 검사와 아예 무관해진다. 첫 장만 조금 걸리고 그 다음부터는 즉시."""
    d = os.path.join(BASE_DIR, "cache", "video")
    try:
        os.makedirs(d, exist_ok=True)
        for ext in ("mp4", "webm", "mkv", "m4v"):
            p = os.path.join(d, "%s.%s" % (video_id, ext))
            if os.path.exists(p) and os.path.getsize(p) > 20000:
                return p, ""
        prune_video_cache(d, keep=3)
        import yt_dlp, glob
        opts = ydl_base_opts()
        opts.update({
            # 반드시 소리까지 들어 있는 단일 파일 — 합치기가 필요 없어야 한다
            "format": LOWRES_FORMAT,
            "outtmpl": os.path.join(d, video_id + ".%(ext)s"),
        })
        print("[capture] 저화질 사본 내려받기 시작: %s" % video_id, flush=True)
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download(["https://www.youtube.com/watch?v=%s" % video_id])
        got = [p for p in glob.glob(os.path.join(d, video_id + ".*")) if os.path.getsize(p) > 20000]
        if got:
            print("[capture] 저화질 사본 준비됨: %s (%.1fMB)"
                  % (os.path.basename(got[0]), os.path.getsize(got[0]) / 1048576.0), flush=True)
            return got[0], ""
        return None, "저화질 사본이 비었음"
    except Exception as e:
        return None, "저화질 사본 실패: %s" % e


def grab_frame(video_id, sec, out_path, ffmpeg_exe):
    """그 시점의 화면 1장을 뽑는다. 성공하면 (True, "") / 실패하면 (False, 사유).

    방법 A — yt-dlp 가 그 1초 구간만 직접 받아온다 (기본).
      스트림 URL 을 ffmpeg 에 넘기는 방법(방법 B)은 유튜브가 403 Forbidden 을 준다.
      헤더(User-Agent/Referer)를 붙여도 막혔다(2026-09-09 v17 실측).
      yt-dlp 는 자기 세션·서명으로 받으므로 막히지 않는다.
    방법 B — 그래도 실패하면 예전 방식(스트림 URL + 헤더)으로 한 번 더 시도한다."""
    import subprocess, tempfile, glob, shutil
    why_a = ""
    # ── 방법 A ──
    ffdir, ffwhy = ffmpeg_dir_for_ytdlp(ffmpeg_exe)
    tmpdir = tempfile.mkdtemp(prefix="ytcap_")
    try:
        import yt_dlp
        from yt_dlp.utils import download_range_func
        start = max(0.0, float(sec) - 0.3)
        opts = ydl_base_opts()
        opts.update({
            "format": CAP_FORMAT,
            "outtmpl": os.path.join(tmpdir, "clip.%(ext)s"),
            "download_ranges": download_range_func(None, [(start, start + 1.5)]),
            "force_keyframes_at_cuts": True,
            "ffmpeg_location": ffdir,
        })
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
        clips = [p for p in glob.glob(os.path.join(tmpdir, "clip.*")) if os.path.getsize(p) > 1000]
        if clips:
            r = subprocess.run([ffmpeg_exe, "-y", "-i", clips[0],
                                "-frames:v", "1", "-q:v", "3", out_path],
                               capture_output=True, timeout=40)
            if r.returncode == 0 and os.path.exists(out_path):
                return True, ""
            tail = r.stderr.decode("utf-8", "ignore").strip().splitlines()
            why_a = f"프레임 추출 실패 {tail[-1] if tail else ''}"
        else:
            why_a = "구간 내려받기 결과가 비었음"
    except Exception as e:
        why_a = f"yt-dlp 구간 실패: {decode_ffmpeg_exit_in(e)}"
        print("[capture] 방법 A 실패: %s (ffmpeg 폴더=%s / %s)" % (why_a, ffdir, ffwhy), flush=True)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    # ── 방법 A' (예비 1) — 저화질 사본을 한 번 받아 두고 그 파일에서 뽑는다 ──
    # yt-dlp 가 또 ffmpeg 를 못 찾더라도, 이 방식은 '합치기 없는 단일 파일' 이라 영향이 없다.
    try:
        vid_path, why = cached_lowres(video_id)
        if vid_path:
            r = subprocess.run([ffmpeg_exe, "-y", "-ss", str(max(0.0, float(sec))),
                                "-i", vid_path, "-frames:v", "1", "-q:v", "3", out_path],
                               capture_output=True, timeout=60)
            if r.returncode == 0 and os.path.exists(out_path):
                return True, ""
            tail = r.stderr.decode("utf-8", "ignore").strip().splitlines()
            why_a += " / 사본에서 추출 실패: %s" % (tail[-1] if tail else ffmpeg_exit_reason(r.returncode) or r.returncode)
        else:
            why_a += " / " + why
    except Exception as e:
        why_a += " / 저화질 사본 방식 실패: %s" % e
    print("[capture] 방법 A′ 까지 실패: %s" % why_a, flush=True)

    # ── 방법 B (예비 2) ──
    try:
        stream_url, stream_headers = get_stream_url(video_id)
        if not stream_url:
            return False, f"{why_a} / 스트림 URL 없음"
        hdr = "".join(f"{k}: {v}\r\n" for k, v in (stream_headers or {}).items())
        mm, ss = divmod(int(sec), 60)
        hh, mm = divmod(mm, 60)
        cmd = [ffmpeg_exe, "-y"]
        if hdr:
            cmd += ["-headers", hdr]
        cmd += ["-ss", f"{hh:02d}:{mm:02d}:{ss:02d}", "-i", stream_url,
                "-frames:v", "1", "-q:v", "3", out_path]
        r = subprocess.run(cmd, capture_output=True, timeout=40)
        if r.returncode == 0 and os.path.exists(out_path):
            return True, ""
        tail = r.stderr.decode("utf-8", "ignore").strip().splitlines()
        why_b = tail[-1] if tail else (ffmpeg_exit_reason(r.returncode) or r.returncode)
        print("[capture] 방법 B 실패: %s" % why_b, flush=True)
        log_formats(video_id)
        return False, f"{why_a} / 예비방식도 실패: {why_b}"
    except Exception as e:
        print("[capture] 방법 B 예외: %s" % e, flush=True)
        log_formats(video_id)
        return False, f"{why_a} / 예비방식 예외: {e}"


def call_claude(system, user_text, max_tokens=8000, web_search=False, kind=""):
    import anthropic
    client = anthropic.Anthropic()
    kwargs = dict(model=MODEL, max_tokens=max_tokens, system=system,
                  messages=[{"role": "user", "content": user_text}])
    if web_search:
        kwargs["tools"] = [{"type": "web_search_20250305", "name": "web_search"}]
    msg = client.messages.create(**kwargs)
    # v31: 비용 기록 (ai_cost.py 1층). 실패해도 요약은 계속된다
    try:
        import ai_cost
        ai_cost.record(getattr(msg, "usage", None), MODEL, kind)
    except Exception as e:
        print("[ai_cost] 기록 건너뜀: %s" % e, flush=True)
    # 텍스트 블록만 이어붙임 (웹 검색 시 tool_use 블록은 건너뜀)
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")

# ---------------- 종목 빠른 확인 (/api/ticker) — 예측 채점 코드는 v31 에서 삭제 ----------------

_KR_MAP = {"code2name": {}, "name2code": {}, "loaded": False}

def _load_kr_map():
    """pykrx로 코스피/코스닥 전 종목 이름↔코드 로드 (최초 1회, 캐시)"""
    if _KR_MAP["loaded"]:
        return
    try:
        from pykrx import stock
        from datetime import datetime
        for market in ("KOSPI", "KOSDAQ"):
            for code in stock.get_market_ticker_list(market=market):
                name = stock.get_market_ticker_name(code)
                suffix = ".KS" if market == "KOSPI" else ".KQ"
                _KR_MAP["code2name"][code] = (name, suffix)
                _KR_MAP["name2code"][name] = code + suffix
        # 시총 순서 (대형주 우선 정렬용) — 실패해도 무방
        try:
            today = datetime.now().strftime("%Y%m%d")
            cap = stock.get_market_cap(today)
            if cap is not None and len(cap):
                col = next((c for c in cap.columns if "시가총액" in c), None)
                if col:
                    ranked = cap.sort_values(col, ascending=False).index.tolist()
                    _KR_MAP["cap_order"] = {code: i for i, code in enumerate(ranked)}
        except Exception:
            pass
        _KR_MAP["loaded"] = True
    except Exception:
        pass  # pykrx 없거나 실패 시 조용히 넘어감

def resolve_korean_name(text):
    """한글 종목명이면 'code.KS/.KQ' 반환. 애매하면 {'candidates':[...]}. 아니면 None"""
    text = (text or "").strip()
    if not text or not any('\uac00' <= c <= '\ud7a3' for c in text):
        return None  # 한글 없으면 패스 (영문 티커)
    _load_kr_map()
    norm = text.replace(" ", "").upper()
    n2c = _KR_MAP["name2code"]
    # 1) 정확 일치 (공백·대소문자 무시)
    for name, code in n2c.items():
        if name.replace(" ", "").upper() == norm:
            return code
    # 2) 시작 일치
    starts = [(name, code) for name, code in n2c.items()
              if name.replace(" ", "").upper().startswith(norm)]
    # 3) 포함
    contains = [(name, code) for name, code in n2c.items()
                if norm in name.replace(" ", "").upper()]
    cand = starts if starts else contains
    if not cand:
        return None
    if len(cand) == 1:
        return cand[0][1]
    # 여러 개 → 시총 큰 순 정렬 후보 (최대 6개)
    order = _KR_MAP.get("cap_order", {})
    cand.sort(key=lambda x: order.get(x[1].split(".")[0], 999999))
    # 시작일치가 딱 하나로 좁혀지면 그것, 아니면 후보 목록
    if len(starts) == 1:
        return starts[0][1]
    return {"candidates": [{"name": n, "code": c} for n, c in cand[:6]]}

def kr_investor_flow(code6):
    """한국 종목 최근 5일 외국인·기관 순매수 대금(억원). 실패 시 None."""
    try:
        from pykrx import stock
        from datetime import datetime, timedelta
        end = datetime.now()
        start = end - timedelta(days=20)
        s, e = start.strftime("%Y%m%d"), end.strftime("%Y%m%d")
        # 날짜별 투자자 순매수: get_market_trading_value_by_date(..., detail=True)
        # 컬럼에 기관합계/외국인 등이 순매수 대금(원)으로 들어옴
        try:
            df = stock.get_market_trading_value_by_date(s, e, code6, detail=True)
        except Exception:
            df = stock.get_market_trading_value_by_date(s, e, code6)
        if df is None or len(df) == 0:
            return None
        recent = df.tail(5)
        cols = [str(c) for c in df.columns]
        def find(*keys):
            for c in df.columns:
                cs = str(c)
                if any(k in cs for k in keys) and "합계" not in cs.replace("기관합계", ""):
                    return c
            for c in df.columns:  # 완화 재탐색
                if any(k in str(c) for k in keys):
                    return c
            return None
        foreign_col = find("외국인")
        inst_col = find("기관합계", "기관")
        def to_eok(col):
            if col is None: return None
            return [round(float(v) / 1e8, 1) for v in recent[col].tolist()]
        result = {}
        fv = to_eok(foreign_col)
        if fv is not None:
            streak = 0
            for v in reversed(fv):
                if v > 0: streak += 1
                else: break
            result["foreign_5d"] = round(sum(fv), 1)
            result["foreign_streak"] = streak
            result["foreign_daily"] = fv
            result["foreign_dates"] = [d.strftime("%m/%d") for d in recent.index]
        iv = to_eok(inst_col)
        if iv is not None:
            result["inst_5d"] = round(sum(iv), 1)
            result["inst_daily"] = iv
        return result if result else None
    except Exception:
        return None

def quick_ticker_check(ticker, ma=21, period_days=30):
    """티커의 최근 수익률 + 이평선 위치 확인. 반환 dict 또는 error."""
    import yfinance as yf
    ticker = (ticker or "").strip()
    if not ticker:
        return {"error": "티커를 입력하세요"}
    # 한국 종목 이름이면 코드로 변환 (pykrx)
    kr = resolve_korean_name(ticker)
    if isinstance(kr, dict) and "candidates" in kr:
        return {"candidates": kr["candidates"]}  # 여러 후보 → 사용자 선택
    if kr:
        ticker = kr  # 예: "삼성전자" → "005930.KS"
    # 흔한 지수 별칭 보정
    alias = {"SOX": "^SOX", "SPX": "^GSPC", "S&P500": "^GSPC", "NDX": "^NDX",
             "나스닥100": "^NDX", "VIX": "^VIX", "다우": "^DJI", "코스피": "^KS11",
             "필라델피아반도체": "^SOX", "SP500": "^GSPC"}
    tk = alias.get(ticker.upper(), alias.get(ticker, ticker))
    try:
        import yfinance as yf
        hist = yf.Ticker(tk).history(period="6mo")
        if hist is None or len(hist) == 0:
            # ^ 없이 시도했으면 붙여서 재시도
            if not tk.startswith("^"):
                hist = yf.Ticker("^" + tk).history(period="6mo")
                if hist is not None and len(hist) > 0:
                    tk = "^" + tk
        if hist is None or len(hist) == 0:
            return {"error": f"'{ticker}' 조회 실패 — 티커를 확인하세요 (예: SOX, NVDA, 000660.KS)"}
        closes = hist["Close"].dropna()
        cur = float(closes.iloc[-1])
        # 기간 수익률
        n = min(period_days, len(closes) - 1)
        past = float(closes.iloc[-1 - n]) if n > 0 else cur
        ret_pct = round((cur - past) / past * 100, 2) if past else 0.0
        # 이평선
        ma_val = None
        if len(closes) >= ma:
            ma_val = round(float(closes.iloc[-ma:].mean()), 2)
        above = (cur > ma_val) if ma_val is not None else None
        # 차트용 데이터: 최근 40일 종가 + 21일선 시계열
        chart_n = min(40, len(closes))
        recent = closes.iloc[-chart_n:]
        prices = [round(float(v), 2) for v in recent]
        # 차트용 날짜 (MM/DD)
        chart_dates = [d.strftime("%m/%d") for d in recent.index]
        # 봉차트용 OHLC (최근 30일)
        ohlc = []
        ohlc_n = min(30, len(hist))
        hh = hist.iloc[-ohlc_n:]
        for idx in range(len(hh)):
            row = hh.iloc[idx]
            ohlc.append({
                "d": hh.index[idx].strftime("%m/%d"),
                "o": round(float(row["Open"]), 2),
                "h": round(float(row["High"]), 2),
                "l": round(float(row["Low"]), 2),
                "c": round(float(row["Close"]), 2),
            })
        # 봉차트 구간의 21일선
        ohlc_ma = []
        for i in range(len(hist) - ohlc_n, len(hist)):
            if i + 1 >= ma:
                ohlc_ma.append(round(float(closes.iloc[i + 1 - ma:i + 1].mean()), 2))
            else:
                ohlc_ma.append(None)
        ma_series = []
        for i in range(len(recent)):
            # 각 지점에서의 21일 이동평균 (데이터 부족하면 None)
            gpos = len(closes) - len(recent) + i
            if gpos + 1 >= ma:
                ma_series.append(round(float(closes.iloc[gpos + 1 - ma:gpos + 1].mean()), 2))
            else:
                ma_series.append(None)
        # 이평선 돌파/이탈 지점 감지 (마지막 교차)
        cross = None
        for i in range(len(prices) - 1, 0, -1):
            if ma_series[i] is None or ma_series[i - 1] is None:
                continue
            prev_above = prices[i - 1] > ma_series[i - 1]
            cur_above = prices[i] > ma_series[i]
            if prev_above != cur_above:
                cross = {"index": i, "type": "돌파" if cur_above else "이탈",
                         "ago": len(prices) - 1 - i}
                break
        result = {
            "ticker": tk, "current": round(cur, 2),
            "period_days": n, "return_pct": ret_pct,
            "ma": ma, "ma_value": ma_val,
            "above_ma": above,
            "high_20": round(float(closes.iloc[-20:].max()), 2) if len(closes) >= 20 else None,
            "low_20": round(float(closes.iloc[-20:].min()), 2) if len(closes) >= 20 else None,
            "prices": prices, "ma_series": ma_series, "cross": cross,
            "dates": chart_dates, "ohlc": ohlc, "ohlc_ma": ohlc_ma,
        }
        # 교차 지점에 날짜 붙이기
        if cross and 0 <= cross["index"] < len(chart_dates):
            result["cross"]["date"] = chart_dates[cross["index"]]
        # 거래량 급증 여부 (삼각형 판정용): 최근 거래량 vs 20일 평균
        try:
            if "Volume" in hist.columns:
                vol = hist["Volume"].dropna()
                if len(vol) >= 20:
                    cur_vol = float(vol.iloc[-1])
                    avg_vol = float(vol.iloc[-20:].mean())
                    if avg_vol > 0:
                        vr = round(cur_vol / avg_vol, 2)
                        result["vol_ratio"] = vr  # 1.5면 평균의 1.5배
                        result["vol_surge"] = vr >= 1.5
        except Exception:
            pass
        # 한국 종목이면 외국인·기관 수급 추가
        if tk.endswith(".KS") or tk.endswith(".KQ"):
            code6 = tk.split(".")[0]
            flow = kr_investor_flow(code6)
            if flow:
                result["flow"] = flow
            if code6 in _KR_MAP["code2name"]:
                result["kr_name"] = _KR_MAP["code2name"][code6][0]
        return result
    except Exception as e:
        return {"error": f"조회 오류: {str(e)[:100]}"}

# ---------------- 라우트 ----------------

@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "youtube.html")

def _cost_brief():
    try:
        import ai_cost
        c = ai_cost.summary()
        return {k: c.get(k) for k in ("month", "total_usd", "limit_usd", "today_usd", "blocked")}
    except Exception as e:
        return {"error": str(e)}

@app.route("/connection-config.js")
@app.route("/connection.js")
def connection_asset():
    # 연결 설정과 연결 코드만 제공한다. 키·비용 장부는 공개하지 않는다.
    name = request.path.rsplit("/", 1)[-1]
    response = send_from_directory(BASE_DIR, name)
    response.headers["Cache-Control"] = "no-store"
    return response


@app.route("/data")
def data_page():
    """📚 자료함 — 책갈피·다시보기 시간표·메모 모아보기 (v31). 같은 origin 이라 Firestore 익명 로그인이 그대로 된다."""
    resp = send_from_directory(BASE_DIR, "data.html")
    resp.headers["Cache-Control"] = "no-store"
    return resp

@app.route("/api/health")
def health():
    return jsonify({"ok": True, "api_key": bool(os.environ.get("ANTHROPIC_API_KEY")),
                    "key_source": API_KEY_SOURCE or "",
                    "version": APP_VERSION,
                    "capture_env": ytdlp_env_report(),     # yt-dlp 버전 · deno · ejs (캡처 진단용)
                    "cost": _cost_brief(),                  # 이달 AI 비용 (v31)
                    "kst": kst_now().strftime("%Y-%m-%d %H:%M"), "model": MODEL})

@app.route("/api/cost")
def cost():
    """AI 비용 요약 — 이달 합계 · 오늘 · 한도 · 최근 5건 (ai_cost.py 2층)"""
    try:
        import ai_cost
        return jsonify(ai_cost.summary())
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/api/fixes")
def fixes():
    """오타사전.txt 를 읽어 {오타: 정정} 으로 준다 (v31 — 단어 하나 고치려고 5천 행 HTML 을 왕복하지 않는다).
    형식: 한 줄에 '오타 = 정정' · '#' 로 시작하면 설명 · 잘못된 줄은 건너뛰고 몇 번째 줄인지 알려준다.
    메모장이 붙이는 BOM 과 cp949 저장도 받아준다."""
    p = os.path.join(BASE_DIR, "오타사전.txt")
    if not os.path.exists(p):
        return jsonify({"fixes": {}, "count": 0, "bad": [], "file": "없음"})
    raw = open(p, "rb").read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp949", "replace")
    out, bad = {}, []
    for i, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if "=" not in s:
            bad.append(i)
            continue
        k, v = s.split("=", 1)
        k, v = k.strip(), v.strip()
        if not k or not v or k == v:
            bad.append(i)
            continue
        out[k] = v
    resp = jsonify({"fixes": out, "count": len(out), "bad": bad, "file": "오타사전.txt"})
    resp.headers["Cache-Control"] = "no-store"
    return resp

@app.route("/api/meta")
def meta():
    """영상 제목·채널명 + 자막 (브라우저가 이걸 받아 AI 호출 판단)"""
    url = request.args.get("url", "").strip()
    vid = extract_video_id(url)
    if not vid:
        return jsonify({"error": "유효한 유튜브 URL이 아닙니다"}), 400
    title, channel = fetch_oembed(f"https://www.youtube.com/watch?v={vid}")
    publish_date = fetch_publish_date(vid)
    LIMIT = 80000
    try:
        segs, lang = fetch_transcript_segments(vid)
        transcript = " ".join(s["text"] for s in segs)
        timed_full, cue_buckets = build_cue_transcript(segs)   # 자르지 않은 전체 + 번호->초 매핑표 (2026-09-10 cueId)
    except Exception as e:
        return jsonify({"error": f"자막을 가져올 수 없습니다: {e}"}), 422
    if len(transcript) < 100:
        return jsonify({"error": "자막이 너무 짧습니다"}), 422
    # [MM:SS] 마커가 붙어 원문보다 길어지므로, 잘림은 timed 쪽에서 먼저 일어난다.
    # 조용히 자르지 말고 몇 자가 잘렸는지 브라우저에 알려준다.
    timed_cut = timed_full[:LIMIT]
    # 2026-09-10 cueId 개선: 잘려나간 번호는 매핑표에서도 제거 - AI가 없는 번호를 고르지 못하게
    kept_ids = set(int(m) for m in re.findall(r"\[#(\d+)\s", timed_cut))
    cue_buckets = [b for b in cue_buckets if b["id"] in kept_ids]
    return jsonify({"title": title, "channel": channel, "publishDate": publish_date,
                    "transcript": transcript[:LIMIT],
                    "transcriptTimed": timed_cut,
                    "cueBuckets": cue_buckets,
                    "transcriptLang": lang,
                    "transcript_chars": len(transcript),
                    "timedChars": len(timed_full),
                    "timedTruncated": len(timed_full) > LIMIT})

@app.route("/api/claude", methods=["POST"])
def claude():
    """브라우저가 조립한 system+user로 Claude 호출 (저장은 브라우저가)"""
    try:
        body = request.get_json(force=True)
        # v31: 3층 차단 — 이달 합계가 한도에 닿으면 호출하지 않는다 (ai_cost.json 의 limit_usd)
        try:
            import ai_cost
            ok, why = ai_cost.check()
        except Exception as e:
            ok, why = True, ""
            print("[ai_cost] 확인 건너뜀: %s" % e, flush=True)
        if not ok:
            print("[ai_cost] 차단: " + why, flush=True)
            return jsonify({"error": "⛔ " + why, "blocked": True}), 402
        if why:
            print("[ai_cost] " + why, flush=True)
        # 용도 표시: 브라우저가 kind 를 주면 그대로, 없으면 system 첫 글자들로
        kind = (body.get("kind") or (body.get("system", "") or "")[:12]).strip()
        text = call_claude(body.get("system", ""), body.get("user", ""),
                           body.get("max_tokens", 8000), body.get("web_search", False), kind=kind)
        return jsonify({"text": text, "cost_warning": why})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/api/ticker")
def ticker_check():
    """종목 빠른 확인 — 수익률 + 이평선 위치"""
    t = request.args.get("t", "").strip()
    ma = int(request.args.get("ma", 21))
    days = int(request.args.get("days", 30))
    return jsonify(quick_ticker_check(t, ma, days))

@app.route("/api/capture", methods=["POST"])
def capture():
    """지정된 시점(들)의 영상 화면을 캡처해 로컬에 저장하고 경로 반환.
    영상을 통째로 내려받지 않고, 스트림 URL에서 ffmpeg으로 해당 시점만 직접 seek해서 프레임 1장씩 뽑는다.
    타임스탬프 1개가 실패해도 나머지는 계속 시도(부분 실패 허용)."""
    try:
        body = request.get_json(force=True)
        video_id = (body.get("videoId") or "").strip()
        timestamps = body.get("timestamps") or []
        if not video_id or not timestamps:
            return jsonify({"error": "videoId/timestamps가 필요합니다"}), 400

        ffmpeg_exe, ffsrc = prepare_ffmpeg()
        if not ffmpeg_exe:
            return jsonify({"error": f"ffmpeg 준비 실패: {ffsrc}", "results": []}), 200
        print(f"[capture] ffmpeg={ffmpeg_exe} ({ffsrc})", flush=True)
        env = ytdlp_env_report()          # 처음 한 번 로그에 yt-dlp 버전·deno 유무를 남긴다
        out_dir = os.path.join(CAPTURE_DIR, video_id)
        os.makedirs(out_dir, exist_ok=True)

        results = []
        errors = []   # 개별 실패 사유 (전부 실패해도 원인을 알 수 있게)
        for item in timestamps[:25]:
            try:
                sec = max(0, float(item.get("t", 0)))
            except (TypeError, ValueError):
                continue
            label = str(item.get("label") or "")[:60]
            fname = f"t_{int(sec)}.jpg"
            out_path = os.path.join(out_dir, fname)
            if not os.path.exists(out_path):
                mm, ss = divmod(int(sec), 60)
                hh, mm = divmod(mm, 60)
                ts_str = f"{hh:02d}:{mm:02d}:{ss:02d}"
                ok, why = grab_frame(video_id, sec, out_path, ffmpeg_exe)
                if not ok:
                    errors.append(f"{ts_str}: {why}"[:600])   # 300자로 자르니 방법 A 사유만 보였다 (v28)
                    continue
            results.append({"t": sec, "label": label, "path": f"/captures/{video_id}/{fname}"})
        hint = capture_hint(errors) if errors else ""
        if hint:
            print("[capture] 할 일: " + hint, flush=True)
        return jsonify({"results": results, "errors": errors, "hint": hint, "env": env})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e), "results": []}), 200

@app.route("/captures/<path:filename>")
def serve_capture(filename):
    return send_from_directory(CAPTURE_DIR, filename)

# ══════════════════════════════════════════════════════════════════════
#  자동 재시작 (v32) — "자동시작을 설치했는데 왜 파일을 바꾸면 서버_재시작을 해야 하나?"
#    자동시작은 윈도우 로그인 때 서버를 '한 번' 띄운다. 그때 읽은 app.py 가 메모리에 남아 있으므로
#    파일을 새로 덮어써도 돌고 있는 서버는 옛 코드다 → 화면에 [버전 경고].
#    → 서버가 스스로 app.py·ai_cost.py 의 변경을 3초마다 보고, 바뀌면 문법 검사 후 자기 자신을 다시 띄운다.
#    안전장치: ① 문법 오류면 재시작하지 않고 로그만 (죽은 서버보다 옛 서버가 낫다)
#              ② 저장 직후 2초 동안 크기가 변하면 아직 쓰는 중으로 보고 기다린다
#              ③ 종료 코드 0 — server_bg.vbs 의 `||` 사슬이 두 번째 서버를 띄우지 않게
# ══════════════════════════════════════════════════════════════════════
WATCH_FILES = ["app.py", "ai_cost.py"]

def _watch_self():
    import sys, time, subprocess, py_compile, threading
    def snap():
        out = {}
        for n in WATCH_FILES:
            p = os.path.join(BASE_DIR, n)
            try:
                st = os.stat(p); out[n] = (st.st_mtime, st.st_size)
            except OSError:
                out[n] = None
        return out
    base = snap()
    while True:
        time.sleep(3)
        cur = snap()
        changed = [n for n in WATCH_FILES if cur.get(n) != base.get(n)]
        if not changed:
            continue
        time.sleep(2)                                   # ② 아직 쓰는 중이면 기다린다
        if snap() != cur:
            base = cur; continue
        bad = []
        for n in changed:                               # ① 문법 검사
            try:
                py_compile.compile(os.path.join(BASE_DIR, n), doraise=True)
            except Exception as e:
                bad.append("%s: %s" % (n, e))
        if bad:
            print("[자동재시작] 파일이 바뀌었지만 문법 오류라 재시작하지 않음 — " + " / ".join(bad), flush=True)
            base = cur; continue
        print("[자동재시작] %s 변경 감지 → 서버를 다시 띄웁니다 (%s)" % (", ".join(changed), kst_now().strftime("%H:%M:%S")), flush=True)
        try:
            sys.stdout.flush(); sys.stderr.flush()
            # 같은 실행파일·같은 인자로 새 서버를 띄운다.
            # 🔴 close_fds=True 가 필수 — werkzeug 는 듣기 소켓을 상속 가능하게 열어 두므로(WERKZEUG_SERVER_FD)
            #    False 면 새 서버가 옛 소켓을 물려받아 "포트가 안 빈다" 며 영원히 기다린다 (컨테이너 실측).
            #    server.log 로 향한 표준출력·오류만 명시적으로 물려준다.
            env = dict(os.environ); env.pop("WERKZEUG_SERVER_FD", None); env.pop("WERKZEUG_RUN_MAIN", None)
            kw = dict(cwd=BASE_DIR, close_fds=True, env=env, stdin=subprocess.DEVNULL)
            try:
                if sys.stdout is not None and sys.stdout.fileno() >= 0:
                    kw["stdout"] = sys.stdout.fileno()
                if sys.stderr is not None and sys.stderr.fileno() >= 0:
                    kw["stderr"] = sys.stderr.fileno()
            except Exception:
                pass
            subprocess.Popen([sys.executable] + sys.argv, **kw)
        except Exception as e:
            print("[자동재시작] 새 서버 띄우기 실패: %s — 서버_재시작.bat 을 쓰세요" % e, flush=True)
            base = cur; continue
        os._exit(0)                                     # ③ 즉시 끝나 포트를 넘긴다 (종료코드 0). 새 서버는 포트가 빌 때까지 기다린다

if __name__ == "__main__":
    # 창 없이 실행하면 이 출력이 전부 server.log 로 들어간다 → 시각을 반드시 남긴다
    print("")
    print("=" * 56)
    print(f" 서버 시작  {kst_now().strftime('%Y-%m-%d %H:%M:%S')} KST")
    print(f" 유튜브 요약기 {APP_VERSION} (서버=자막+AI / 저장=Firestore)")
    print(" http://localhost:5055")
    print(f" 모델: {MODEL}")
    try:
        e = ytdlp_env_report(force=True)
        print(f" 캡처 환경: yt-dlp={e['yt_dlp']} / deno={e['deno']} / ejs={e['ejs']}")
    except Exception as _e:
        print(f" 캡처 환경 확인 실패: {_e}")
    if API_KEY_SOURCE:
        print(f" API 키: OK ({API_KEY_SOURCE})")
    else:
        print(" ⚠️  ANTHROPIC_API_KEY 없음 — 요약·질문·시장분석이 전부 실패합니다.")
        print("     이 폴더에 key.txt 를 만들고 키를 한 줄로 넣으세요.")
    print("=" * 56, flush=True)
    try:
        import threading
        threading.Thread(target=_watch_self, daemon=True, name="watch-self").start()
        print(" 자동 재시작: app.py·ai_cost.py 가 바뀌면 3초 안에 스스로 다시 뜹니다 (서버_재시작.bat 불필요)", flush=True)
    except Exception as _e:
        print(f" 자동 재시작 감시 실패(수동 재시작 필요): {_e}", flush=True)
    # 자동 재시작 직후엔 옛 서버가 포트를 놓는 데 잠깐 걸린다 → 최대 20초 기다린다 (실측: 안 기다리면 새 서버가 죽는다)
    try:
        import socket, time as _t
        for _i in range(70):
            _s = socket.socket(); _s.settimeout(0.3)
            _busy = _s.connect_ex(("127.0.0.1", 5055)) == 0; _s.close()
            if not _busy:
                break
            if _i == 0:
                print(" 포트 5055 가 아직 쓰이는 중 — 옛 서버가 내려가길 기다립니다…", flush=True)
            _t.sleep(0.3)
    except Exception as _e:
        print(f" 포트 확인 건너뜀: {_e}", flush=True)
    try:
        app.run(host="0.0.0.0", port=5055, threaded=True)
    except OSError as e:
        # 포트가 이미 쓰이는 중 = 서버가 이미 떠 있음. 조용히 죽지 말고 이유를 남긴다.
        print(f" [시작 실패] 포트 5055 를 쓸 수 없습니다: {e}", flush=True)
        print(" → 서버가 이미 실행 중이거나 다른 프로그램이 5055 를 쓰고 있습니다.", flush=True)
        raise
