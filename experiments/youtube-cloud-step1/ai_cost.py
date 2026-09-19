# -*- coding: utf-8 -*-
"""
ai_cost — AI 호출 비용을 기록·표시·차단하는 3층 (v31, 2026-09-09)

왜: 2026-08 에 $16.5 × 8회(약 $132) 자동충전 사고. 기록만으로는 못 막는다 → 한도에 닿으면 서버가 호출을 거부한다.

  1층 기록  record(usage, model, kind)  → ai_cost.json 에 호출 1건씩 (시각·토큰·달러·용도)
  2층 표시  summary()                   → 이달 합계 · 오늘 합계 · 한도 · 최근 5건  (/api/cost, /api/health, 화면 배지)
  3층 차단  check()                     → 이달 합계 ≥ 한도면 (False, 사유). /api/claude 가 호출 전에 묻는다

한도 바꾸기: ai_cost.json 의 "limit_usd" 를 메모장으로 고친다 (서버 재시작 불필요). 기본 30달러.
단가(PRICES)는 2026-09 기준 설정값 — Anthropic 청구서와 한 번 대조할 것. 모르는 모델은 Sonnet 단가로 계산하고 표시한다.
파일이 깨져도 요약이 멈추지 않도록 모든 함수가 예외를 삼키되 print 로 남긴다.
"""
import os, json, threading
from datetime import datetime
from zoneinfo import ZoneInfo

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COST_FILE = os.path.join(BASE_DIR, "ai_cost.json")
DEFAULT_LIMIT_USD = 30.0
WARN_RATIO = 0.8

# 100만 토큰당 달러 (입력, 출력). 웹검색은 1,000회당 10달러.
PRICES = {
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-sonnet-4-5": (3.0, 15.0),
    "claude-opus-4-1":   (15.0, 75.0),
    "claude-haiku-4-5":  (1.0, 5.0),
}
WEB_SEARCH_USD = 0.01
_lock = threading.Lock()


def _now():
    return datetime.now(ZoneInfo("Asia/Seoul"))


def _empty(month):
    return {"limit_usd": DEFAULT_LIMIT_USD, "month": month, "total_usd": 0.0,
            "calls": [], "history": {}}


def _load():
    month = _now().strftime("%Y-%m")
    d = None
    if os.path.exists(COST_FILE):
        try:
            with open(COST_FILE, encoding="utf-8") as f:
                d = json.load(f)
        except Exception as e:
            print("[ai_cost] ai_cost.json 읽기 실패 — 새로 만든다: %s" % e, flush=True)
    if not isinstance(d, dict):
        d = _empty(month)
    d.setdefault("limit_usd", DEFAULT_LIMIT_USD)
    d.setdefault("history", {})
    d.setdefault("calls", [])
    d.setdefault("total_usd", 0.0)
    if d.get("month") != month:               # 달이 바뀌면 지난달 합계만 남기고 비운다
        if d.get("month"):
            d["history"][d["month"]] = round(float(d.get("total_usd") or 0), 4)
        d["month"] = month
        d["total_usd"] = 0.0
        d["calls"] = []
    return d


def _save(d):
    tmp = COST_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, COST_FILE)


def price_of(model, in_tok, out_tok, web_searches=0):
    p_in, p_out = PRICES.get(model, PRICES["claude-sonnet-4-6"])
    return in_tok / 1e6 * p_in + out_tok / 1e6 * p_out + web_searches * WEB_SEARCH_USD


def record(usage, model, kind=""):
    """호출 1건 기록. usage 는 anthropic 응답의 msg.usage (없으면 0 으로). 반환: 이번 호출 달러."""
    try:
        in_tok = int(getattr(usage, "input_tokens", 0) or 0)
        out_tok = int(getattr(usage, "output_tokens", 0) or 0)
        # 프롬프트 캐시 토큰도 입력으로 센다 (단가 차이는 무시 — 넉넉하게 잡는 쪽)
        in_tok += int(getattr(usage, "cache_creation_input_tokens", 0) or 0)
        in_tok += int(getattr(usage, "cache_read_input_tokens", 0) or 0)
        ws = 0
        stu = getattr(usage, "server_tool_use", None)
        if stu is not None:
            ws = int(getattr(stu, "web_search_requests", 0) or 0)
        usd = price_of(model, in_tok, out_tok, ws)
        with _lock:
            d = _load()
            d["calls"].append({"ts": _now().strftime("%m-%d %H:%M"), "kind": (kind or "")[:20],
                               "model": model, "in": in_tok, "out": out_tok, "ws": ws, "usd": round(usd, 4)})
            d["calls"] = d["calls"][-500:]
            d["total_usd"] = round(float(d["total_usd"]) + usd, 4)
            _save(d)
            print("[ai_cost] %s 입력 %d · 출력 %d · 검색 %d → $%.4f (이달 $%.2f / 한도 $%.0f)"
                  % (kind or "호출", in_tok, out_tok, ws, usd, d["total_usd"], d["limit_usd"]), flush=True)
        return usd
    except Exception as e:
        print("[ai_cost] 기록 실패: %s" % e, flush=True)
        return 0.0


def check():
    """호출해도 되는지. 반환 (허용여부, 메시지). 메시지는 경고(80%↑)일 때도 채워진다."""
    try:
        with _lock:
            d = _load()
        total, limit = float(d["total_usd"]), float(d["limit_usd"])
        if limit > 0 and total >= limit:
            return False, ("AI 월 한도 도달 — 이달 $%.2f / 한도 $%.2f. 폴더의 ai_cost.json 에서 limit_usd 를 올리면 계속할 수 있습니다."
                           % (total, limit))
        if limit > 0 and total >= limit * WARN_RATIO:
            return True, "AI 월 비용 경고 — 이달 $%.2f / 한도 $%.0f (%.0f%%)" % (total, limit, total / limit * 100)
        return True, ""
    except Exception as e:
        print("[ai_cost] 확인 실패(허용으로 진행): %s" % e, flush=True)
        return True, ""


def summary():
    """화면·health 용 요약."""
    try:
        with _lock:
            d = _load()
        today = _now().strftime("%m-%d")
        today_usd = sum(c.get("usd", 0) for c in d["calls"] if str(c.get("ts", "")).startswith(today))
        return {"month": d["month"], "total_usd": round(float(d["total_usd"]), 2),
                "limit_usd": float(d["limit_usd"]), "today_usd": round(today_usd, 2),
                "calls": len(d["calls"]), "recent": d["calls"][-5:], "history": d.get("history", {}),
                "blocked": float(d["limit_usd"]) > 0 and float(d["total_usd"]) >= float(d["limit_usd"])}
    except Exception as e:
        return {"error": str(e)}
