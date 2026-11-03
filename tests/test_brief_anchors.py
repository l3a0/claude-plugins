#!/usr/bin/env python3
"""Tests for skills/ask-team/scripts/brief_anchors.py against stand-in `gh` and `git` commands.

    python3 tests/test_brief_anchors.py

The stand-ins answer from environment variables, so the test needs no network and no GitHub login. The stand-in
`gh` gives the merge base and the base branch's tip different commits, so a script that read the wrong one fails.
Each stand-in also checks its arguments and fails on a call to the wrong repository, pull request, commit or
checkout, so a script that dropped `-R` or `-C` fails too.
"""
import os, stat, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, '..', 'skills', 'ask-team', 'scripts', 'brief_anchors.py')

GH = '''#!/bin/sh
case "$*" in
  "pr view 5 -R o/r "*|"pr view 6 -R o/s "*)
    echo "$5" > "$(dirname "$0")/last_repo"
    printf '{"headRefOid":"aaaaaaa1111","headRefName":"%s","baseRefName":"%s","state":"%s"}' \\
      "${STUB_HEAD_REF:-feat}" "${STUB_BASE:-main}" "${STUB_STATE:-OPEN}";;
  "api repos/$(cat "$(dirname "$0")/last_repo")/compare/${STUB_BASE:-main}...aaaaaaa1111 "*)
    case "$*" in *merge_base_commit*) echo "bbbbbbb2222";; *) echo "ddddddd3333";; esac;;
  *) echo "stand-in gh: unexpected call: $*" >&2; exit 1;;
esac
'''
GIT = '''#!/bin/sh
[ -n "$STUB_GIT_FAIL" ] && { echo "fatal: not a git repository" >&2; exit 128; }
[ "$*" = "-C ${STUB_CHECKOUT:-/co} rev-parse HEAD" ] || { echo "stand-in git: unexpected call: $*" >&2; exit 1; }
echo "${STUB_LOCAL:-aaaaaaa1111}"
'''

failures = 0


def check(name, cond):
    global failures
    print(('ok   ' if cond else 'FAIL ') + name)
    failures += not cond


def run(*specs, **env):
    full = dict(os.environ, PATH=BIN + os.pathsep + os.environ['PATH'], **env)
    done = subprocess.run([sys.executable, SCRIPT, *specs], capture_output=True, text=True, env=full)
    return done.returncode, done.stdout + done.stderr


with tempfile.TemporaryDirectory() as BIN:
    for name, body in (('gh', GH), ('git', GIT)):
        path = os.path.join(BIN, name)
        with open(path, 'w') as f:
            f.write(body)
        os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)

    code, out = run('o/r#5=/co')
    check('exits 0 on a good spec', code == 0)
    check('numbers the item and names the pull request', out.startswith('1. **o/r PR #5**'))
    check('head is the pull request head', 'head `aaaaaaa`' in out)
    check('base is the merge base, not the base tip', 'base `bbbbbbb`' in out and 'ddddddd' not in out)
    check('diff runs from base to head', 'Diff: `git diff bbbbbbb aaaaaaa`' in out)
    check('names the checkout and branch', 'Checkout: `/co` (branch `feat`)' in out)
    check('no flag when the checkout is at the head', 'Update it first' not in out and 'State:' not in out)

    code, out = run('o/r#5=/co', STUB_LOCAL='ccccccc4444')
    check('flags a checkout not at the head', 'Checkout HEAD is `ccccccc`, not the head' in out)

    code, out = run('o/r#5', STUB_STATE='MERGED')
    check('flags a pull request that is not open', '**State: MERGED.**' in out)
    check('says when no checkout is given', 'no checkout given' in out)

    code, out = run('o/r#5', STUB_STATE='CLOSED')
    check('flags a pull request closed without merging', '**State: CLOSED.**' in out)

    code, out = run('o/r#5=/co')
    check('leaves the placeholder for what it changes', '<What it changes.>' in out)

    code, out = run('o/r#5=/elsewhere', STUB_CHECKOUT='/elsewhere')
    check('reads the checkout it was given', code == 0 and 'Checkout: `/elsewhere`' in out)

    code, out = run('o/r#5', STUB_HEAD_REF='x`<!--hidden-->')
    check('flags a branch name that could break its code span', 'unusual branch name' in out
          and '`x`<!--' not in out)

    code, out = run('o/r#5', STUB_BASE='release')
    check('names the real base branch', 'on `release`' in out)

    code, out = run('o/r#5', 'o/s#6')
    check('numbers each pull request and reads each repository', code == 0 and '\n2. **o/s PR #6**' in out)

    code, out = run('o/r#5=/tmp', STUB_GIT_FAIL='1')
    check('a checkout that is not a repository exits with one line', code != 0 and 'Traceback' not in out
          and 'not a git repository' in out)

    code, out = run('not-a-spec')
    check('a malformed spec exits non-zero', code != 0 and 'not OWNER/REPO#N' in out)

    code, out = run('o/r#5x')
    check('a spec with trailing text exits non-zero', code != 0 and 'not OWNER/REPO#N' in out)

    code, out = run()
    check('no arguments exits non-zero with the usage', code != 0 and 'Usage:' in out)

print('all passed' if not failures else f'{failures} failed')
sys.exit(1 if failures else 0)
