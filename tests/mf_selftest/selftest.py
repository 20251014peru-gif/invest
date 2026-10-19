# -*- coding: utf-8 -*-
"""
서비스 계정 Firestore 쓰기 권한 시험 (1회성 · 임시 — 시험 후 이 파일과 워크플로를 제거한다)
하는 일: chatgpt_macro_private/multifactor_kr/_selftest/ping, ping2 문서를 배치로 만들고 → 읽어 보고 → 삭제한다(어느 단계에서 실패해도 삭제를 시도한다).
         각 단계에서 비로그인(인증 없는) REST 읽기가 403 인지 확인한다: 만들기 전 · 문서가 있는 동안(문서/목록) · 삭제 후.
원칙: 자격 값·경로 외의 정보는 출력하지 않는다. 예외 원문은 출력하지 않고 클래스 이름만 쓴다. 시험 문서에는 개인 정보가 없다.
종료코드: 0 모두 통과 · 1 하나라도 실패(쓰기 권한 없음, 비로그인 403 아님, 삭제 실패 등)
"""
import os, sys, json, urllib.request, urllib.error
from datetime import datetime, timezone

PROJECT = "my-system-25497"
BASE = "chatgpt_macro_private/multifactor_kr/_selftest"
REST = "https://firestore.googleapis.com/v1/projects/%s/databases/(default)/documents/%s"
R = {}


def anon(path):
    """인증 없이 GET → HTTP 상태코드(문서 내용은 읽지 않는다)."""
    try:
        with urllib.request.urlopen(REST % (PROJECT, path), timeout=30) as r:
            return r.status
    except urllib.error.HTTPError as ex:
        return ex.code
    except Exception as ex:
        return "err:" + type(ex).__name__


def step(name, fn):
    try:
        R[name] = fn()
    except Exception as ex:
        R[name] = "FAIL:" + type(ex).__name__
    print("%-34s %s" % (name, R[name]))
    return R[name]


def main():
    from google.cloud import firestore
    c = firestore.Client(project=PROJECT)
    ping, ping2 = c.document(BASE + "/ping"), c.document(BASE + "/ping2")
    now = datetime.now(timezone.utc).isoformat()

    step("anon_get_before_create", lambda: anon(BASE + "/ping"))
    created = step("batch_create_2_docs", lambda: (lambda b: (b.set(ping, {"purpose": "write-permission selftest", "at": now}), b.set(ping2, {"purpose": "write-permission selftest", "at": now}), b.commit(), "ok")[-1])(c.batch()))
    try:
        if created == "ok":
            step("read_back_exists", lambda: bool(ping.get().exists) and bool(ping2.get().exists))
            step("anon_get_while_exists", lambda: anon(BASE + "/ping"))
            step("anon_list_while_exists", lambda: anon(BASE + "?pageSize=1&mask.fieldPaths=zznone"))
    finally:
        # 만들기가 실패했어도 일부가 생겼을 수 있으므로 항상 삭제를 시도한다.
        step("delete_2_docs", lambda: (lambda b: (b.delete(ping), b.delete(ping2), b.commit(), "ok")[-1])(c.batch()))
        step("exists_after_delete", lambda: bool(ping.get().exists) or bool(ping2.get().exists))
        step("anon_get_after_delete", lambda: anon(BASE + "/ping"))
        step("anon_list_after_delete", lambda: anon(BASE + "?pageSize=1&mask.fieldPaths=zznone"))

    ok = (R.get("batch_create_2_docs") == "ok" and R.get("read_back_exists") is True and R.get("delete_2_docs") == "ok" and R.get("exists_after_delete") is False
          and all(R.get(k) == 403 for k in ("anon_get_before_create", "anon_get_while_exists", "anon_list_while_exists", "anon_get_after_delete", "anon_list_after_delete")))
    lines = ["## 서비스 계정 Firestore 쓰기 시험 (임시)", "", "- 대상: `%s/{ping,ping2}` (프로젝트 %s)" % (BASE, PROJECT), "- 결과: **%s**" % ("모두 통과" if ok else "실패 있음"), "", "| 단계 | 결과 |", "|---|---|"]
    lines += ["| %s | %s |" % (k, v) for k, v in R.items()]
    lines += ["", "- 기대값: `anon_*` 는 모두 403, `batch_create_2_docs`·`delete_2_docs` 는 ok, `read_back_exists` 는 True, `exists_after_delete` 는 False."]
    summ = os.environ.get("GITHUB_STEP_SUMMARY")
    if summ:
        with open(summ, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        code = main()
    except Exception as ex:
        print("시험 실행 실패:", type(ex).__name__)
        code = 1
    sys.stdout.flush()
    sys.exit(code)
