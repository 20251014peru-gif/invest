# -*- coding: utf-8 -*-
"""mf_publish 단위 시험 — Firestore 없이 가짜 writer 로 검증한다. 실행: python -m unittest discover -s tests/mf -p "test_*.py" -v"""
import os, sys, io, json, tempfile, unittest, contextlib, datetime as dt

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
import mf_publish as pub


def good(n=6, price_date="2026-10-19", **over):
    d = {"schema": "multifactor_kr/1", "version": "v 20261019-2", "generated_at": "2026-10-19T18:00:00+09:00", "price_date": price_date,
         "quarter_date": "2026-06-01", "n": n, "items": [{"code": "%06d" % i, "name": "종목%d" % i, "raw": {"per": 1.5}} for i in range(n)]}
    d.update(over)
    return d


class FakeWriter:
    def __init__(self, existing=None, fail_on_batch=False):
        self.docs = dict(existing or {}); self.batches = []; self.fail = fail_on_batch

    def get(self, path): return self.docs.get(path)

    def write_batch(self, items):
        if self.fail: raise RuntimeError("firestore down: secret-detail-xyz")
        self.batches.append(list(items))
        for p, d in items: self.docs[p] = d           # 실제 배치처럼 한 번에 모두 반영


class BuildTests(unittest.TestCase):
    def test_valid_document_fields_and_payload_roundtrip(self):
        sid, doc, size = pub.build_document(good(), now=dt.datetime(2026, 10, 24, 10, 20, tzinfo=pub.KST))
        self.assertEqual(sid, "2026-10-19")
        self.assertEqual(doc["snapshot_id"], "2026-10-19"); self.assertEqual(doc["n"], 6); self.assertEqual(doc["written_at"], "2026-10-24T10:20:00+09:00")
        self.assertEqual(json.loads(doc["payload"]), good())
        self.assertEqual(size, len(doc["payload"].encode("utf-8")))

    def test_rejects_bad_inputs(self):
        mismatch = good(); mismatch["n"] = 7                                    # n 은 7 인데 항목은 6개
        bad = [good(schema="x/1"), good(n=3, items=good(3)["items"]), mismatch, good(items="nope"), good(price_date="2026/10/19"),
               good(price_date=None), good(items=[{"v": float("nan")}] * 6), {}, [], None, good(items=[{"v": float("inf")}] * 6)]
        for d in bad:
            with self.assertRaises(pub.PublishError, msg=str(d)[:60]):
                pub.build_document(d)

    def test_rejects_oversize_payload(self):
        big = good(items=[{"blob": "가" * 2000} for _ in range(400)], n=400)   # 한글 3바이트 × 2000 × 400 ≈ 2.4MB
        with self.assertRaises(pub.PublishError): pub.build_document(big)

    def test_korean_text_survives_and_is_not_escaped(self):
        _, doc, _ = pub.build_document(good())
        self.assertIn("종목1", doc["payload"])


class PublishTests(unittest.TestCase):
    def test_writes_snapshot_and_latest_in_one_batch_with_same_doc(self):
        w = FakeWriter()
        sid, _ = pub.publish(good(), w)
        self.assertEqual(len(w.batches), 1)
        paths = [p for p, _ in w.batches[0]]
        self.assertEqual(paths, [pub.BASE_PATH + "/2026-10-19", pub.LATEST])
        self.assertEqual(w.batches[0][0][1], w.batches[0][1][1])
        self.assertTrue(pub.LATEST.startswith("chatgpt_macro_private/multifactor_kr/"))   # 비로그인 접근이 막힌 경로에만 쓴다

    def test_batch_failure_leaves_nothing_written(self):
        w = FakeWriter(fail_on_batch=True)
        with self.assertRaises(RuntimeError): pub.publish(good(), w)
        self.assertEqual(w.docs, {})

    def test_invalid_input_never_touches_writer(self):
        w = FakeWriter()
        with self.assertRaises(pub.PublishError): pub.publish(good(schema="bad"), w)
        self.assertEqual(w.batches, [])

    def test_refuses_older_result_over_newer_latest(self):
        w = FakeWriter({pub.LATEST: {"price_date": "2026-10-26"}})
        with self.assertRaises(pub.PublishError) as cm: pub.publish(good(price_date="2026-10-19"), w)
        self.assertEqual(cm.exception.code, 4); self.assertEqual(w.batches, [])

    def test_force_overrides_stale_guard(self):
        w = FakeWriter({pub.LATEST: {"price_date": "2026-10-26"}})
        pub.publish(good(price_date="2026-10-19"), w, force=True)
        self.assertEqual(w.docs[pub.LATEST]["price_date"], "2026-10-19")

    def test_same_or_newer_date_overwrites(self):
        for old in ("2026-10-19", "2026-10-12", None):
            w = FakeWriter({pub.LATEST: {"price_date": old}} if old else {})
            pub.publish(good(price_date="2026-10-19"), w)
            self.assertEqual(w.docs[pub.LATEST]["snapshot_id"], "2026-10-19")


class MainTests(unittest.TestCase):
    def run_main(self, data, args=(), writer=None, raw_text=None):
        d = tempfile.mkdtemp(); p = os.path.join(d, "mf.json")
        with open(p, "w", encoding="utf-8") as f: f.write(raw_text if raw_text is not None else json.dumps(data, ensure_ascii=False))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = pub.main(["--in", p, *args], writer_factory=lambda project: writer)
        return code, out.getvalue()

    def test_dry_run_validates_without_writing(self):
        w = FakeWriter()
        code, out = self.run_main(good(), ["--dry-run"], writer=w)
        self.assertEqual(code, 0); self.assertEqual(w.batches, []); self.assertIn("쓰지 않음", out)

    def test_publish_ok_prints_no_payload(self):
        w = FakeWriter()
        code, out = self.run_main(good(), writer=w)
        self.assertEqual(code, 0); self.assertNotIn("종목1", out); self.assertEqual(len(w.batches), 1)

    def test_write_failure_returns_2_and_hides_exception_text(self):
        code, out = self.run_main(good(), writer=FakeWriter(fail_on_batch=True))
        self.assertEqual(code, 2); self.assertNotIn("secret-detail-xyz", out); self.assertIn("RuntimeError", out)

    def test_connection_failure_returns_2_without_details(self):
        def boom(project): raise PermissionError("creds file C:/secret/key.json")
        d = tempfile.mkdtemp(); p = os.path.join(d, "mf.json")
        with open(p, "w", encoding="utf-8") as f: json.dump(good(), f)
        out = io.StringIO()
        with contextlib.redirect_stdout(out): code = pub.main(["--in", p], writer_factory=boom)
        self.assertEqual(code, 2); self.assertNotIn("secret", out.getvalue())

    def test_stale_returns_4(self):
        code, _ = self.run_main(good(price_date="2026-10-19"), writer=FakeWriter({pub.LATEST: {"price_date": "2026-11-02"}}))
        self.assertEqual(code, 4)

    def test_unreadable_or_invalid_file_returns_2(self):
        self.assertEqual(self.run_main(None, raw_text="{not json")[0], 2)
        out = io.StringIO()
        with contextlib.redirect_stdout(out): self.assertEqual(pub.main(["--in", "Z:/no/such/file.json"], writer_factory=lambda p: FakeWriter()), 2)
        self.assertEqual(self.run_main(good(schema="bad"), writer=FakeWriter())[0], 2)


if __name__ == "__main__":
    unittest.main()
