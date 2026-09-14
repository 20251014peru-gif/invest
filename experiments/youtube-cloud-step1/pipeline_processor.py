"""No real inference adapter: executes the original pipeline with blocked I/O."""
import json
import os
from pathlib import Path
import signal
import subprocess


def pipeline_processor(payload):
    node = os.environ.get('TEST_NODE', 'node')
    worker = str(Path(__file__).with_name('pipeline-worker.cjs'))
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    child = subprocess.Popen([node, worker], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, encoding='utf-8',
                             creationflags=flags, start_new_session=os.name != 'nt')
    try:
        out, _ = child.communicate(json.dumps(payload, ensure_ascii=False), timeout=90)
    except BaseException:
        # Reap the entire Node/browser process tree before the next job can start.
        if os.name == 'nt':
            killed = subprocess.run(['taskkill', '/PID', str(child.pid), '/T', '/F'],
                                    capture_output=True, creationflags=flags)
            if killed.returncode and child.poll() is None:
                raise SystemExit('Worker tree termination failed; stop processing.')
        else:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        child.communicate()
        raise
    if child.returncode:
        raise RuntimeError('Synthetic pipeline failed')
    result = json.loads(out)
    if result.get('mode') != 'synthetic-pipeline' or result.get('ai_calls') != 0 or result.get('firestore_writes') != 0:
        raise RuntimeError('Unexpected processor output')
    return result
