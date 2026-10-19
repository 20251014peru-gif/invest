# -*- coding: utf-8 -*-
# v 20261019-1  mf_publish.py — 국내 멀티팩터 결과를 비공개 Firestore 에 게시한다(저장소·Pages·아티팩트에는 올리지 않는다).
# 읽기: scripts/multifactor_kr.py 가 만든 JSON(schema multifactor_kr/1)
# 쓰기: chatgpt_macro_private/multifactor_kr/snapshots/{price_date} 와 .../latest  (두 문서를 한 번의 배치로 → 둘 다 쓰이거나 둘 다 안 쓰인다)
#       이 경로는 클라이언트 규칙으로 비로그인 접근이 막혀 있음을 확인했다(2026-10-19 비로그인 REST 403). 읽기는 mfLatest 함수(본인 인증)만 한다.
# 인증: 실행 환경의 기본 자격(GOOGLE_APPLICATION_CREDENTIALS — Actions 에서는 google-github-actions/auth 가 설정). 키 값은 출력하지 않는다.
# 종료코드: 0 게시 완료(또는 --dry-run 검증 통과) · 2 입력 오류/자격·쓰기 실패 · 4 더 오래된 결과라 덮어쓰지 않음
import os, sys
# scripts/ 안의 calendar.py 가 표준 라이브러리를 가리지 않도록 이 폴더를 import 경로에서 뺀다(multifactor_kr.py 와 같은 이유).
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.getcwd()) != _HERE]

import json, re, argparse, datetime as dt

BASE_PATH = "chatgpt_macro_private/multifactor_kr/snapshots"
LATEST = BASE_PATH + "/latest"
PROJECT = "my-system-25497"
SCHEMA = "multifactor_kr/1"
MAX_PAYLOAD_BYTES = 900_000       # 문서 한도 1 MiB 에서 여유를 둔다
MIN_ITEMS = 5
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
KST = dt.timezone(dt.timedelta(hours=9))


class PublishError(Exception):
    def __init__(self, msg, code=2):
        super().__init__(msg)
        self.code = code


def build_document(data, now=None):
    """검증 후 (snapshot_id, 문서 dict) 를 돌려준다. 문제가 있으면 PublishError(2)."""
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        raise PublishError("schema 가 %s 이 아닙니다" % SCHEMA)
    items = data.get("items")
    if not isinstance(items, list) or len(items) < MIN_ITEMS:
        raise PublishError("items 가 없거나 %d개 미만입니다" % MIN_ITEMS)
    if data.get("n") != len(items):
        raise PublishError("n 과 items 개수가 다릅니다")
    price_date = data.get("price_date")
    if not isinstance(price_date, str) or not DATE_RE.match(price_date):
        raise PublishError("price_date 형식이 YYYY-MM-DD 가 아닙니다")
    try:
        payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    except (ValueError, TypeError):
        raise PublishError("NaN/inf 또는 JSON 으로 만들 수 없는 값이 있습니다")
    size = len(payload.encode("utf-8"))
    if size > MAX_PAYLOAD_BYTES:
        raise PublishError("결과가 너무 큽니다(%d 바이트 > %d)" % (size, MAX_PAYLOAD_BYTES))
    now = now or dt.datetime.now(KST)
    doc = {
        "schema": SCHEMA, "version": str(data.get("version", "")), "generated_at": str(data.get("generated_at", "")),
        "price_date": price_date, "quarter_date": data.get("quarter_date"), "n": len(items),
        "snapshot_id": price_date, "written_at": now.replace(microsecond=0).isoformat(), "payload": payload,
    }
    return price_date, doc, size


def publish(data, writer, now=None, force=False):
    """writer.get(path) → dict|None, writer.write_batch([(path, dict), ...]). → (snapshot_id, payload_bytes)"""
    snapshot_id, doc, size = build_document(data, now)
    current = writer.get(LATEST)
    cur_date = (current or {}).get("price_date")
    if cur_date and cur_date > snapshot_id and not force:
        raise PublishError("저장된 최신 결과(%s)가 이번 결과(%s)보다 최신이라 덮어쓰지 않습니다" % (cur_date, snapshot_id), code=4)
    writer.write_batch([(BASE_PATH + "/" + snapshot_id, doc), (LATEST, doc)])
    return snapshot_id, size


class FirestoreWriter:
    """실제 Firestore. 기본 자격(ADC)을 쓰며, 자격 값은 어디에도 출력하지 않는다."""
    def __init__(self, project=PROJECT):
        from google.cloud import firestore
        self._client = firestore.Client(project=project)

    def get(self, path):
        snap = self._client.document(path).get()
        return snap.to_dict() if snap.exists else None

    def write_batch(self, items):
        batch = self._client.batch()
        for path, data in items:
            batch.set(self._client.document(path), data)
        batch.commit()


def main(argv=None, writer_factory=FirestoreWriter):
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True, help="multifactor_kr.py 가 만든 JSON 파일")
    ap.add_argument("--project", default=PROJECT)
    ap.add_argument("--dry-run", action="store_true", help="검증만 하고 쓰지 않는다")
    ap.add_argument("--force", action="store_true", help="저장된 결과가 더 최신이어도 덮어쓴다(수동 복구용)")
    a = ap.parse_args(argv)
    try:
        with open(a.inp, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        print("입력 파일을 읽지 못했습니다"); return 2
    try:
        if a.dry_run:
            sid, _, size = build_document(data)
            print("검증 통과(쓰지 않음): snapshot=%s n=%d payload=%d바이트" % (sid, data["n"], size)); return 0
        try:
            writer = writer_factory(a.project)
        except Exception as ex:
            print("Firestore 연결 실패:", type(ex).__name__); return 2
        sid, size = publish(data, writer, force=a.force)
        print("게시 완료: snapshot=%s, latest 갱신, payload=%d바이트" % (sid, size)); return 0
    except PublishError as ex:
        print("게시 중단:", ex); return ex.code
    except Exception as ex:
        print("게시 실패:", type(ex).__name__); return 2     # 예외 원문(자격·경로 정보 가능)은 출력하지 않는다


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    sys.exit(code)
