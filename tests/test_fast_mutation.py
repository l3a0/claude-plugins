#!/usr/bin/env python3
"""Tests for skills/fast-mutation/scripts/mutate.py's script runner, on a repository it builds in a temporary folder.

    python3 tests/test_fast_mutation.py

The pytest runner and its coverage map need pytest, which CI does not install, so only the script runner is tested.
"""
import json, os, signal, stat, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, '..', 'skills', 'fast-mutation', 'scripts', 'mutate.py')

failures = 0


def check(name, cond):
    global failures
    print(('ok   ' if cond else 'FAIL ') + name)
    failures += not cond


MOD = 'def add(a, b):\n    return a + b\n\n\ndef sign(x):\n    return 1 if x > 0 else -1\n'
NEAR = '''import sys
sys.path.insert(0, '.')
from mod import add
print('ok   setup')
bad = 0
for got, want in ((add(2, 3), 5),):
    print(('ok   ' if got == want else 'FAIL ') + 'add')
    bad += got != want
sys.exit(bad)
'''
FAR = '''import sys
sys.path.insert(0, '.')
from mod import sign
print('ok   sign' if sign(-2) == -1 else 'FAIL sign of a negative')
sys.exit(0 if sign(-2) == -1 else 1)
'''
CRASH = 'import sys\nsys.exit(3)\n'
LOUD = 'import sys\nprint("boom", file=sys.stderr)\nsys.exit(3)\n'
FAILED = 'import sys\nprint("ok   first")\nprint("FAILED the second check")\nsys.exit(1)\n'
ERRORS = 'import sys\nprint("ERROR: test_lookup (t.T)")\nsys.exit(1)\n'
SLOW = 'import sys, time\ntime.sleep(float(sys.argv[1]) if len(sys.argv) > 1 else 3)\n'
READS = 'import sys\nsys.stdin.read()\n'

with tempfile.TemporaryDirectory() as root:
    repo = os.path.join(root, 'repo')
    os.makedirs(os.path.join(repo, 'tests'))
    for path, text in (('mod.py', MOD), ('tests/near.py', NEAR), ('tests/far.py', FAR), ('tests/crash.py', CRASH),
                       ('tests/loud.py', LOUD), ('tests/failed.py', FAILED), ('tests/errors.py', ERRORS),
                       ('tests/slow.py', SLOW), ('tests/reads.py', READS)):
        with open(os.path.join(repo, path), 'w') as f:
            f.write(text)
    subprocess.run(['git', '-C', repo, 'init', '-q'], check=True)

    def run(spec, *args):
        path = os.path.join(root, 'spec.json')
        with open(path, 'w') as f:
            json.dump(spec, f)
        out = os.path.join(root, 'out')
        # A pipe nobody writes to, so a child that read the runner's stdin would wait on it.
        quiet, held = os.pipe()
        try:
            done = subprocess.run([sys.executable, SCRIPT, path, '--out', out, *args], capture_output=True, text=True,
                                  stdin=quiet, timeout=120)
        finally:
            os.close(quiet), os.close(held)
        rows = []
        if os.path.exists(os.path.join(out, 'results.jsonl')):
            with open(os.path.join(out, 'results.jsonl')) as f:
                rows = [json.loads(line) for line in f]
        return done.returncode, done.stdout + done.stderr, rows

    spec = {'runner': 'script', 'root': repo, 'python': sys.executable,
            'baseline': [['tests/near.py'], ['tests/far.py']], 'select': ['tests/near.py'],
            'escalate': [['tests/near.py'], ['tests/far.py']],
            'mutants': [
                {'name': 'add subtracts', 'file': 'mod.py', 'edits': [['return a + b', 'return a - b']]},
                {'name': 'sign flips', 'file': 'mod.py', 'edits': [['else -1', 'else 1']]},
                {'name': 'not there', 'file': 'mod.py', 'edits': [['return a * b', 'return 0']]},
            ]}
    code, out, rows = run(spec)
    by = {r['name']: r for r in rows if not r.get('escalated')}
    wide = {r['name']: r for r in rows if r.get('escalated')}
    check('exits 0 on a green baseline', code == 0)
    check('reads a green baseline of two commands', 'BASE green' in out and by['BASE']['status'] == 'green'
          and by['BASE']['summary'] == '2 command(s), 0 failure(s)')
    check('catches a mutant the selection notices', by['add subtracts']['status'] == 'red' and 'CAUGHT' in out)
    check('names the failing line', by['add subtracts']['failed'] == ['FAIL add'])
    check('a survivor of the selection is caught by the full escalate run',
          by['sign flips']['status'] == 'green' and wide['sign flips']['status'] == 'red'
          and 'CAUGHT-WIDE' in out and 'scope=full (script runner, no coverage map)' in out)
    check('names the failing line of the escalate run', wide['sign flips']['failed'] == ['FAIL sign of a negative'])
    check('reports an edit that does not apply', by['not there']['status'] == 'not-applied')
    with open(os.path.join(repo, 'mod.py')) as f:
        check('restores the file byte for byte', f.read() == MOD)

    code, out, rows = run(dict(spec, escalate=[['tests/near.py']]))
    check('a survivor of every run reads SURVIVED-ALL', 'SURVIVED-ALL' in out)

    code, out, rows = run(dict(spec, baseline=['tests/crash.py']))
    check('stops on a red baseline', code == 2 and 'baseline is not green' in out)

    crashing = dict(spec['mutants'][1], select=['tests/crash.py'])
    code, out, rows = run(dict(spec, mutants=[crashing]), '--no-escalate')
    check('names a command that failed without a FAIL line', rows[1]['status'] == 'red'
          and rows[1]['failed'] == ['tests/crash.py: exit 3'])
    code, out, rows = run(dict(spec, mutants=[dict(crashing, select=['tests/loud.py'])]), '--no-escalate')
    check('names a command that failed without a FAIL line by its last output line',
          rows[1]['failed'] == ['tests/loud.py: boom'])
    code, out, rows = run(dict(spec, mutants=[dict(crashing, select=[['tests/failed.py'], ['tests/errors.py']])]),
                          '--no-escalate')
    check('the default pattern reads FAILED and ERROR lines after an ok line',
          rows[1]['failed'] == ['FAILED the second check', 'ERROR: test_lookup (t.T)'])

    both = {'name': 'both broken', 'file': 'mod.py', 'edits': [['return a + b', 'return a - b'], ['else -1', 'else 1']]}
    code, out, rows = run(dict(spec, mutants=[both], select=[['tests/near.py'], ['tests/far.py']]), '--no-escalate')
    check('keeps the failures of every command that failed', rows[1]['failed'] == ['FAIL add', 'FAIL sign of a negative'])

    code, out, rows = run(dict(spec, mutants=[dict(both, select=['tests/slow.py'])], timeout=1), '--no-escalate')
    check('a script past its time limit reads TIMEOUT', rows[1]['status'] == 'timeout' and 'TIMEOUT' in out)
    code, out, rows = run(dict(spec, mutants=[dict(both, select=[['tests/slow.py', '0.7'], ['tests/slow.py', '0.7']])],
                               timeout=1), '--no-escalate')
    check('the time limit is shared by the commands of a selection', rows[1]['status'] == 'timeout')
    code, out, rows = run(dict(spec, mutants=[dict(both, select=[['tests/near.py'], ['tests/slow.py', '5']])], timeout=2),
                          '--no-escalate')
    check('a run that failed before its time ran out reads red', rows[1]['status'] == 'red'
          and rows[1]['failed'] == ['FAIL add'])

    survivor = {'name': 'comment only', 'file': 'mod.py', 'edits': [['def add(a, b):', 'def add(a, b):  # x']]}
    # A limit of 3 s gives 6 s by default, with 2 s of margin on each side for a loaded runner.
    code, out, rows = run(dict(spec, mutants=[survivor], timeout=3, escalate=[['tests/slow.py', '4']]))
    check('escalation gets more than the time limit by default', 'SURVIVED-ALL' in out and 'TIMEOUT-WIDE' not in out)
    code, out, rows = run(dict(spec, mutants=[survivor], timeout=3, escalate=[['tests/slow.py', '8']]))
    check('escalation gets no more than twice the time limit by default', 'TIMEOUT-WIDE' in out)
    code, out, rows = run(dict(spec, baseline=[['tests/slow.py', '2'], ['tests/slow.py', '2']], mutants=[], timeout=3))
    check('the baseline gets more than the time limit by default', code == 0 and 'BASE green' in out)
    code, out, rows = run(dict(spec, baseline=['tests/slow.py', '8'], mutants=[], timeout=3))
    check('the baseline gets no more than twice the time limit by default', code == 2 and 'BASE timeout' in out)
    code, out, rows = run(dict(spec, baseline=['tests/slow.py', '1.5'], mutants=[], timeout=3, escalate_timeout=1))
    check('the baseline runs under escalate_timeout when the spec sets it', code == 2 and 'BASE timeout' in out)
    code, out, rows = run(dict(spec, mutants=[survivor], timeout=1, escalate_timeout=1, escalate=[['tests/slow.py', '1.5']]))
    check('escalate_timeout limits escalation', 'TIMEOUT-WIDE' in out)
    code, out, rows = run({k: v for k, v in dict(spec, mutants=[survivor]).items() if k != 'escalate'})
    check('says when survivors were not escalated because escalate is missing', code == 0
          and 'no escalate selection' in out)
    code, out, rows = run({k: v for k, v in dict(spec, mutants=[dict(survivor, select=['tests/near.py'])]).items()
                           if k != 'select'}, '--no-escalate')
    check('needs no default select when every mutant has its own', code == 0 and 'SURVIVED' in out)
    code, out, rows = run({k: v for k, v in dict(spec, mutants=[survivor]).items() if k != 'escalate'}, '--no-escalate')
    check('says nothing about a missing escalate under --no-escalate', code == 0 and 'no escalate selection' not in out)
    check('prints the out folder before the baseline', out.splitlines()[0].startswith('out '))

    code, out, rows = run(dict(spec, baseline=['tests/reads.py'], mutants=[], timeout=20))
    check('a test that reads stdin gets an empty stdin and does not hang', code == 0 and 'BASE green' in out
          and rows[0]['secs'] < 10)

    with open(os.path.join(root, 'outside.py'), 'w') as f:
        f.write('X = 1\n')
    for label, name in (('a path that climbs out of root', '../outside.py'),
                        ('an absolute path outside root', os.path.join(root, 'outside.py'))):
        code, out, rows = run(dict(spec, mutants=[{'name': 'escape', 'file': name, 'edits': [['X = 1', 'X = 2']]}]))
        with open(os.path.join(root, 'outside.py')) as f:
            check(f'refuses {label}, and writes nothing', code != 0 and 'must sit inside root' in out and f.read() == 'X = 1\n')

    os.link(os.path.join(root, 'outside.py'), os.path.join(repo, 'linked.py'))
    code, out, rows = run(dict(spec, mutants=[{'name': 'linked', 'file': 'linked.py', 'edits': [['X = 1', 'X = 2']]}]))
    with open(os.path.join(root, 'outside.py')) as f:
        check('refuses a file with a second hard link, and writes nothing', code != 0 and 'hard link' in out
              and f.read() == 'X = 1\n')
    os.remove(os.path.join(repo, 'linked.py'))

    stub = os.path.join(root, 'stub-python')
    with open(stub, 'w') as f:
        f.write('#!/bin/sh\necho "$@" >> "$(dirname "$0")/stub-args"\nexit 0\n')
    os.chmod(stub, os.stat(stub).st_mode | stat.S_IEXEC)
    code, out, rows = run({'root': repo, 'python': stub, 'baseline': ['tests'], 'select': ['tests'], 'mutants': []})
    with open(os.path.join(root, 'stub-args')) as f:
        check('a spec with no runner key still runs pytest', code == 0 and f.read().startswith('-m pytest'))

    slow_mutant = {'name': 'slow', 'file': 'mod.py', 'edits': [['return a + b', 'return a - b']], 'select': ['tests/slow.py', '120']}
    path = os.path.join(root, 'spec-term.json')
    with open(path, 'w') as f:
        json.dump(dict(spec, mutants=[slow_mutant], timeout=300), f)
    for sig in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
        proc = subprocess.Popen([sys.executable, SCRIPT, path, '--out', os.path.join(root, 'out-term'), '--no-escalate'],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
        # A loaded machine can take a while to reach the mutant, so the wait is generous.
        seen, deadline = False, time.monotonic() + 90
        while time.monotonic() < deadline:
            with open(os.path.join(repo, 'mod.py')) as f:
                if 'a - b' in f.read():
                    seen = True
                    break
            time.sleep(0.05)
        proc.send_signal(sig)
        proc.wait(timeout=60)
        with open(os.path.join(repo, 'mod.py')) as f:
            check(f'{sig.name} during a mutant restores the file', seen and f.read() == MOD and proc.returncode == 128 + sig)

    code, out, rows = run(dict(spec, fail_pattern=r'add$'), '--only', 'add subtracts', '--no-escalate')
    check('reads failures with the spec\'s fail_pattern', rows[1]['status'] == 'red' and rows[1]['failed'] == ['add'])
    code, out, rows = run(dict(spec, mutants=spec['mutants'][:1], select=[['tests/near.py'], ['tests/far.py']]))
    check('runs every command of a selection and keeps each failure', code == 0
          and rows[1]['status'] == 'red' and rows[1]['failed'] == ['FAIL add'])

    code, out, rows = run(dict(spec, workers=4), '--no-escalate')
    check('says the script runner does not use workers', 'does not use them' in out)
    code, out, rows = run(dict(spec, runner='nose'))
    check('refuses an unknown runner', code != 0 and "runner must be 'pytest' or 'script'" in out)
    code, out, rows = run(dict(spec, select=[]))
    check('refuses an empty selection', code != 0 and 'names no command' in out)

# The signal functions run in a child, so the signals they ignore stay this process's own.
UNIT = '''import importlib.util, os, signal, sys
spec = importlib.util.spec_from_file_location('mutate', sys.argv[1])
mutate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mutate)
names = {s: s.name for s in mutate.STOP_SIGNALS}
print('stops', sorted(names.values()))
mutate.quiet_signals()
print('quiet', all(signal.getsignal(s) == signal.SIG_IGN for s in names))
for s in names:
    signal.signal(s, signal.SIG_DFL)
try:
    mutate.exit_on_signal(signal.SIGTERM, None)
except SystemExit as stop:
    print('exit', stop.code, all(signal.getsignal(s) == signal.SIG_IGN for s in names))
for s in names:
    signal.signal(s, signal.default_int_handler if s == signal.SIGINT else signal.SIG_DFL)
done = []
def restore():
    for s in names:
        os.kill(os.getpid(), s)
    done.append(True)
marker = lambda signum, frame: None
for s in names:
    signal.signal(s, marker)
mutate.finish(restore)
print('finish', done == [True])
print('handlers back', all(signal.getsignal(s) is marker for s in names))
def interrupted():
    raise SystemExit(143)
mutate.quiet_signals, done = interrupted, []
try:
    mutate.finish(lambda: done.append(True))
except SystemExit as stop:
    print('race', stop.code, done == [True])
'''
done = subprocess.run([sys.executable, '-c', UNIT, SCRIPT], capture_output=True, text=True)
lines = done.stdout.splitlines()
check('Ctrl-C, SIGTERM and SIGHUP are the stop signals', "stops ['SIGHUP', 'SIGINT', 'SIGTERM']" in lines)
check('quiet_signals ignores every stop signal', 'quiet True' in lines)
check('a stop signal exits with 128 plus its number and ignores the rest', 'exit 143 True' in lines)
check('no stop signal during the last restore can cut it short', 'finish True' in lines and 'KeyboardInterrupt' not in done.stderr)
check('the stop signals work again after the last restore', 'handlers back True' in lines)
check('a signal while the handlers are being switched still reaches the restore', 'race 143 True' in lines)
with open(SCRIPT) as f:
    source = f.read()
check("main's last restore runs through finish", 'finally:\n        finish(restore)\n' in source)

print('all passed' if not failures else f'{failures} failed')
sys.exit(1 if failures else 0)
