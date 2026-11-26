#!/usr/bin/env python3
"""Tests for skills/ask-team/scripts/removed_tests.py on real git repositories it builds in a temporary folder.

    python3 tests/test_removed_tests.py
"""
import os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, '..', 'skills', 'ask-team', 'scripts', 'removed_tests.py')

failures = 0


def check(name, cond):
    global failures
    print(('ok   ' if cond else 'FAIL ') + name)
    failures += not cond


def git(repo, *args):
    subprocess.run(['git', '-C', repo, '-c', 'user.name=t', '-c', 'user.email=t@example.com', *args], check=True,
                   capture_output=True)


def commit(repo, files):
    for path, text in files.items():
        full = os.path.join(repo, path)
        if text is None:
            os.remove(full)
            continue
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, 'w') as f:
            f.write(text)
    git(repo, 'add', '-A')
    git(repo, 'commit', '-qm', 'c')
    return subprocess.run(['git', '-C', repo, 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()


def run(*args):
    done = subprocess.run([sys.executable, '-I', SCRIPT, *args], capture_output=True, text=True)
    return done.returncode, done.stdout + done.stderr


A = '''import pytest


def test_kept():
    pass


async def test_async_cut():
    pass


class TestGroup:
    def test_method_cut(self):
        pass

    def test_twice(self):
        pass


def test_multi_line(
    x,
):
    pass


def helper_test_not_a_test():
    pass
'''
B = 'def test_twice():\n    pass\n\ndef test_moved():\n    pass\n'

with tempfile.TemporaryDirectory() as root:
    repo = os.path.join(root, 'repo')
    os.mkdir(repo)
    git(repo, 'init', '-q')
    c1 = commit(repo, {'tests/test_a.py': A, 'tests/test_b.py': B, 'tests/notes.md': 'def test_in_markdown():\n',
                       'src/test_outside.py': 'def test_outside():\n    pass\n'})

    code, out = run(f'{repo}={c1}..{c1}')
    check('exits 0 with nothing gone', code == 0 and '0 test name(s) gone' in out)

    c2 = commit(repo, {
        'tests/test_a.py': A.replace('async def test_async_cut', 'async def kept_async')
                            .replace('def test_method_cut', 'def method_kept')
                            .replace('    def test_twice(self):\n        pass\n', '')
                            .replace('def test_multi_line(', 'def renamed_multi_line('),
        'tests/test_b.py': B.replace('def test_moved():\n    pass\n', ''),
        'tests/test_c.py': 'def test_moved():\n    pass\n',
        'tests/notes.md': None,
        'src/test_outside.py': None,
    })
    code, out = run(f'{repo}={c1}..{c2}')
    check('exits 0 with tests gone', code == 0)
    check('counts the names gone', '4 test name(s) gone' in out)
    check('finds an async test cut', '- test_async_cut: was in tests/test_a.py; now in no file' in out)
    check('finds a method cut from a class', '- test_method_cut: was in tests/test_a.py' in out)
    check('finds a definition split over lines', '- test_multi_line:' in out)
    check('finds one of two definitions of a name cut, and says where the other is',
          '- test_twice: was in tests/test_a.py, tests/test_b.py; now in tests/test_b.py' in out)
    check('does not count a test moved to another file', 'test_moved' not in out)
    check('does not count a test kept', 'test_kept' not in out)
    check('does not count a function whose name does not start with test', 'helper_test' not in out)
    check('reads only .py files', 'test_in_markdown' not in out)
    check('reads only the tests folder by default', 'test_outside' not in out)

    code, out = run('--path', 'src', f'{repo}={c1}..{c2}')
    check('--path reads another folder', '1 test name(s) gone' in out and '- test_outside: was in src/test_outside.py' in out)
    code, out = run('--path', 'src', '--path', 'tests', f'{repo}={c1}..{c2}')
    check('--path repeats', '5 test name(s) gone' in out)

    code, out = run(f'{repo}=HEAD~1..HEAD')
    check('takes refs as well as hashes', code == 0 and '4 test name(s) gone' in out)

    code, out = run(f'{repo}={c2}..{c1}')
    check('a range read backwards lists nothing it added', '0 test name(s) gone' in out)

    other = os.path.join(root, 'other')
    os.mkdir(other)
    git(other, 'init', '-q')
    o1 = commit(other, {'tests/test_x.py': 'def test_x():\n    pass\n'})
    o2 = commit(other, {'tests/test_x.py': None, 'README.md': 'gone\n'})
    code, out = run(f'{repo}={c1}..{c2}', f'{other}={o1}..{o2}')
    check('reads each checkout it is given', f'{other} {o1}..{o2}: 1 test name(s) gone' in out
          and '- test_x: was in tests/test_x.py; now in no file' in out and '4 test name(s) gone' in out)

    code, out = run('--path', 'missing', f'{repo}={c1}..{c2}')
    check('stops on a folder FROM does not hold', code != 0 and 'holds nothing at missing' in out)
    code, out = run(f'{repo}=nosuch..{c2}')
    check('stops on a name that is not a commit', code != 0 and 'nosuch is not a commit' in out and 'Traceback' not in out)
    code, out = run(f'{repo}')
    check('stops on a malformed range', code != 0 and 'not CHECKOUT=FROM..TO' in out)
    code, out = run(f'{root}/nowhere={c1}..{c2}')
    check('stops on a checkout that is not a repository', code != 0 and 'Traceback' not in out)

print('all passed' if not failures else f'{failures} failed')
sys.exit(1 if failures else 0)
