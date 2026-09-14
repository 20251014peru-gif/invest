"""Local-only synthetic service. Public cloud deployment is intentionally unsupported."""
import argparse
import hmac
import json
import os
import re
from pathlib import Path
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from job_store import JobStore, Conflict, QueueFull, process_one
from pipeline_processor import pipeline_processor


class ExclusiveWorker:
    def __init__(self, path):
        self.file = open(path, 'a+b')
        try:
            self.file.seek(0)
            if not self.file.read(1):
                self.file.write(b'0'); self.file.flush()
            self.file.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException:
            self.file.close()
            raise RuntimeError('이 저장소의 작업 서버가 이미 실행 중입니다.') from None

    def close(self):
        self.file.close()


def synthetic_processor(payload):
    time.sleep(2)
    return {'mode': 'synthetic', 'text': '합성 시험 완료 — 실제 AI 요약이 아닙니다.',
            'input_chars': len(payload['transcript']), 'ai_calls': 0, 'firestore_writes': 0}


def handler_for(store, tokens, pipeline_enabled=False, healthy=lambda: True):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # Do not log titles, transcript bodies, or credentials.

        def respond(self, status, value, content_type='application/json; charset=utf-8'):
            body = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'none'")
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass  # Client disconnect never cancels an accepted, persisted job.

        def owner(self):
            supplied = self.headers.get('Authorization', '')
            if not supplied.isascii():
                return None
            for token, owner in tokens.items():
                if hmac.compare_digest(supplied, 'Bearer ' + token):
                    return owner
            return None

        def do_GET(self):
            path = urlsplit(self.path).path
            if path == '/':
                return self.respond(200, Path(__file__).with_name('job-demo.html').read_bytes(), 'text/html; charset=utf-8')
            if path == '/youtube.html':
                if not pipeline_enabled:
                    return self.respond(409, {'error': '--processor pipeline 옵션으로 시험 서버를 실행하세요.'})
                html = Path(__file__).with_name('youtube.html').read_text(encoding='utf-8')
                html = re.sub(r'<script\b[^>]*\bsrc=["\']https?://[^>]*>\s*</script>', '', html, flags=re.I)
                html = html.replace('<head>', '<head><script src="offline-fixture.js"></script><script src="queue-client.js"></script>', 1)
                return self.respond(200, html.encode('utf-8'), 'text/html; charset=utf-8')
            if path in ['/connection.js', '/offline-fixture.js', '/queue-client.js']:
                return self.respond(200, Path(__file__).with_name(path[1:]).read_bytes(), 'application/javascript; charset=utf-8')
            if path == '/connection-config.js':
                return self.respond(200, b'window.YT_CONNECTION_CONFIG={};', 'application/javascript')
            owner = self.owner()
            if owner is None:
                return self.respond(401, {'error': '시험용 접근 코드를 입력하세요.'})
            if path == '/api/jobs':
                return self.respond(200, {'jobs': store.list(owner)})
            if path.startswith('/api/jobs/'):
                row = store.get(owner, path.rsplit('/', 1)[-1])
                return self.respond(200 if row else 404, row or {'error': '작업을 찾을 수 없습니다.'})
            return self.respond(404, {'error': '없는 경로입니다.'})

        def do_POST(self):
            owner = self.owner()
            if owner is None:
                return self.respond(401, {'error': '시험용 접근 코드를 입력하세요.'})
            if self.path != '/api/jobs':
                return self.respond(404, {'error': '없는 경로입니다.'})
            if not healthy():
                return self.respond(503, {'error': '작업 처리기가 중단되었습니다. 서버 상태를 확인하세요.'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 600000:
                    return self.respond(413, {'error': '요청 크기를 확인하세요.'})
                if self.headers.get_content_type() != 'application/json':
                    return self.respond(415, {'error': 'JSON 요청이 필요합니다.'})
                self.connection.settimeout(5)
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict) or set(body) != {'request_key', 'payload'}:
                    raise ValueError()
                if pipeline_enabled and (not isinstance(body['payload'], dict) or
                        not isinstance(body['payload'].get('transcript'), str) or
                        len(body['payload']['transcript'].strip()) < 300):
                    raise ValueError()
                row, created = store.submit(owner, body['request_key'], body['payload'])
                return self.respond(202 if created else 200, row)
            except Conflict:
                return self.respond(409, {'error': '같은 요청 식별자의 내용이 다릅니다.'})
            except QueueFull:
                return self.respond(429, {'error': '대기 작업 한도를 초과했습니다.'})
            except (ValueError, TypeError, KeyError, TimeoutError):
                return self.respond(400, {'error': '제목·자막·요청 형식을 확인하세요.'})
            except Exception:
                return self.respond(503, {'error': '저장 확인이 되지 않았습니다. 동일한 요청으로 접수 확인을 하세요.'})
    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', required=True)
    parser.add_argument('--port', type=int, default=0)
    parser.add_argument('--ready-file', required=True)
    parser.add_argument('--processor', choices=['synthetic', 'pipeline'], default='synthetic')
    args = parser.parse_args()
    token = os.environ.get('YT_JOB_TEST_TOKEN', '')
    if len(token) < 24 or not token.isascii():
        raise SystemExit('24자 이상의 ASCII 시험 토큰을 환경변수 YT_JOB_TEST_TOKEN에 지정하세요.')
    db_path = Path(args.db).resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    guard = ExclusiveWorker(str(db_path) + '.lock')
    store = JobStore(db_path)
    store.recover_interrupted()
    stop = threading.Event()
    def worker():
        while not stop.is_set():
            try:
                worked = process_one(store, pipeline_processor if args.processor == 'pipeline' else synthetic_processor)
            except BaseException:
                stop.set()  # Storage failure stops the worker, no repeat inference.
                break
            if not worked:
                stop.wait(0.1)
    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), handler_for(store, {token: 'local-test'}, args.processor == 'pipeline', lambda: not stop.is_set()))
    Path(args.ready_file).write_text(json.dumps({'url': 'http://127.0.0.1:%s/' % server.server_port, 'mode': 'synthetic'}))
    try:
        server.serve_forever()
    finally:
        stop.set(); server.server_close(); thread.join(); guard.close()


if __name__ == '__main__':
    main()
