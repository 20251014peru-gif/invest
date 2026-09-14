import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from job_store import JobStore, Conflict, QueueFull, process_one
from job_service import ExclusiveWorker


class JobsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'jobs.sqlite'
        self.store = JobStore(self.path)
        self.payload = {'title': 'synthetic', 'transcript': 'x' * 100}

    def submit(self, key='request-0001'):
        return self.store.submit('a', key, self.payload)[0]

    def test_persistence_and_owner_isolation(self):
        row = self.submit()
        reopened = JobStore(self.path)
        self.assertEqual(row, reopened.get('a', row['id']))
        self.assertIsNone(reopened.get('b', row['id']))
        self.assertEqual([], reopened.list('b'))
        self.assertNotIn('transcript', row)

    def test_concurrent_idempotency_and_collision(self):
        with ThreadPoolExecutor(8) as pool:
            rows = list(pool.map(lambda _: self.submit(), range(8)))
        self.assertEqual(1, len({r['id'] for r in rows}))
        with self.assertRaises(Conflict):
            self.store.submit('a', 'request-0001', {**self.payload, 'title': 'different'})

    def test_concurrent_claim_and_fencing(self):
        row = self.submit()
        with ThreadPoolExecutor(8) as pool:
            claims = [j for j in pool.map(lambda _: self.store.claim_next(), range(8)) if j]
        self.assertEqual(1, len(claims))
        self.store.finish(claims[0], result={'text': 'ok'})
        with self.assertRaises(Conflict):
            self.store.finish(claims[0], result={'text': 'overwrite'})
        self.assertEqual('ok', self.store.get('a', row['id'])['result']['text'])

    def test_recovery_does_not_repeat_work(self):
        running = self.submit()
        claim = self.store.claim_next()
        queued = self.submit('request-0002')
        self.assertEqual(1, self.store.recover_interrupted())
        self.assertEqual('uncertain', self.store.get('a', running['id'])['status'])
        self.assertEqual('queued', self.store.get('a', queued['id'])['status'])
        with self.assertRaises(Conflict):
            self.store.finish(claim, result={})

    def test_processor_failure_redacted_and_terminal(self):
        row = self.submit()
        def failing(_):
            raise RuntimeError('secret transcript')
        self.assertTrue(process_one(self.store, failing))
        self.assertFalse(process_one(self.store, failing))
        result = self.store.get('a', row['id'])
        self.assertEqual('failed', result['status'])
        self.assertNotIn('secret', result['error'])

    def test_result_storage_failure_never_repeats_processor(self):
        row = self.submit()
        calls = []
        with patch.object(self.store, 'finish', side_effect=OSError('disk')):
            with self.assertRaises(OSError):
                process_one(self.store, lambda p: calls.append(p) or {'text': 'ok'})
        self.store.recover_interrupted()
        self.assertFalse(process_one(self.store, lambda p: calls.append(p)))
        self.assertEqual(1, len(calls))
        self.assertEqual('uncertain', self.store.get('a', row['id'])['status'])

    def test_limits(self):
        with self.assertRaises(ValueError):
            self.store.submit('a', 'request-0001', {'title': 't', 'transcript': 'short'})
        for i in range(20):
            self.submit('request-%04d' % i)
        with self.assertRaises(QueueFull):
            self.submit('request-0021')
        self.assertFalse(self.store.submit('a', 'request-0000', self.payload)[1])

    def test_exclusive_worker(self):
        guard = ExclusiveWorker(str(self.path) + '.lock')
        try:
            with self.assertRaises(RuntimeError):
                ExclusiveWorker(str(self.path) + '.lock')
        finally:
            guard.close()
        ExclusiveWorker(str(self.path) + '.lock').close()

    def test_metadata_roundtrip_and_validation(self):
        payload = {**self.payload, 'channel':'test', 'timeline':'00:00 start', 'chaptersOnly':True}
        self.store.submit('a', 'request-meta', payload)
        self.assertEqual(payload, self.store.claim_next()['payload'])
        with self.assertRaises(ValueError):
            self.store.submit('a', 'request-bad1', {**self.payload, 'chaptersOnly':'false'})
        with self.assertRaises(ValueError):
            self.store.submit('a', 'request-bad2', {**self.payload, 'timeline':'x'*20001})


if __name__ == '__main__':
    unittest.main()
