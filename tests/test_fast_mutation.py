#!/usr/bin/env python3
"""Tests for skills/fast-mutation/scripts/mutate.py's script runner, on a repository it builds in a temporary folder.

    python3 tests/test_fast_mutation.py

The pytest runner and its coverage map need pytest, which CI does not install, so only the script runner is tested.
"""
import json, os, subprocess, sys, tempfile

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

with tempfile.TemporaryDirectory() as root:
    repo = os.path.join(root, 'repo')
    os.makedirs(os.path.join(repo, 'tests'))
    for path, text in (('mod.py', MOD), ('tests/near.py', NEAR), ('tests/far.py', FAR), ('tests/crash.py', CRASH)):
        with open(os.path.join(repo, path), 'w') as f:
            f.write(text)
    subprocess.run(['git', '-C', repo, 'init', '-q'], check=True)

    def run(spec, *args):
        path = os.path.join(root, 'spec.json')
        with open(path, 'w') as f:
            json.dump(spec, f)
        out = os.path.join(root, 'out')
        done = subprocess.run([sys.executable, SCRIPT, path, '--out', out, *args], capture_output=True, text=True)
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
    check('reads a green baseline of two commands', 'BASE green' in out and by['BASE']['status'] == 'green')
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

print('all passed' if not failures else f'{failures} failed')
sys.exit(1 if failures else 0)
