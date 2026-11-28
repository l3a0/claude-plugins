#!/usr/bin/env python3
"""Tests for the rewrite-calls skill's three scripts, on small files written to a temporary folder.

    python3 tests/test_rewrite_calls.py

Each check runs a script as the skill tells a session to, then reads the file it left. The scripts need
Python 3.12 or later, so on an older interpreter run it with `uv run --no-project --python '>=3.12' python`.
"""
import ast, os, subprocess, sys, tempfile, textwrap

if sys.version_info < (3, 12):
    print('FAIL the rewrite-calls scripts need Python 3.12 or later, and this is '
          f'{sys.version_info.major}.{sys.version_info.minor}')
    sys.exit(1)

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

    write(path, 'f(1)\n')
    done = run('rewrite_calls.py', 'f', 'g({sev})', path)
    check('a missing keyword field stops the run', done.returncode == 2 and '{sev}' in done.stderr
          and read(path) == 'f(1)\n')

    other = os.path.join(root, 'other.py')
    write(path, 'f(1, sev=2)\n')
    write(other, 'f(1)\n')
    done = run('rewrite_calls.py', 'f', 'g({0}, {sev})', path, other)
    check('a refusal in a later file writes no earlier file', done.returncode == 2 and read(path) == 'f(1, sev=2)\n'
          and 'no file was written' in done.stderr)

    for name in ('call', 'func', 'args'):
        write(path, f'f(1, {name}=2)\n')
        done = run('rewrite_calls.py', 'f', 'g({args})', path)
        check(f'a keyword named {name} stops the run', done.returncode == 2 and read(path) == f'f(1, {name}=2)\n')

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
    check('a spec with too few entries stops the run', done.returncode == 2 and '1 entries' in done.stderr)
    with open(spec, 'w') as f:
        f.write('["g({args})", null, null]')
    done = run('rewrite_calls.py', 'f', '--spec', spec, path)
    check('a spec with too many entries stops the run', done.returncode == 2 and '3 entries' in done.stderr)
    done = run('rewrite_calls.py', 'f', '--spec', spec, path, other)
    check('a spec given two files stops the run', done.returncode == 2 and read(path) == 'f(1)\nf(2)\n')
    with open(spec, 'w') as f:
        f.write('{"0": "g({args})"}')
    done = run('rewrite_calls.py', 'f', '--spec', spec, path)
    check('a spec that is not a list stops the run', done.returncode == 2 and read(path) == 'f(1)\nf(2)\n')

    write(path, 'if x:\n    f(1)\nf(2)\n')
    done = run('rewrite_calls.py', 'f', '--list', path)
    check('--list numbers calls in source order whatever their depth',
          done.stdout == f'0: {path}:2: f(1)\n1: {path}:3: f(2)\n')
    with open(spec, 'w') as f:
        f.write('[null, "g({args})"]')
    run('rewrite_calls.py', 'f', '--spec', spec, path)
    check('a spec entry rewrites the call in that source position', read(path) == 'if x:\n    f(1)\ng(2)\n')

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
    done = run('rewrite_calls.py', 'f', 'g({args})  # was {{call}}', path)
    check('an escaped {call} in a template does not keep the comment', done.returncode == 2)
    done = run('rewrite_calls.py', 'f', 'g({call})', path)
    check('a template that keeps the whole call keeps the comment',
          done.returncode == 0 and read(path) == 'g(f(\n    1,  # why\n))\n')

    write(path, 'f(  # why\n    1,\n)\n')
    done = run('rewrite_calls.py', 'f', 'g({args})', path)
    check('a comment before the first argument stops the run', done.returncode == 2 and 'line 1' in done.stderr
          and read(path) == 'f(  # why\n    1,\n)\n')

    write(path, 'f(\n    "a",  # why\n    code=3,\n)\n')
    done = run('rewrite_calls.py', 'f', 'g({0}, code={code})', path)
    check('a comment between arguments that only {args} carries stops a {0} template', done.returncode == 2)

    with open(path, 'w', encoding='utf-8') as f:  # not write(), whose dedent can drop a line holding only a form feed
        f.write('x = 1\n\x0c\nf(1)\nf(2)\n')
    done = run('rewrite_calls.py', 'f', '--list', path)
    check('a form feed does not shift line numbers', done.stdout == f'0: {path}:3: f(1)\n1: {path}:4: f(2)\n')
    done = run('rewrite_calls.py', 'f', 'g({args})', path)
    check('a form feed does not shift a rewrite', done.returncode == 0 and read(path) == 'x = 1\n\x0c\ng(1)\ng(2)\n')

    write(path, 'f(\n  1)\nf(2\n')
    done = run('rewrite_calls.py', 'f', 'g({args})', path, '--check')
    check('an unclosed bracket exits 2 rather than reading as a change', done.returncode == 2
          and 'Traceback' not in done.stderr)

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
    check('a placeholder that holds spaces is kept whole', '{a if flag else b}' in new and same_program(old, new))

    old, new, done = reflow('''
    f(
        f"some words here then {a if flag else b} end"
    )
    ''')
    check('a break that would fall inside a placeholder moves before it',
          new == 'f(\n    "some words here then "\n    f"{a if flag else b} end"\n)\n')

    old, new, done = reflow('''
    f(
        f"a brace {{ and some words then {x}"
    )
    ''')
    check('a piece with only an escaped brace becomes a plain string with one brace',
          new == 'f(\n    "a brace { and some words then "\n    f"{x}"\n)\n' and same_program(old, new))

    old, new, done = reflow('''
    f(
        f"{x} with several more words of text }} end"
    )
    ''')
    check('a piece with only an escaped closing brace becomes a plain string with one brace',
          new == 'f(\n    f"{x} with several more words of "\n    "text } end"\n)\n' and same_program(old, new))

    old, new, done = reflow('''
    f(
        "short "
        "pieces "
        "that "
        f"{x} fit"
    )
    ''')
    check('by default a ragged run with no long line is left alone', new == old)
    old, new, done = reflow('''
    f(
        "short "
        "pieces "
        "that "
        f"{x} fit"
    )
    ''', '--ragged')
    check('--ragged joins a ragged run into as few lines as fit', new == 'f(\n    f"short pieces that {x} fit"\n)\n')

    old, new, done = reflow('''
    f(
        "a a a a a a a a a a a a a a a a "
        "ab"
    )
    ''', '--ragged')
    check('a joined line exactly at the length stays one line', new == 'f(\n    "a a a a a a a a a a a a a a a a ab"\n)\n')
    old, new, done = reflow('''
    f(
        "a a a a a a a a a a a a a a a a "
        "abc"
    )
    ''', '--ragged')
    check('a joined line one past the length splits', new == old)
    old, new, done = reflow('''
    f(
        "a a a a a a a a a a a a a a a a ab"
        "cd"
    )
    ''')
    check('by default a run whose longest line is exactly the length is left alone', new == old)

    old, new, done = reflow('''
    f(g(
        "aaaa bbbb cccc dddd eeee ffff g h"))
    ''')
    check('the closing brackets count toward the last line', all(len(line) <= 40 for line in new.splitlines())
          and new != old and same_program(old, new))

    old, new, done = reflow('''
    x = \\
        "a long string that needs splitting here"
    ''')
    check('a split that would stop the file parsing is left alone', new == old and 'left as it was' in done.stderr)

    old, new, done = reflow('''
    f(
        "plain {braces} "
        f"next to {x}"
    )
    ''', '--ragged')
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
    ''', '--ragged')
    check('a comment on a middle line ends the run', new.startswith('f(\n    "one "  # a comment in the middle\n'))

    old, new, done = reflow('''
    f(
        "a string long enough to split",  # noqa: E501
    )
    # fmt: off
    g(
        "a string long enough to split here too"
    )
    # fmt: on
    ''')
    check('a noqa line and a fmt: off region are left alone', new == old)

    old, new, done = reflow('f(\n\t"a tab-indented string of thirty-eight"\n)\n')
    check('a tab counts as four columns', new != old and all(len(line.expandtabs(4)) <= 40 for line in new.splitlines()))

    write(path, 'f(\n    "short "\n    "pieces"\n)\n')
    done = run('reflow_strings.py', path, '--line-length', '40', '--check', '--ragged')
    check('reflow --check exits 1 and prints a diff', done.returncode == 1 and '+    "short pieces"' in done.stdout)
    check('reflow --check writes nothing', read(path) == 'f(\n    "short "\n    "pieces"\n)\n')

    with open(os.path.join(root, 'pyproject.toml'), 'w') as f:
        f.write('[project]\nname = "x"\n\n[tool.ruff]\nline-length = 30\n\n[tool.ruff.lint]\nselect = ["E"]\n')
    write(path, 'f(\n    "a string of thirty-five letters"\n)\n')
    done = run('reflow_strings.py', path)
    check('the line length comes from pyproject.toml', 'reflowed at 30 columns' in done.stdout and
          all(len(line) <= 30 for line in read(path).splitlines()))
    with open(os.path.join(root, 'pyproject.toml'), 'w') as f:
        f.write('[tool.black]\nline-length = 30\n\n[tool.ruff.lint]\nselect = ["E"]\n')
    write(path, 'f(\n    "a string of thirty-five letters"\n)\n')
    done = run('reflow_strings.py', path)
    check("only pyproject's own [tool.ruff] table sets the length", read(path) == 'f(\n    "a string of thirty-five letters"\n)\n')
    with open(os.path.join(root, 'ruff.toml'), 'w') as f:
        f.write('line-length = 30\n')
    done = run('reflow_strings.py', path)
    check('ruff.toml is read, and beats pyproject.toml in its folder', 'reflowed at 30 columns' in done.stdout)
    write(path, 'f(\n    "a string of thirty-five letters"\n)\n')
    with open(os.path.join(root, '.ruff.toml'), 'w') as f:
        f.write('line-length = 120\n')
    done = run('reflow_strings.py', path)
    check('.ruff.toml beats ruff.toml', read(path) == 'f(\n    "a string of thirty-five letters"\n)\n')
    for name in ('pyproject.toml', 'ruff.toml', '.ruff.toml'):
        os.remove(os.path.join(root, name))
    deep = os.path.join(root, 'deep')
    os.makedirs(deep)
    with open(os.path.join(root, 'ruff.toml'), 'w') as f:
        f.write('line-length = 30\n')
    with open(os.path.join(deep, 'ruff.toml'), 'w') as f:
        f.write('[lint]\nselect = ["E"]\n')
    deep_file = os.path.join(deep, 'm.py')
    write(deep_file, 'f(\n    "a string of thirty-five letters"\n)\n')
    done = run('reflow_strings.py', deep_file, '--check')
    check('the closest config wins even when it sets no length, as in ruff', done.returncode == 0)
    os.remove(os.path.join(root, 'ruff.toml'))

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

    write(target, '"""Doc."""\nf(f"the job {name} failed after {count} retries", code=1)\n')
    done = run('check_strings.py', target, cwd=root)
    check('an absolute path from outside the repository is compared', done.returncode == 1 and 'gone 1x' in done.stdout)
    done = run('check_strings.py', 'mod.py', '--ref', 'mian', cwd=repo)
    check('a ref that names no commit stops the run', done.returncode == 2 and 'mian' in done.stderr)
    done = run('check_strings.py', '--ref=--output=x', 'mod.py', cwd=repo)
    check('a ref that starts with a dash is refused', done.returncode == 2 and not os.path.exists(os.path.join(repo, 'x')))
    loose = os.path.join(root, 'loose.py')
    write(loose, 'x = "a"\n')
    done = run('check_strings.py', loose, cwd=root)
    check('a file outside any git work tree stops the run', done.returncode == 2)

    write(target, '"""Doc."""\nf("failed")\nf("failed")\ng(f"job {count} done")\n')
    subprocess.run(git + ['commit', '-q', '-am', 'second'], check=True)
    write(target, '"""Doc."""\nf("failed")\ng(f"job {count} done")\n')
    done = run('check_strings.py', 'mod.py', cwd=repo)
    check('a string that appeared twice and now once fails', done.returncode == 1 and "gone 1x: 'failed'" in done.stdout)
    write(target, '"""Doc."""\nf("failed")\nf("failed")\ng(f"job {cnt} done")\n')
    done = run('check_strings.py', 'mod.py', cwd=repo)
    check('a changed placeholder fails', done.returncode == 1 and 'gone 1x' in done.stdout)
    write(target, '"""Docs."""\nf("failed")\nf("failed")\ng(f"job {count} done")\n')
    done = run('check_strings.py', 'mod.py', cwd=repo)
    check('a changed docstring fails', done.returncode == 1 and "gone 1x: 'Doc.'" in done.stdout)
    write(target, '"""Doc."""\nf("failed")\nf("failed")\ng(f"job {count} done")\n')
    done = run('check_strings.py', 'mod.py', '--ref', 'HEAD~1', cwd=repo)
    check('--ref compares against that commit', done.returncode == 1 and 'gone 1x' in done.stdout)
    done = run('check_strings.py', 'mod.py', cwd=repo)
    check('the file as committed passes against HEAD', done.returncode == 0)

sys.exit(1 if failures else 0)
