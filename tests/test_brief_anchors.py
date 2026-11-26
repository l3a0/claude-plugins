#!/usr/bin/env python3
"""Tests for skills/ask-team/scripts/brief_anchors.py against stand-in `gh` and `git` commands.

    python3 tests/test_brief_anchors.py

The stand-ins answer from environment variables, so the test needs no network and no GitHub login. The stand-in
`gh` gives the merge base and the base branch's tip different commits, so a script that read the wrong one fails.
The `--next` cases write a round 1 brief from the script's own items, then write later rounds from it.
Each stand-in also checks its arguments and fails on a call to the wrong repository, pull request, commit or
checkout, so a script that dropped `-R` or `-C` fails too.
"""
import os, stat, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, '..', 'skills', 'ask-team', 'scripts', 'brief_anchors.py')

GH = '''#!/bin/sh
d="$(dirname "$0")"
case "$*" in
  "pr view 5 -R o/r "*|"pr view 6 -R o/s "*)
    echo "$5" > "$d/last_repo"
    if [ "$5" = o/s ]; then sha="${STUB_SHA_S:-${STUB_SHA:-aaaaaaa1111}}"; else sha="${STUB_SHA:-aaaaaaa1111}"; fi
    echo "$sha" > "$d/last_sha"
    printf '{"headRefOid":"%s","headRefName":"%s","baseRefName":"%s","state":"%s"}' \\
      "$sha" "${STUB_HEAD_REF:-feat}" "${STUB_BASE:-main}" "${STUB_STATE:-OPEN}";;
  "api repos/$(cat "$d/last_repo")/compare/${STUB_BASE:-main}...$(cat "$d/last_sha") "*)
    case "$*" in *merge_base_commit*) echo "${STUB_MB:-bbbbbbb2222}";; *) echo "ddddddd3333";; esac;;
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

    code, out = run('o/r#5=/co')
    check('puts the placeholder in a paragraph of its own under the item', 'aaaaaaa`.\n\n   <What it changes.>' in out)

    # --next: write round 1's brief from the script's own items, then the later rounds from it.
    SCRATCH = os.path.join(BIN, 'scratch')
    os.mkdir(SCRATCH)

    def brief(name, text):
        path = os.path.join(SCRATCH, name)
        with open(path, 'w') as f:
            f.write(text)
        return path

    def read(path):
        with open(path) as f:
            return f.read()

    def nxt(prev, out, *heads, **env):
        return run('--next', prev, '--out', os.path.join(SCRATCH, out), *heads, **env)

    code, items = run('o/r#5=/co')
    items = items.strip().replace('<What it changes.>', 'Changes `order_path.py`, round one.')
    LIMITS = '- Mutate only a copy taken with `git -C <checkout> archive aaaaaaa | tar -x -C <your scratch folder>`.'
    R1 = (f'# Review brief: settle an order, round 1\n\n## Subject and anchors\n\n{items}\n\n'
          'Review the head commit named here, not the branch tip.\n\n'
          'The path to an irreversible action: none in this subject.\n\n'
          f'## Limits for every agent in the round\n\n{LIMITS}\n')
    r1 = brief('r1.md', R1)

    code, out = nxt(r1, 'r2.md', 'eeeeeee5555', STUB_SHA='eeeeeee5555', STUB_LOCAL='eeeeeee5555')
    r2 = read(os.path.join(SCRATCH, 'r2.md')) if code == 0 else ''
    check('--next exits 0 and says where it wrote', code == 0 and 'r2.md' in out)
    check('--next bumps the round in the title', r2.startswith('# Review brief: settle an order, round 2\n'))
    check('--next moves the item to the new head', '1. **o/r PR #5**, head `eeeeeee`' in r2 and 'head `aaaaaaa`' not in r2)
    check('--next lists the round just finished as an earlier anchor', 'Earlier rounds read round 1 `aaaaaaa`.\n' in r2)
    check('--next keeps the diff from the merge base to the new head', 'Diff: `git diff bbbbbbb eeeeeee`.' in r2)
    check('--next keeps what the session wrote about the change', '   Changes `order_path.py`, round one.' in r2)
    check('--next moves the archive line to the new head', 'archive eeeeeee | tar' in r2 and 'archive aaaaaaa' not in r2)
    check('--next adds the blank for what the round reads, after the items',
          '`order_path.py`, round one.\n\n<This round reads round 1\'s fixes: `git -C /co diff aaaaaaa eeeeeee` '
          'on o/r PR #5,' in r2 and r2.index('<This round reads') < r2.index('Review the head commit'))
    check('--next leaves every other line as it was',
          [line for line in R1.split('\n') if line not in r2.split('\n')]
          == [R1.split('\n')[0], items.split('\n')[0], LIMITS])

    R2 = r2.replace(r2[r2.index('<This round reads'):r2.index('\n\nReview the head')],
                    'This round reads round 1\'s fixes, `git diff aaaaaaa eeeeeee`,\n'
                    'and the passage `archive aaaaaaa` named, over two lines.')
    R2 = R2.replace('none in this subject.', 'none in this subject. The risk engineer reads it at `eeeeeee`.')
    r2 = brief('r2-filled.md', R2)
    code, out = nxt(r2, 'r3.md', 'o/r#5=fffffff6666', STUB_SHA='fffffff6666', STUB_LOCAL='fffffff6666',
                    STUB_MB='9999999aaaa')
    r3 = read(os.path.join(SCRATCH, 'r3.md')) if code == 0 else ''
    check('--next takes OWNER/REPO#N=HEAD', code == 0 and 'round 3\n' in r3)
    check('--next grows the list of earlier anchors', 'Earlier rounds read round 1 `aaaaaaa`, round 2 `eeeeeee`.\n' in r3)
    check('--next reads a merge base that moved from GitHub', 'base `9999999`' in r3 and 'git diff 9999999 fffffff' in r3)
    check('--next replaces the whole paragraph on what the last round read',
          'over two lines' not in r3 and 'diff eeeeeee fffffff' in r3 and r3.count('This round reads') == 1)
    check('--next names a line that still holds the old head', 'still names round 2\'s head eeeeeee' in out
          and 'risk engineer reads it' in out)
    check('--next does not name a line it moved', 'archive' not in out)

    before = read(os.path.join(SCRATCH, 'r3.md'))
    code, out = nxt(r2, 'r3.md', 'fffffff6666', STUB_SHA='fffffff6666', STUB_LOCAL='fffffff6666')
    check('--next refuses to overwrite a brief', code != 0 and 'already exists' in out
          and read(os.path.join(SCRATCH, 'r3.md')) == before)

    code, out = nxt(r1, 'mismatch.md', 'eeeeeee5555', STUB_SHA='1234567aaaa')
    check('--next stops when GitHub has another head, and writes nothing', code != 0 and 'not eeeeeee' in out
          and not os.path.exists(os.path.join(SCRATCH, 'mismatch.md')))

    code, out = nxt(r1, 'flag.md', 'eeeeeee5555', STUB_SHA='eeeeeee5555')
    check('--next flags a checkout not at the new head', code == 0
          and 'Checkout HEAD is `aaaaaaa`' in read(os.path.join(SCRATCH, 'flag.md')))

    code, out = nxt(brief('other.md', R1.replace('archive aaaaaaa', 'archive 1234567')), 'other-out.md',
                    'eeeeeee5555', STUB_SHA='eeeeeee5555', STUB_LOCAL='eeeeeee5555')
    check('--next stops on an archive line naming another commit', code != 0 and 'archive line names 1234567' in out
          and not os.path.exists(os.path.join(SCRATCH, 'other-out.md')))

    code, out = nxt(brief('untitled.md', R1.replace(', round 1', '')), 'u.md', 'eeeeeee5555')
    check('--next stops on a title with no round', code != 0 and "round <N>'" in out)

    code, out = nxt(brief('gap.md', R1.replace(', round 1', ', round 3')), 'g.md', 'eeeeeee5555', STUB_SHA='eeeeeee5555')
    check('--next stops when the earlier anchors do not reach the round', code != 0 and 'earlier rounds none' in out
          and not os.path.exists(os.path.join(SCRATCH, 'g.md')))

    code, out = nxt(brief('none.md', '# Review brief: x, round 1\n\nNo items.\n'), 'n.md', 'eeeeeee5555')
    check('--next stops on a brief with no items', code != 0 and 'no item' in out)

    code, two = run('o/r#5=/co', 'o/s#6', STUB_SHA_S='1111111bbbb')
    TWO = (f'# Review brief: two, round 1\n\n## Subject and anchors\n\n{two.strip()}\n\n'
           '- `git -C /co archive aaaaaaa` and `git -C /s archive 1111111`.\n')
    r1b = brief('two.md', TWO)
    code, out = nxt(r1b, 'two-r2.md', 'o/r#5=eeeeeee5555', 'o/s#6=1111111', STUB_SHA='eeeeeee5555',
                    STUB_LOCAL='eeeeeee5555', STUB_SHA_S='1111111bbbb')
    t2 = read(os.path.join(SCRATCH, 'two-r2.md')) if code == 0 else ''
    check('--next moves each pull request to its own head', '**o/r PR #5**, head `eeeeeee`' in t2
          and '**o/s PR #6**, head `1111111`' in t2 and 'Earlier rounds read round 1 `1111111`.' in t2)
    check('--next moves each archive line by the head it named', 'archive eeeeeee` and `git -C /s archive 1111111`' in t2)
    check('--next keeps the item numbers', '\n2. **o/s PR #6**' in t2)
    check('--next writes <checkout> in the blank where the item names none', 'git -C <checkout> diff 1111111 1111111' in t2)

    code, out = nxt(r1b, 'two-bare.md', 'eeeeeee5555')
    check('--next refuses a bare head for two pull requests', code != 0 and 'bare HEAD' in out)
    code, out = nxt(r1b, 'two-short.md', 'o/r#5=eeeeeee5555')
    check('--next wants a head for every pull request', code != 0 and 'Missing: o/s#6' in out)
    code, out = nxt(r1b, 'two-wrong.md', 'o/r#5=eeeeeee5555', 'o/t#7=eeeeeee5555')
    check('--next refuses a pull request the brief does not list', code != 0 and 'no such pull request' in out)
    code, out = nxt(r1b, 'two-bad.md', 'o/r#5=main')
    check('--next refuses a head that is not a commit', code != 0 and 'not OWNER/REPO#N=HEAD' in out)
    code, out = run('--next', r1b)
    check('--next without --out shows its usage', code != 0 and '--out NEW_BRIEF' in out)

print('all passed' if not failures else f'{failures} failed')
sys.exit(1 if failures else 0)
