"""macro.yml '실행하고 커밋·push' 단계의 실패 전파 시험 (실제 bash 스크립트를 꺼내 임시 git 저장소에서 실행).
사용: python3 tests/test_macro_workflow.py   (bash·git 필요. Windows 는 Git Bash)
검사: macro_periods 종료코드 1이면 (변경 있음/없음/push 재시도 후) 모두 최종 exit 1, 성공이면 exit 0,
      실패 알림 단계가 if: failure() 로 뒤에 있는지."""
import json, os, re, shutil, stat, subprocess, sys, tempfile

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
BASH = shutil.which('bash')


def workflow_parts():
    with open(os.path.join(ROOT, '.github', 'workflows', 'macro.yml'), encoding='utf-8') as f:
        text = f.read()
    m = re.search(r"      - name: 실행하고[^\n]*\n(?:        [^\n]*\n)*?        run: \|\n((?:          [^\n]*\n|\n)+)", text)
    assert m, '실행 단계를 찾지 못함'
    script = '\n'.join(l[10:] if l.startswith('          ') else l for l in m.group(1).split('\n'))
    notify = re.search(r"      - name: 실패하면 폰으로 알림\n        if: failure\(\)", text)
    assert notify and notify.start() > m.end() - 1, '실패 알림 단계(if: failure())가 실행 단계 뒤에 없음'
    assert 'FRED_API_KEY: ${{ secrets.FRED_API_KEY }}' in text, 'FRED_API_KEY가 수집 단계 환경변수에 연결되지 않음'
    return script


def sh(cmd, cwd, env=None):
    return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, encoding='utf-8', errors='replace')


def git(cwd, *a):
    r = sh(['git', '-c', 'user.name=t', '-c', 'user.email=t@t', *a], cwd)
    assert r.returncode == 0, (a, r.stderr)
    return r.stdout.strip()


def write_exec(path, text):
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)
    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)


def case(script, periods_rc, change, push_fail_times=0, push_always_fail=False, report_rc=0):
    tmp = tempfile.mkdtemp()
    try:
        origin, work, binp = (os.path.join(tmp, n) for n in ('origin.git', 'work', 'bin'))
        os.makedirs(binp)
        sh(['git', 'init', '-q', '--bare', '-b', 'main', origin], tmp)
        sh(['git', 'clone', '-q', origin, work], tmp)
        for d in ('scripts', 'facts', 'analysis', 'log', 'data'):
            os.makedirs(os.path.join(work, d), exist_ok=True)
        for f in ('macro.py', 'macro_extra.py', 'regime.py', 'calendar.py', 'macro_time_meta.py', 'journal.py'):
            write_exec(os.path.join(work, 'scripts', f), 'import sys\nsys.exit(0)\n')
        # macro.py 는 변경 여부를 환경변수로 제어한다 (실제 수집기 대역)
        write_exec(os.path.join(work, 'scripts', 'macro.py'),
                   "import os, time\nif os.environ.get('STUB_CHANGE') == '1':\n    open('facts/macro.json', 'w').write(str(time.time()))\n")
        write_exec(os.path.join(work, 'scripts', 'macro_periods.py'), "import os, sys\nsys.exit(int(os.environ.get('STUB_PERIODS_RC', '0')))\n")
        write_exec(os.path.join(work, 'scripts', 'report_feeds.py'), "import os, sys\nsys.exit(int(os.environ.get('STUB_REPORT_RC', '0')))\n")
        for f in ('facts/macro_periods.json', 'facts/macro.json', 'facts/macro_history.json', 'facts/macro_extra.json', 'facts/macro_extra_history.json',
                  'facts/kr_key.json', 'facts/calendar_sent.json', 'facts/market_report_feeds.json', 'facts/market_report_validation.json', 'facts/market_report_clock.json', 'facts/report_candidates/.gitkeep', 'facts/report_editions/.gitkeep', 'analysis/regime.json', 'analysis/calendar.json', 'log/.keep', 'data/status.json'):
            os.makedirs(os.path.dirname(os.path.join(work, f)), exist_ok=True)
            open(os.path.join(work, f), 'w').write('0')  # git add 경로가 하나라도 없으면 실제 워크플로처럼 전체가 실패하므로 모두 만든다
        git(work, 'checkout', '-q', '-b', 'main'); git(work, 'add', '-A'); git(work, 'commit', '-q', '-m', 'init'); git(work, 'push', '-q', 'origin', 'main')
        counter = os.path.join(tmp, 'pushes')
        hook = os.path.join(origin, 'hooks', 'pre-receive')
        write_exec(hook, "#!/bin/sh\nn=$(cat '%s' 2>/dev/null || echo 0); n=$((n+1)); echo $n > '%s'\n%s\n" % (
            counter.replace('\\', '/'), counter.replace('\\', '/'),
            'exit 1' if push_always_fail else ('[ "$n" -le %d ] && exit 1 || exit 0' % push_fail_times)))
        write_exec(os.path.join(binp, 'python'), '#!/bin/sh\nexec "%s" "$@"\n' % sys.executable.replace('\\', '/'))
        write_exec(os.path.join(binp, 'sleep'), '#!/bin/sh\nexit 0\n')  # push 재시도 대기 생략
        env = dict(os.environ, PATH=binp + os.pathsep + os.environ['PATH'], STUB_PERIODS_RC=str(periods_rc), STUB_REPORT_RC=str(report_rc), STUB_CHANGE='1' if change else '0', NTFY_TOPIC='')
        spath = os.path.join(tmp, 'step.sh')  # 한글이 든 스크립트를 인자로 넘기면 비UTF-8 로케일에서 실패하므로 파일로 실행
        with open(spath, 'w', encoding='utf-8', newline='\n') as f:
            f.write(script)
        r = sh([BASH, spath], work, env)
        return r.returncode, r.stdout + r.stderr, git(work, 'log', '--oneline', 'origin/main').count('\n') + 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    assert BASH, 'bash 가 필요함(Windows 는 Git Bash)'
    script = workflow_parts()
    rc, log, n = case(script, 1, change=True)
    assert rc == 1 and n == 2 and 'macro_periods 종료코드 1' in log, (rc, n, log[-400:])  # 저장·push 는 끝난 뒤 실패
    rc, log, n = case(script, 1, change=False)
    assert rc == 1 and n == 1 and '변경 없음' in log and 'macro_periods 종료코드 1' in log, (rc, log[-400:])  # 변경 없어도 exit 0 금지
    rc, log, n = case(script, 0, change=True)
    assert rc == 0 and n == 2, (rc, log[-300:])
    rc, log, n = case(script, 0, change=False)
    assert rc == 0 and n == 1, (rc, log[-300:])
    rc, log, n = case(script, 1, change=True, push_fail_times=2)  # push 2번 밀린 뒤 성공해도 실패 코드가 유실되지 않음
    assert rc == 1 and n == 2 and 'push 성공 (시도 3 회)' in log, (rc, n, log[-500:])
    rc, log, n = case(script, 0, change=True, push_always_fail=True)  # 기존 동작: push 4회 실패는 실패
    assert rc == 1 and 'push 4회 실패' in log, (rc, log[-300:])
    for change in (True, False):
        rc, log, n = case(script, 0, change=change, report_rc=1)
        assert rc == 1 and '보고서 수집 경로 실패' in log, (rc, log[-400:])
    print('OK: 워크플로 실패 전파 시험 통과 (실패+변경 / 실패+무변경 / 성공 / push 재시도 후 실패 코드 유지 / push 전부 실패 / 알림 단계 위치)')


if __name__ == '__main__':
    main()
