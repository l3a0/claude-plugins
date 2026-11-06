#!/usr/bin/env python3
"""Tests for skills/ask-team/scripts/removed_text.py on real git repositories it builds in a temporary folder.

    python3 tests/test_removed_text.py
"""
import os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, '..', 'skills', 'ask-team', 'scripts', 'removed_text.py')

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
        with open(os.path.join(repo, path), 'w') as f:
            f.write(text)
    git(repo, 'add', '-A')
    git(repo, 'commit', '-qm', 'c')
    return subprocess.run(['git', '-C', repo, 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()


def repo(root, name, files):
    path = os.path.join(root, name)
    os.mkdir(path)
    git(path, 'init', '-q')
    return path, commit(path, files)


def run(*args):
    done = subprocess.run([sys.executable, '-I', SCRIPT, *args], capture_output=True, text=True)
    return done.returncode, done.stdout, done.stderr


CUT = 'The input check refuses only an order that adds.'
STAY = 'Every order passes the gate before it goes out.'

with tempfile.TemporaryDirectory() as root:
    design, d1 = repo(root, 'design', {'design.md': f'{STAY} {CUT}\n'})
    plugin, p1 = repo(root, 'plugin', {
        'gen.py': 'LINE = "The input check refuses only\n    an order that adds."\n',
        'agent.md': f'{CUT}\n',
        'other.md': 'Nothing here is related.\n',
        'logo.png': f'{CUT}\n',
    })
    d2 = commit(design, {'design.md': f'{STAY}\n'})

    code, out, _ = run(f'{design}={d1}..{d2}', f'{plugin}={p1}..{p1}')
    check('exits 0 with a sentence left behind', code == 0)
    check('prints the removed run under its file', f'- design.md: {CUT}' in out)
    check('counts the runs', '1 removed run(s)' in out and '0 removed run(s)' in out)
    check('finds the copy left in a companion', f'still in {plugin}: agent.md:1' in out)
    check('finds a copy wrapped across lines, at its first line', f'still in {plugin}: gen.py:1' in out)
    check('names every file that holds a copy', out.count('still in') == 2)
    check('skips a file that is not text', 'logo.png' not in out)
    check('does not name an unrelated file', 'other.md' not in out)
    check('does not say the sentence stands where it was cut', f'still in {design}' not in out)

    p2 = commit(plugin, {'agent.md': 'Gone.\n', 'gen.py': 'LINE = "Gone."\n', 'logo.png': 'Gone.\n'})
    code, out, _ = run(f'{design}={d1}..{d2}', f'{plugin}={p1}..{p2}')
    check('reports nothing left once both are cut', 'still in' not in out and '- agent.md:' in out)

    code, out, _ = run('--min-words', '4', f'{plugin}={p1}..{p2}')
    check('a shorter window still works', code == 0 and '- agent.md:' in out)
    code, out, _ = run('--min-words', '99', f'{design}={d1}..{d2}')
    check('a run under the minimum is not listed', '0 removed run(s)' in out)

    d3 = commit(design, {'design.md': f'{STAY}\none two three\nfour five six\nseven\n'})
    d4 = commit(design, {'design.md': f'{STAY}\nseven\n'})
    code, out, _ = run(f'{design}={d3}..{d4}')
    check('a run carries across a line end', '- design.md: one two three four five six' in out)

    d5 = commit(design, {'design.md': f'{STAY}\n-- a line that reads like a header here\nseven\n'})
    d6 = commit(design, {'design.md': f'{STAY}\nseven\n'})
    code, out, _ = run(f'{design}={d5}..{d6}')
    check('a removed line that reads like a header stays text', '- design.md: -- a line that reads like a header' in out)

    code, out, _ = run('--min-words', '1', f'{design}={d5}..{d6}')
    check('a diff header is not a removed run', 'a/design.md' not in out and 'b/design.md' not in out)

    d7 = commit(design, {'design.md': 'alpha beta gamma delta epsilon\nkept words stay here now\nzeta eta theta iota kappa\n'})
    d8 = commit(design, {'design.md': 'kept words stay here now\n'})
    code, out, _ = run(f'{design}={d7}..{d8}')
    check('kept text between two cuts splits them into two runs', '2 removed run(s)' in out)

    d9 = commit(design, {'design.md': 'alpha beta gamma delta epsilon kept words stay zeta eta theta iota kappa\n'})
    d10 = commit(design, {'design.md': 'kept words stay\n'})
    code, out, _ = run(f'{design}={d9}..{d10}')
    check('kept words on one line split two cuts into two runs', '2 removed run(s)' in out)

    upper, u1 = repo(root, 'upper', {'agent.md': 'THE INPUT CHECK REFUSES ONLY AN ORDER THAT ADDS.\n'})
    code, out, _ = run(f'{design}={d1}..{d2}', f'{upper}={u1}..{u1}')
    check('a copy in another case still matches', f'still in {upper}: agent.md:1' in out)

    a, a1 = repo(root, 'a', {'cut.md': 'one two three four five\n', 'near.md': 'six seven eight nine\n', 'keep.md': 'x\n'})
    b, b1 = repo(root, 'b', {'copy.md': 'one two three four five\n', 'near.md': 'six seven eight nine\n'})
    a2 = commit(a, {'cut.md': 'x\n', 'near.md': 'x\n'})
    code, out, _ = run(f'{a}={a1}..{a2}', f'{b}={b1}..{b1}')
    check('a run of exactly the minimum is listed and found', '- cut.md: one two three four five' in out
          and f'still in {b}: copy.md:1' in out)
    check('a run one word short of the minimum is not listed', '- near.md' not in out)

    r, r1 = repo(root, 'r', {'old.md': 'alpha beta gamma delta epsilon zeta\n'})
    git(r, 'mv', 'old.md', 'new.md')
    r2 = commit(r, {})
    code, out, _ = run(f'{r}={r1}..{r2}')
    check('a renamed file shows as removed and still in its new name', '- old.md: alpha beta' in out
          and f'still in {r}: new.md:1' in out)

    u, u1 = repo(root, 'u', {'ü file.md': 'alpha beta gamma delta epsilon zeta\n'})
    u2 = commit(u, {'ü file.md': 'x\n'})
    code, out, _ = run(f'{u}={u1}..{u2}')
    check('a path with a space and a non-ASCII letter prints as it is', '- ü file.md: alpha beta' in out)

    n, n1 = repo(root, 'n', {'bin.py': 'x\0y alpha beta gamma delta epsilon\n', 'cut.md': 'alpha beta gamma delta epsilon\n'})
    n2 = commit(n, {'cut.md': 'x\n'})
    code, out, _ = run(f'{n}={n1}..{n2}')
    check('a file holding a NUL is not searched, whatever its name', 'bin.py' not in out and '- cut.md' in out)

    git(design, 'branch', 'feature', d5)
    code, out, _ = run(f'{design}=feature..{d6}')
    check('takes a branch name as a commit', code == 0 and 'feature..' in out)

    code, _, err = run(f'{design}={d1}')
    check('refuses an argument with no range', code != 0 and 'CHECKOUT=FROM..TO' in err)
    code, _, err = run(f'{design}={d1}...{d2}')
    check('refuses a three-dot range', code != 0 and 'CHECKOUT=FROM..TO' in err)
    code, _, err = run('--min-words', '0', f'{design}={d1}..{d2}')
    check('refuses a minimum of zero', code != 0 and 'at least 1' in err)
    code, _, err = run(f'{design}={d1}..nosuchcommit')
    check('stops on an unknown commit', code != 0 and 'failed' in err)

print('all passed' if not failures else f'{failures} failed')
sys.exit(bool(failures))
