#!/usr/bin/env python3
"""Tests for the rewrite-calls skill's three scripts, on small files written to a temporary folder.

    python3 tests/test_rewrite_calls.py

Each check runs a script as the skill tells a session to, then reads the file it left.
"""
import ast, os, subprocess, sys, tempfile, textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, '..', 'skills', 'rewrite-calls', 'scripts')

failures = 0


def check(name, cond):
    global failures
    print(('ok   ' if cond else 'FAIL ') + name)
    failures += not cond


def run(script, *args, cwd=None):
    return subprocess.run([sys.executable, os.path.join(SCRIPTS, script), *args], capture_output=True, text=True,
                          cwd=cwd)


def write(path, text):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(textwrap.dedent(text).lstrip('\n'))


def read(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


def same_program(a, b):
    return ast.dump(ast.parse(a)) == ast.dump(ast.parse(b))


with tempfile.TemporaryDirectory() as root:
    path = os.path.join(root, 'mod.py')

    # rewrite_calls.py
    CALLS = '''
    class S:
        def run(self, name):
            self._alerts.alarm("disk full", code=3)
            self._alerts.alarm(
                f"restart of {name}",  # the supervisor's count
                code=4,
            )
            other.self._alerts.alarm("not a match")
            self._alerts.alarm_later("not a match either")
            x = "é"; self._alerts.alarm("after a two-byte letter")
    '''
    write(path, CALLS)
    before = read(path)
    done = run('rewrite_calls.py', 'self._alerts.alarm', '{func}(Alarm({args}))', path, '--check')
    check('rewrite --check exits 1 when calls would change', done.returncode == 1)
    check('rewrite --check prints a diff', '+        self._alerts.alarm(Alarm("disk full", code=3))' in done.stdout)
    check('rewrite --check writes nothing', read(path) == before)

    done = run('rewrite_calls.py', 'self._alerts.alarm', '{func}(Alarm({args}))', path)
    after = read(path)
    check('rewrite exits 0 and counts the calls', done.returncode == 0 and '3 calls rewritten' in done.stdout)
    check('rewrite wraps a one-line call', 'self._alerts.alarm(Alarm("disk full", code=3))' in after)
    check('rewrite keeps a comment between arguments',
          'Alarm(f"restart of {name}",  # the supervisor\'s count\n            code=4)' in after)
    check('rewrite leaves a call whose name only ends with the target', 'other.self._alerts.alarm("not a match")' in after)
    check('rewrite leaves a call whose last name differs', 'alarm_later("not a match either")' in after)
    check('rewrite finds a call after a non-ASCII letter on its line',
          'x = "é"; self._alerts.alarm(Alarm("after a two-byte letter"))' in after)

    write(path, 'log.warn("a", 1, level=2)\nlog.warn()\n')
    done = run('rewrite_calls.py', 'log.warn', 'log.warning({1}, {0}, lvl={level})', path)
    check('a missing field stops the run and names the call', done.returncode == 2 and 'line 2' in done.stderr)
    check('a stopped run writes nothing', read(path) == 'log.warn("a", 1, level=2)\nlog.warn()\n')

    write(path, 'log.warn("a", 1, level=2)\n')
    run('rewrite_calls.py', 'log.warn', 'log.warning({1}, {0}, lvl={level}, d={{}})', path)
    check('positional and keyword fields fill, and doubled braces stay literal',
          read(path) == 'log.warning(1, "a", lvl=2, d={})\n')

    write(path, 'f(1)\nf(2)\nf(3)\n')
    spec = os.path.join(root, 'spec.json')
    with open(spec, 'w') as f:
        f.write('["g({args})", null, "h({0}, {0})"]')
    done = run('rewrite_calls.py', 'f', '--spec', spec, path)
    check('a spec rewrites each call by its own entry and leaves a null', read(path) == 'g(1)\nf(2)\nh(3, 3)\n')
    write(path, 'f(1)\nf(2)\n')
    with open(spec, 'w') as f:
        f.write('["g({args})"]')
    done = run('rewrite_calls.py', 'f', '--spec', spec, path)
    check('a spec whose count differs stops the run', done.returncode == 2 and '1 entries' in done.stderr)

    write(path, 'f(f(1))\n')
    done = run('rewrite_calls.py', 'f', 'g({args})', path)
    check('a call inside a matching call stops the run', done.returncode == 2 and 'inside' in done.stderr)
    check('a nested-call refusal writes nothing', read(path) == 'f(f(1))\n')

    write(path, 'f(1)\n')
    done = run('rewrite_calls.py', 'f', 'g({args}', path)
    check('a rewrite that would not parse is refused', done.returncode == 2 and read(path) == 'f(1)\n')

    write(path, 'f(\n    1,  # why\n)\n')
    done = run('rewrite_calls.py', 'f', 'g({args})', path)
    check('a comment after the last argument stops the run rather than being dropped',
          done.returncode == 2 and 'line 2' in done.stderr and read(path) == 'f(\n    1,  # why\n)\n')
    done = run('rewrite_calls.py', 'f', 'g({call})', path)
    check('a template that keeps the whole call keeps the comment', '# why' in read(path))

    write(path, 'f(1)\nx.f(2)\n')
    done = run('rewrite_calls.py', 'f', '--list', path)
    check('--list numbers the matching calls', done.stdout == f'0: {path}:1: f(1)\n')

    write(path, 'g(1)\n')
    done = run('rewrite_calls.py', 'f', 'h({args})', path, '--check')
    check('rewrite --check exits 0 when nothing matches', done.returncode == 0 and done.stdout == '')

    # reflow_strings.py
    def reflow(src, *args):
        write(path, src)
        old = read(path)
        done = run('reflow_strings.py', path, '--line-length', '40', *args)
        return old, read(path), done

    old, new, done = reflow('''
    f(
        f"the job {name} failed after {count} tries"
    )
    ''')
    check('an f-string splits at a space next to a placeholder', new == textwrap.dedent('''\
    f(
        f"the job {name} failed after "
        f"{count} tries"
    )
    '''))
    check('the split keeps the program the same', same_program(old, new))

    old, new, done = reflow('''
    f(
        f"the job {name} did fail after many retries"
    )
    ''')
    check('a piece with no placeholder drops the f prefix', new == textwrap.dedent('''\
    f(
        f"the job {name} did fail after "
        "many retries"
    )
    '''))

    old, new, done = reflow('''
    f(
        f"result: {a if flag else b} and so on and so forth"
    )
    ''')
    check('a placeholder that holds spaces is never cut', '{a if flag else b}' in new and same_program(old, new))

    old, new, done = reflow('''
    f(
        f"a brace {{ and some words then {x}"
    )
    ''')
    check('a piece with only an escaped brace becomes a plain string with one brace',
          new == 'f(\n    "a brace { and some words then "\n    f"{x}"\n)\n' and same_program(old, new))

    old, new, done = reflow('''
    f(
        "short "
        "pieces "
        "that "
        f"{x} fit"
    )
    ''')
    check('a ragged run joins into as few lines as fit', new == 'f(\n    f"short pieces that {x} fit"\n)\n')

    old, new, done = reflow('''
    f(
        "plain {braces} "
        f"next to {x}"
    )
    ''')
    check('joining a plain piece with braces into an f-string keeps its text', same_program(old, new) and
          new == 'f(\n    f"plain {{braces}} next to {x}"\n)\n')

    old, new, done = reflow('''
    f(
        "a message long enough to need a split",  # note
        2,
    )
    ''')
    check('a trailing comma and comment stay on the last piece',
          '    "split",  # note\n' in new and same_program(old, new))
    check('every line but the commented one fits the length',
          all(len(line) <= 40 for line in new.splitlines() if '#' not in line))

    old, new, done = reflow('''
    def g():
        """
        "a docstring line that looks like a literal and runs long"
        """
    ''')
    check('a too-long line inside a docstring must not be split', new == old)
    check('the docstring line is reported as left alone', 'left as it was' in done.stderr)

    old, new, done = reflow('''
    "a statement that is one long string literal on its line"
    ''')
    check('a statement-level literal must not split into two statements', new == old)

    old, new, done = reflow('''
    f(
        "averyveryveryverylongsinglewordwithnospacesinitatall"
    )
    ''')
    check('a long literal with no space to cut at is left alone', new == old)

    old, new, done = reflow('''
    f(
        r"a raw string that runs long enough to need a split"
    )
    g(
        b"a bytes literal that runs long enough to need a split"
    )
    ''')
    check('raw and bytes literals are left alone', new == old)

    old, new, done = reflow('''
    f(
        "one "  # a comment in the middle
        "two "
        "three"
    )
    ''')
    check('a comment on a middle line ends the run', new.startswith('f(\n    "one "  # a comment in the middle\n'))

    old, new, done = reflow('''
    f(
        "short "
        "pieces"
    )
    ''', '--long-only')
    check('--long-only leaves a ragged run with no long line', new == old)

    write(path, 'f(\n    "short "\n    "pieces"\n)\n')
    done = run('reflow_strings.py', path, '--line-length', '40', '--check')
    check('reflow --check exits 1 and prints a diff', done.returncode == 1 and '+    "short pieces"' in done.stdout)
    check('reflow --check writes nothing', read(path) == 'f(\n    "short "\n    "pieces"\n)\n')

    with open(os.path.join(root, 'pyproject.toml'), 'w') as f:
        f.write('[project]\nname = "x"\n\n[tool.ruff]\nline-length = 30\n\n[tool.ruff.lint]\nselect = ["E"]\n')
    write(path, 'f(\n    "a string of thirty-five letters"\n)\n')
    done = run('reflow_strings.py', path)
    check('the line length comes from pyproject.toml', 'reflowed at 30 columns' in done.stdout and
          all(len(line) <= 30 for line in read(path).splitlines()))
    os.remove(os.path.join(root, 'pyproject.toml'))

    write(path, 'f(\n')
    done = run('reflow_strings.py', path)
    check('a file that does not parse is refused', done.returncode == 2)

    # check_strings.py
    repo = os.path.join(root, 'repo')
    os.makedirs(repo)
    git = ['git', '-C', repo, '-c', 'user.name=t', '-c', 'user.email=t@example.invalid']
    subprocess.run(git + ['init', '-q'], check=True)
    target = os.path.join(repo, 'mod.py')
    write(target, '"""Doc."""\nf(f"the job {name} failed after {count} tries", code=1)\n')
    subprocess.run(git + ['add', 'mod.py'], check=True)
    subprocess.run(git + ['commit', '-q', '-m', 'base'], check=True)

    write(target, '"""Doc."""\nf(\n    Alarm(\n        f"the job {name} failed after "\n        f"{count} tries",\n'
                  '        code=1,\n    )\n)\n')
    done = run('check_strings.py', 'mod.py', cwd=repo)
    check('a split and wrapped string passes the check', done.returncode == 0 and 'every string unchanged' in done.stdout)

    write(target, '"""Doc."""\nf(f"the job {name} failed after {count} retries", code=1)\n')
    done = run('check_strings.py', 'mod.py', cwd=repo)
    check('a changed word fails the check and shows both texts', done.returncode == 1 and 'gone 1x' in done.stdout
          and 'new 1x' in done.stdout)

    write(target, '"""Doc."""\nf(Alarm(f"the job {name} failed after {count} tries", key="job"), code=1)\n')
    done = run('check_strings.py', 'mod.py', cwd=repo)
    check('a string a template adds is listed and passes', done.returncode == 0 and "new 1x: 'job'" in done.stdout)

    write(os.path.join(repo, 'new.py'), 'x = 1\n')
    done = run('check_strings.py', 'new.py', cwd=repo)
    check('a file git does not know is skipped', done.returncode == 0 and 'skipped' in done.stdout)

sys.exit(1 if failures else 0)
