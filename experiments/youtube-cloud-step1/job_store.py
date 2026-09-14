"""Durable, owner-scoped job core. No AI/network/Firestore imports."""
import hashlib
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager


class Conflict(ValueError):
    pass


class QueueFull(ValueError):
    pass


class JobStore:
    def __init__(self, path):
        self.path = str(path)
        with self.connection() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('''CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, owner TEXT NOT NULL, request_key TEXT NOT NULL,
                payload_hash TEXT NOT NULL, payload TEXT NOT NULL, status TEXT NOT NULL,
                result TEXT, error TEXT, claim TEXT, created REAL NOT NULL, updated REAL NOT NULL,
                UNIQUE(owner, request_key))''')

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA synchronous=FULL')
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def submit(self, owner, key, payload):
        if not isinstance(key, str) or not 8 <= len(key) <= 128:
            raise ValueError('요청 식별자를 확인하세요.')
        if not isinstance(payload, dict) or set(payload) != {'title', 'transcript'}:
            raise ValueError('제목과 자막을 입력하세요.')
        if not isinstance(payload['title'], str) or not 1 <= len(payload['title'].strip()) <= 300:
            raise ValueError('제목 길이를 확인하세요.')
        if not isinstance(payload['transcript'], str) or not 100 <= len(payload['transcript'].strip()) <= 80000:
            raise ValueError('자막은 100~80,000자까지 입력하세요.')
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        digest = hashlib.sha256(encoded.encode()).hexdigest()
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            previous = db.execute('SELECT * FROM jobs WHERE owner=? AND request_key=?', (owner, key)).fetchone()
            if previous:
                if previous['payload_hash'] != digest:
                    raise Conflict('같은 요청 식별자에 다른 내용이 제출되었습니다.')
                return self.public(previous), False
            count = db.execute("SELECT COUNT(*) FROM jobs WHERE owner=? AND status IN ('queued','running')", (owner,)).fetchone()[0]
            if count >= 20:
                raise QueueFull('대기 작업이 많습니다. 완료 후 다시 접수하세요.')
            ident, now = uuid.uuid4().hex, time.time()
            db.execute('INSERT INTO jobs (id,owner,request_key,payload_hash,payload,status,created,updated) VALUES (?,?,?,?,?,?,?,?)',
                       (ident, owner, key, digest, encoded, 'queued', now, now))
            return self.public(db.execute('SELECT * FROM jobs WHERE id=?', (ident,)).fetchone()), True

    @staticmethod
    def public(row):
        return {'id': row['id'], 'title': json.loads(row['payload'])['title'], 'status': row['status'],
                'result': json.loads(row['result']) if row['result'] else None,
                'error': row['error'], 'created': row['created'], 'updated': row['updated']}

    def get(self, owner, ident):
        with self.connection() as db:
            row = db.execute('SELECT * FROM jobs WHERE id=? AND owner=?', (ident, owner)).fetchone()
            return self.public(row) if row else None

    def list(self, owner):
        with self.connection() as db:
            return [self.public(r) for r in db.execute('SELECT * FROM jobs WHERE owner=? ORDER BY created DESC LIMIT 100', (owner,))]

    def claim_next(self):
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY created, id LIMIT 1").fetchone()
            if not row:
                return None
            claim = uuid.uuid4().hex
            db.execute("UPDATE jobs SET status='running',claim=?,updated=? WHERE id=?", (claim, time.time(), row['id']))
            return {'id': row['id'], 'claim': claim, 'payload': json.loads(row['payload'])}

    def finish(self, job, result=None, error=None):
        with self.connection() as db:
            changed = db.execute("UPDATE jobs SET status=?,result=?,error=?,updated=? WHERE id=? AND claim=? AND status='running'",
                ('failed' if error else 'succeeded', json.dumps(result, ensure_ascii=False) if result is not None else None,
                 error, time.time(), job['id'], job['claim'])).rowcount
            if not changed:
                raise Conflict('작업 상태가 변경되어 결과를 덮어쓰지 않았습니다.')

    def recover_interrupted(self):
        """Only call while holding the service's exclusive worker lock."""
        with self.connection() as db:
            return db.execute("UPDATE jobs SET status='uncertain',error='처리 중 서버가 중단되었습니다. 자동 재호출하지 않습니다.',updated=? WHERE status='running'", (time.time(),)).rowcount


def process_one(store, processor):
    job = store.claim_next()
    if not job:
        return False
    try:
        result = processor(job['payload'])
    except Exception:
        store.finish(job, error='작업 처리 실패. 원본 입력은 보존되며 자동 재호출하지 않습니다.')
    else:
        # A failed result write is not classified as a failed model call. Leave running
        # for uncertain recovery; never automatically repeat an external call.
        store.finish(job, result=result)
    return True
