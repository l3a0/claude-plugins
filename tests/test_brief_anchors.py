#!/usr/bin/env python3
"""Tests for skills/ask-team/scripts/brief_anchors.py against stand-in `gh` and `git` commands.

    python3 tests/test_brief_anchors.py

The stand-ins answer from environment variables, so the test needs no network and no GitHub login. The stand-in
`gh` gives the merge base and the base branch's tip different commits, so a script that read the wrong one fails.
The `--next` cases write a round 1 brief from the script's own items, then write later rounds from it. One also
starts from `fixtures/review-brief-round-1.md`, a whole brief whose round 1 head had the base merged on top of its fix.
Each stand-in also checks its arguments and fails on a call to the wrong repository, pull request, commit or
checkout, so a script that dropped `-R` or `-C` fails too.
"""
import os, stat, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURE = os.path.join(HERE, 'fixtures', 'review-brief-round-1.md')
SCRIPT = os.path.join(HERE, '..', 'skills', 'ask-team', 'scripts', 'brief_anchors.py')

GH = '''#!/bin/sh
d="$(dirname "$0")"
case "$*" in
  "pr view 5 -R o/r "*|"pr view 05 -R o/r "*|"pr view 6 -R o/s "*)
    echo "$5" > "$d/last_repo"
    if [ "$5" = o/s ]; then sha="${STUB_SHA_S:-${STUB_SHA:-aaaaaaa1111}}"; else sha="${STUB_SHA:-aaaaaaa1111}"; fi
    echo "$sha" > "$d/last_sha"
    printf '{"headRefOid":"%s","headRefName":"%s","baseRefName":"%s","state":"%s"}' \\
      "$sha" "${STUB_HEAD_REF:-feat}" "${STUB_BASE:-main}" "${STUB_STATE:-OPEN}";;
  "api repos/$(cat "$d/last_repo")/compare/${STUB_BASE:-main}...$(cat "$d/last_sha") "*)
    case "$*" in *merge_base_commit*) echo "${STUB_MB:-bbbbbbb2222}";; *) echo "ddddddd3333";; esac;;
  "api repos/$(cat "$d/last_repo")/compare/"*"...$(cat "$d/last_sha") --jq .status"|\
  "api repos/$(cat "$d/last_repo")/compare/"*"...${STUB_FIX:-none} --jq .status"|\
  "api repos/o/s/compare/"*"...${STUB_FIX_S:-none} --jq .status")
    # STUB_OLD_STATUS_S answers every compare on o/s, so one companion can move as a fix while the other was
    # force-pushed.
    if [ "$(cat "$d/last_repo")" = o/s ] && [ -n "${STUB_OLD_STATUS_S:-}" ]; then echo "$STUB_OLD_STATUS_S"; exit 0; fi
    # The fix against the head answers STUB_FIX_STATUS, and the last round's head against the fix STUB_OLD_STATUS.
    # A status of 404 answers as GitHub does for a commit the repository lacks.
    span="${2#repos/*/compare/}"
    # Any other span is unexpected, so a script that compared the last head with the head rather than the fix fails,
    # and where STUB_OLD names the last round's head, so does one that compared another commit with the fix.
    fix="${STUB_FIX:-none}"; [ "$fix" = none ] && fix="$(cat "$d/last_sha")"
    if [ "${span%%...*}" = "${STUB_FIX:-none}" ] && [ "${span#*...}" = "$(cat "$d/last_sha")" ]; then
      st="${STUB_FIX_STATUS:-ahead}"
    elif [ "${span#*...}" = "$fix" ] && { [ -z "${STUB_OLD:-}" ] || [ "${span%%...*}" = "$STUB_OLD" ]; }; then
      st="${STUB_OLD_STATUS:-ahead}"
    elif [ -n "${STUB_OLD:-}" ] && [ "${span%%...*}" = "$STUB_OLD" ] && [ "${span#*...}" = "$(cat "$d/last_sha")" ]; then
      # The last round's head against the head, which a run with --fix asks when the fix does not hold that head.
      st="${STUB_OLD_HEAD_STATUS:-${STUB_OLD_STATUS:-ahead}}"
    else
      echo "stand-in gh: unexpected call: $*" >&2; exit 1
    fi
    [ "$st" = 404 ] && { echo "gh: Not Found (HTTP 404)" >&2; exit 1; }
    echo "$st";;
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
    check('--next names only the line it left alone', out.count('still names') == 1)

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

    check('--next names no line for a pull request whose head did not move', 'still names' not in out)

    # A force push on one companion: that pull request's part of the blank names the whole change, and the other's
    # still names the round's fixes.
    code, out = nxt(r1b, 'two-pushed.md', 'o/r#5=eeeeeee5555', 'o/s#6=1111111', STUB_SHA='eeeeeee5555',
                    STUB_LOCAL='eeeeeee5555', STUB_SHA_S='1111111bbbb', STUB_OLD_STATUS='diverged')
    tp = read(os.path.join(SCRATCH, 'two-pushed.md')) if code == 0 else ''
    check('--next names the whole change only for the companion a force push replaced', code == 0
          and "<This round reads the whole change, `git -C /co diff bbbbbbb eeeeeee`, on o/r PR #5, because a force "
              "push replaced round 1's head aaaaaaa; round 1's fixes, `git -C <checkout> diff 1111111 1111111`, on "
              "o/s PR #6, leaving out what a merge of the base brought, and any passage" in tp)
    # The other companion moved as a fix, from 1111111 to 3333333, under a merge at 2222222, so its part names its
    # last head and its fix, and neither its new head nor the merge base.
    code, out = nxt(r1b, 'two-moved.md', 'o/r#5=eeeeeee5555', 'o/s#6=2222222', '--fix', 'o/s#6=3333333',
                    STUB_SHA='eeeeeee5555', STUB_LOCAL='eeeeeee5555', STUB_SHA_S='2222222bbbb', STUB_FIX_S='3333333',
                    STUB_OLD_STATUS='diverged', STUB_OLD_STATUS_S='ahead')
    tm = read(os.path.join(SCRATCH, 'two-moved.md')) if code == 0 else ''
    check('--next names the last head and the fix for a companion that moved as a fix beside one a force push '
          'replaced', code == 0 and "on o/r PR #5, because a force push replaced round 1's head aaaaaaa; round 1's "
          "fixes, `git -C <checkout> diff 1111111 3333333`, on o/s PR #6," in tm
          and 'bbbbbbb 2222222' not in tm[tm.find('<This round reads'):])

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

    first = items.split('\n')[0]
    inline = R1.replace(first, first.replace(' Diff:', ' Changes `stress.py`. Diff:'))
    code, out = nxt(brief('inline.md', inline), 'inline-out.md', 'eeeeeee5555', STUB_SHA='eeeeeee5555', STUB_LOCAL='eeeeeee5555')
    check('--next stops on text written on an item\'s first line, and writes nothing', code != 0
          and 'did not print' in out and 'line 5' in out and not os.path.exists(os.path.join(SCRATCH, 'inline-out.md')))

    TEMPLATE_LINE = ('<From round 2 on, `brief_anchors.py --next` writes this paragraph as a blank. Fill it.\n'
                     'Delete this line in round 1.>')
    kept = R1.replace('Review the head commit', TEMPLATE_LINE + '\n\nReview the head commit')
    code, out = nxt(brief('kept.md', kept), 'kept-out.md', 'eeeeeee5555', STUB_SHA='eeeeeee5555', STUB_LOCAL='eeeeeee5555')
    k2 = read(os.path.join(SCRATCH, 'kept-out.md')) if code == 0 else ''
    check('--next replaces the template\'s own round 2 line', code == 0 and 'From round 2 on' not in k2
          and k2.count('<This round reads') == 1)

    code, out = nxt(os.path.join(SCRATCH, 'r2.md'), 'rerun-r3.md', 'fffffff6666', STUB_SHA='fffffff6666', STUB_LOCAL='fffffff6666')
    rr = read(os.path.join(SCRATCH, 'rerun-r3.md')) if code == 0 else ''
    check('--next replaces a blank the last round left unfilled', code == 0 and rr.count('This round reads') == 1
          and 'diff eeeeeee fffffff' in rr)

    listed = R2.replace('over two lines.', 'over two lines:\n\n1. `eeeeeee`, round 1\'s fixes.\n2. `ccccccc`, the merge of main.')
    code, out = nxt(brief('listed.md', listed), 'listed-out.md', 'fffffff6666', STUB_SHA='fffffff6666', STUB_LOCAL='fffffff6666')
    lo = read(os.path.join(SCRATCH, 'listed-out.md')) if code == 0 else ''
    check('--next replaces the list under the paragraph on what the last round read', code == 0
          and 'merge of main' not in lo and 'Review the head commit' in lo and '1. **o/r PR #5**' in lo)

    check('--next names each list line it replaced', out.count('replaced with the paragraph') == 2 and 'merge of main' in out)

    for label, body in (('a loose list', '1. `eeeeeee`, round 1\'s fixes.\n\n2. `ccccccc`, the merge of main.'),
                        ('a bulleted list', '- `eeeeeee`, round 1\'s fixes.\n- `ccccccc`, the merge of main.'),
                        ('a list item with an indented paragraph',
                         '1. `eeeeeee`, round 1\'s fixes.\n\n   Detail of the fix.\n\n2. `ccccccc`, the merge of main.'),
                        ('a list item with a tab-indented paragraph',
                         '1. `eeeeeee`, round 1\'s fixes.\n\n\tDetail of the fix.\n\n2. `ccccccc`, the merge of main.')):
        shaped = R2.replace('over two lines.', 'over two lines:\n\n' + body)
        code, out = nxt(brief('shaped.md', shaped), 'shaped-out.md', 'fffffff6666', STUB_SHA='fffffff6666', STUB_LOCAL='fffffff6666')
        so = read(os.path.join(SCRATCH, 'shaped-out.md')) if code == 0 else ''
        os.remove(os.path.join(SCRATCH, 'shaped-out.md')) if code == 0 else None
        check(f'--next replaces {label} under the paragraph', code == 0 and 'merge of main' not in so
              and 'Detail' not in so and 'Review the head commit' in so)
        check(f'--next names every line of {label} it replaced', 'merge of main' in out
              and ('Detail' not in body or 'Detail of the fix' in out))

    tight = R2.replace('over two lines.', 'over two lines:\n1. `eeeeeee`, round 1\'s fixes.\n\n   Detail of the fix.')
    code, out = nxt(brief('tight.md', tight), 'tight-out.md', 'fffffff6666', STUB_SHA='fffffff6666', STUB_LOCAL='fffffff6666')
    to = read(os.path.join(SCRATCH, 'tight-out.md')) if code == 0 else ''
    check('--next replaces a list written with no blank line above it, and its indented paragraph', code == 0
          and 'round 1\'s fixes.\n' not in to and 'Detail' not in to and 'Review the head commit' in to)
    check('--next names a list written with no blank line above it', 'round 1\'s fixes.' in out and 'Detail of the fix' in out)

    one = R2.replace("This round reads round 1's fixes, `git diff aaaaaaa eeeeeee`,\nand the passage `archive aaaaaaa` named, over two lines.",
                     "This round reads the fixes:\n1. `eeeeeee`, round 1's fixes.\n\n   Detail of the fix.")
    code, out = nxt(brief('one.md', one), 'one-out.md', 'fffffff6666', STUB_SHA='fffffff6666', STUB_LOCAL='fffffff6666')
    oo = read(os.path.join(SCRATCH, 'one-out.md')) if code == 0 else ''
    check('--next replaces and names a list right under a one-line paragraph', code == 0 and 'Detail' not in oo
          and "round 1's fixes." in out and 'Detail of the fix' in out)

    bullet = one.replace("1. `eeeeeee`, round 1's fixes.", "- `eeeeeee`, round 1's fixes.")
    code, out = nxt(brief('bullet.md', bullet), 'bullet-out.md', 'fffffff6666', STUB_SHA='fffffff6666', STUB_LOCAL='fffffff6666')
    check('--next replaces and names a bulleted list right under the paragraph', code == 0
          and 'Detail' not in read(os.path.join(SCRATCH, 'bullet-out.md')) and "round 1's fixes." in out)

    year = R2.replace('over two lines.', 'over\n2026. It also reads more.\n\n   Kept command.')
    code, out = nxt(brief('year.md', year), 'year-out.md', 'fffffff6666', STUB_SHA='fffffff6666', STUB_LOCAL='fffffff6666')
    check('--next keeps an indented line under a wrapped line that starts with a year, and names that line', code == 0
          and 'Kept command.' in read(os.path.join(SCRATCH, 'year-out.md')) and '2026. It also reads more.' in out)

    for label, tail in (('a 2. line', 'over two lines:\n2. `ccccccc`, the second fix.\n   Glued detail.'),
                        ('a year line', 'over\n2026. It also reads more,\nwrapped onto a glued line.')):
        glued_tail = R2.replace('over two lines.', tail)
        code, out = nxt(brief('tail.md', glued_tail), 'tail-out.md', 'fffffff6666', STUB_SHA='fffffff6666', STUB_LOCAL='fffffff6666')
        last = tail.split('\n')[-1].strip()
        check(f'--next names a line glued under {label} that it replaced', code == 0 and last in out
              and last not in read(os.path.join(SCRATCH, 'tail-out.md')))
        if code == 0:
            os.remove(os.path.join(SCRATCH, 'tail-out.md'))

    digit = R2.replace('over two lines.', 'over\n2. It also reads more.\n\n   Kept command.')
    code, out = nxt(brief('digit.md', digit), 'digit-out.md', 'fffffff6666', STUB_SHA='fffffff6666', STUB_LOCAL='fffffff6666')
    check('--next keeps an indented line under a wrapped line that starts with 2.', code == 0
          and 'Kept command.' in read(os.path.join(SCRATCH, 'digit-out.md')) and '2. It also reads more.' in out)

    paren = one.replace("1. `eeeeeee`, round 1's fixes.", "1) `eeeeeee`, round 1's fixes.")
    code, out = nxt(brief('paren.md', paren), 'paren-out.md', 'fffffff6666', STUB_SHA='fffffff6666', STUB_LOCAL='fffffff6666')
    check('--next replaces and names a 1) list right under the paragraph', code == 0
          and 'Detail' not in read(os.path.join(SCRATCH, 'paren-out.md')) and "round 1's fixes." in out and 'Detail of the fix' in out)

    third = R2.replace('over two lines.', 'over two lines:\n3. `ccccccc`, the third fix.')
    code, out = nxt(brief('third.md', third), 'third-out.md', 'fffffff6666', STUB_SHA='fffffff6666', STUB_LOCAL='fffffff6666')
    check('--next names a numbered line other than 1. that it replaced with the paragraph', code == 0
          and 'the third fix.' in out and 'the third fix' not in read(os.path.join(SCRATCH, 'third-out.md')))


    moved = R2[:R2.index('\n\nThis round reads round 1')] + R2[R2.index('\n\nReview the head'):]
    moved = moved.replace('## Subject and anchors\n\n', '## Subject and anchors\n\nThis round reads the fixes,\nover two lines.\n\n')
    code, out = nxt(brief('moved.md', moved), 'moved-out.md', 'fffffff6666', STUB_SHA='fffffff6666', STUB_LOCAL='fffffff6666')
    check('--next warns on no item line when the paragraph sits above the items', code == 0 and '**o/r PR #5**' not in out)

    glued = moved.replace('over two lines.\n\n1. **o/r PR #5**', 'over two lines.\n1. **o/r PR #5**')
    code, out = nxt(brief('glued.md', glued), 'glued-out.md', 'fffffff6666', STUB_SHA='fffffff6666', STUB_LOCAL='fffffff6666')
    go = read(os.path.join(SCRATCH, 'glued-out.md')) if code == 0 else ''
    check('--next never replaces an item line right under the paragraph', code == 0 and '1. **o/r PR #5**, head `fffffff`' in go
          and 'Changes `order_path.py`' in go and '**o/r PR #5**' not in out)

    glued_list = moved.replace('over two lines.\n\n1. **o/r PR #5**', 'over two lines.\n\n- `eeeeeee`, round 1\'s fixes.\n1. **o/r PR #5**')
    code, out = nxt(brief('glued-list.md', glued_list), 'glued-list-out.md', 'fffffff6666', STUB_SHA='fffffff6666', STUB_LOCAL='fffffff6666')
    gl = read(os.path.join(SCRATCH, 'glued-list-out.md')) if code == 0 else ''
    check('--next stops a list under the paragraph at an item line right under it', code == 0
          and '1. **o/r PR #5**, head `fffffff`' in gl and "round 1's fixes." not in gl)

    note = R2.replace('over two lines.', 'over two lines.\n\n   Kept note.')
    code, out = nxt(brief('note.md', note), 'note-out.md', 'fffffff6666', STUB_SHA='fffffff6666', STUB_LOCAL='fffffff6666')
    check('--next keeps an indented line under the paragraph when no list comes first', code == 0
          and 'Kept note.' in read(os.path.join(SCRATCH, 'note-out.md')) and 'replaced with' not in out)

    above = R2[:R2.index('\n\nThis round reads round 1')] + R2[R2.index('\n\nReview the head'):]
    above = above.replace('## Subject and anchors\n\n', '## Subject and anchors\n\nThis round reads the fixes.\n\n')
    code, out = nxt(brief('above.md', above), 'above-out.md', 'fffffff6666', STUB_SHA='fffffff6666', STUB_LOCAL='fffffff6666')
    ab = read(os.path.join(SCRATCH, 'above-out.md')) if code == 0 else ''
    check('--next keeps an item right under the paragraph', code == 0 and '1. **o/r PR #5**, head `fffffff`' in ab
          and 'Changes `order_path.py`' in ab)

    inline_after = R1.replace(first, first + ' Changes `stress.py`.')
    code, out = nxt(brief('after.md', inline_after), 'after-out.md', 'eeeeeee5555', STUB_SHA='eeeeeee5555', STUB_LOCAL='eeeeeee5555')
    check('--next stops on text after the diff on an item\'s first line', code != 0 and 'did not print' in out)
    code, out = nxt(brief('spaces.md', R1.replace(first, first + '   ')), 'spaces-out.md', 'eeeeeee5555',
                    STUB_SHA='eeeeeee5555', STUB_LOCAL='eeeeeee5555')
    check('--next accepts trailing spaces on an item\'s first line', code == 0)

    for label, env in (('the checkout flag', {'STUB_LOCAL': 'ccccccc4444'}), ('a state that is not open', {'STUB_STATE': 'MERGED'}),
                       ('an unusual branch name', {'STUB_HEAD_REF': 'x`<!--hidden-->'})):
        code, flagged = run('o/r#5=/co', **env)
        flagged = flagged.strip()
        body = f'# Review brief: flagged, round 1\n\n{flagged}\n'
        code, out = nxt(brief('flagged.md', body), 'flagged-out.md', 'eeeeeee5555', STUB_SHA='eeeeeee5555', **env)
        check(f'--next accepts a first line it printed with {label}', code == 0)
        if code == 0:
            os.remove(os.path.join(SCRATCH, 'flagged-out.md'))

    code, out = nxt(brief('dup.md', R1.replace(items, items + '\n\n' + items)), 'dup-out.md', 'eeeeeee5555')
    check('--next stops on a brief that lists one pull request twice', code != 0 and 'listed twice' in out)

    swapped = R2.replace(', round 2\n', ', round 3\n').replace(
        'Earlier rounds read round 1 `aaaaaaa`.', 'Earlier rounds read round 2 `aaaaaaa`, round 1 `aaaaaaa`.')
    code, out = nxt(brief('swapped.md', swapped), 'swapped-out.md', 'fffffff6666', STUB_SHA='fffffff6666')
    check('--next stops on earlier anchors out of order', code != 0 and 'earlier rounds 2, 1' in out
          and not os.path.exists(os.path.join(SCRATCH, 'swapped-out.md')))

    # A round whose fix sits under a merge of the base: the next round anchors at the merge, and reads only the fix.
    with open(FIXTURE) as f:
        FIX_R1 = f.read()
    fixture = brief('fixture-r1.md', FIX_R1)
    merged = dict(STUB_SHA='ccccccc9999', STUB_LOCAL='ccccccc9999', STUB_FIX='eeeeeee5555', STUB_OLD='aaaaaaa')
    code, out = nxt(fixture, 'fixture-r2.md', '--fix', 'eeeeeee5555', 'ccccccc9999', **merged)
    fr2 = read(os.path.join(SCRATCH, 'fixture-r2.md')) if code == 0 else ''
    check('--next --fix exits 0 on the fixture brief', code == 0)
    check('--next --fix moves the subject to the new round and head', fr2.startswith(
        '# Review brief: settle an order, round 2\n') and '1. **o/r PR #5**, head `ccccccc`' in fr2
          and 'Earlier rounds read round 1 `aaaaaaa`.\n' in fr2)
    check('--next --fix names the diff from the last anchor to the fix, not to the new head',
          "<This round reads round 1's fixes: `git -C /co diff aaaaaaa eeeeeee` on o/r PR #5," in fr2
          and 'diff aaaaaaa ccccccc' not in fr2)
    check('--next --fix moves the archive line to the new head, not to the fix', 'archive ccccccc | tar' in fr2)
    scope = FIX_R1[FIX_R1.index('## Out of scope'):]
    check('--next --fix carries the out-of-scope list forward unchanged', fr2.endswith(scope)
          and fr2.count('## Out of scope') == 1)

    code, out = nxt(fixture, 'fixture-named.md', '--fix', 'o/r#5=eeeeeee5555', 'o/r#5=ccccccc9999', **merged)
    check('--next takes --fix OWNER/REPO#N=FIX', code == 0
          and 'diff aaaaaaa eeeeeee' in read(os.path.join(SCRATCH, 'fixture-named.md')))

    code, out = nxt(fixture, 'fixture-diverged.md', '--fix', 'eeeeeee5555', 'ccccccc9999', STUB_FIX_STATUS='diverged',
                    **merged)
    check('--next stops on a fix outside the head\'s history, and writes nothing', code != 0
          and 'not in the head\'s history' in out and 'diverged' in out
          and not os.path.exists(os.path.join(SCRATCH, 'fixture-diverged.md')))
    code, out = nxt(fixture, 'fixture-behind.md', '--fix', 'eeeeeee5555', 'ccccccc9999', STUB_FIX_STATUS='behind',
                    **merged)
    check('--next stops on a fix that comes after the head, and writes nothing', code != 0 and 'behind' in out
          and not os.path.exists(os.path.join(SCRATCH, 'fixture-behind.md')))
    code, out = nxt(fixture, 'fixture-unknown.md', '--fix', 'eeeeeee5555', 'ccccccc9999', STUB_FIX_STATUS='404',
                    **merged)
    check('--next stops on a fix GitHub cannot compare', code != 0 and 'Not Found' in out
          and not os.path.exists(os.path.join(SCRATCH, 'fixture-unknown.md')))
    # A force push, such as a rebase, leaves the last head outside the head's history. The diff then holds the whole
    # rebase rather than the round's fixes, so the run says so on standard error and the blank names the whole change.
    for status in ('diverged', 'behind'):
        code, out = nxt(fixture, f'fixture-old-{status}.md', '--fix', 'eeeeeee5555', 'ccccccc9999',
                        STUB_OLD_STATUS=status, **merged)
        written = read(os.path.join(SCRATCH, f'fixture-old-{status}.md')) if code == 0 else ''
        check(f'--next warns when the last head is {status} against the fix and the head, as after a force push, '
              'and writes the brief', code == 0 and "not in the head's history" in out
              and 'more than the round' in out and '#108' not in out and "review-round.md's step 1" in out)
        check(f'--next names the whole change from the merge base when the last head is {status}, not the diff '
              'from that head', "<This round reads the whole change, `git -C /co diff bbbbbbb ccccccc`, on o/r PR #5, "
              "because a force push replaced round 1's head aaaaaaa, and any passage" in written
              and 'diff aaaaaaa eeeeeee' not in written and "round 1's fixes" not in written)
    # A fix from before the last head, while the head still holds that head, is a mistake rather than a force push.
    for status in ('behind', 'diverged'):
        code, out = nxt(fixture, f'fixture-early-{status}.md', '--fix', 'eeeeeee5555', 'ccccccc9999',
                        STUB_OLD_STATUS=status, STUB_OLD_HEAD_STATUS='ahead', **merged)
        check(f'--next stops on a fix {status} against a last head the head still holds, and writes nothing',
              code != 0 and 'from before the round' in out and status in out
              and not os.path.exists(os.path.join(SCRATCH, f'fixture-early-{status}.md')))
    # The warning goes to standard error, as the docstring says, so standard output stays clean.
    split = subprocess.run([sys.executable, SCRIPT, '--next', fixture, '--out', os.path.join(SCRATCH, 'fixture-split.md'),
                            '--fix', 'eeeeeee5555', 'ccccccc9999'], capture_output=True, text=True,
                           env=dict(os.environ, PATH=BIN + os.pathsep + os.environ['PATH'], STUB_OLD_STATUS='diverged',
                                    **merged))
    check('--next prints the force-push warning on standard error only', split.returncode == 0
          and 'more than the round' in split.stderr and 'more than the round' not in split.stdout)
    brief_05 = brief('fixture-05.md', FIX_R1.replace('**o/r PR #5**', '**o/r PR #05**'))
    code, out = nxt(brief_05, 'fixture-05-out.md', 'o/r#5=ccccccc9999', **merged)
    check('--next reads a brief item the first form wrote as PR #05', code == 0
          and '**o/r PR #05**, head `ccccccc`' in read(os.path.join(SCRATCH, 'fixture-05-out.md')))
    code, out = nxt(brief_05, 'fixture-05-fix.md', '--fix', 'o/r#5=eeeeeee5555', 'o/r#5=ccccccc9999', **merged)
    check('--next applies a --fix to a brief item written PR #05', code == 0
          and 'diff aaaaaaa eeeeeee' in read(os.path.join(SCRATCH, 'fixture-05-fix.md')))
    # A round that changed nothing on a pull request leaves its head where it was, and a --fix from before it is a
    # mistake, not a force push.
    code, out = nxt(fixture, 'fixture-unchanged-early.md', '--fix', 'eeeeeee5555', 'aaaaaaa1111', STUB_OLD_STATUS='behind',
                    **dict(merged, STUB_SHA='aaaaaaa1111', STUB_LOCAL='aaaaaaa1111'))
    check('--next stops on a fix from before a last head that is the head itself', code != 0
          and 'from before the round' in out and not os.path.exists(os.path.join(SCRATCH, 'fixture-unchanged-early.md')))
    for answer in (' ', 'unknown'):
        code, out = nxt(fixture, 'fixture-odd.md', '--fix', 'eeeeeee5555', 'ccccccc9999', STUB_OLD_STATUS=answer,
                        **merged)
        check(f'--next stops on a compare answer GitHub does not document ({answer!r})', code != 0
              and 'none of ahead' in out
              and not os.path.exists(os.path.join(SCRATCH, 'fixture-odd.md')))
    code, out = nxt(fixture, 'fixture-odd-fix.md', '--fix', 'eeeeeee5555', 'ccccccc9999', STUB_FIX_STATUS='unknown',
                    **merged)
    check('--next stops on an undocumented answer for the fix against the head', code != 0 and 'none of ahead' in out
          and not os.path.exists(os.path.join(SCRATCH, 'fixture-odd-fix.md')))
    code, out = nxt(fixture, 'fixture-odd-nofix.md', 'ccccccc9999', STUB_OLD_STATUS=' ', **dict(merged, STUB_FIX='none'))
    check('--next with no --fix stops on an empty compare answer', code != 0 and 'none of ahead' in out
          and not os.path.exists(os.path.join(SCRATCH, 'fixture-odd-nofix.md')))
    code, out = nxt(fixture, 'fixture-odd-held.md', '--fix', 'eeeeeee5555', 'ccccccc9999', STUB_OLD_STATUS='diverged',
                    STUB_OLD_HEAD_STATUS=' ', **merged)
    check('--next stops on an empty answer for the last head against the head', code != 0 and 'none of ahead' in out
          and not os.path.exists(os.path.join(SCRATCH, 'fixture-odd-held.md')))
    code, out = nxt(fixture, 'fixture-held-404.md', '--fix', 'eeeeeee5555', 'ccccccc9999', STUB_OLD_STATUS='diverged',
                    STUB_OLD_HEAD_STATUS='404', **merged)
    check('--next stops when GitHub cannot compare the last head with the head', code != 0 and 'Not Found' in out
          and not os.path.exists(os.path.join(SCRATCH, 'fixture-held-404.md')))
    code, out = nxt(fixture, 'fixture-ahead.md', '--fix', 'eeeeeee5555', 'ccccccc9999', **merged)
    check('--next says nothing of a force push when the last head is in the fix\'s history', code == 0
          and 'more than the round' not in out)
    check('--next names the round\'s fixes, not the whole change, when the last head is in the fix\'s history',
          "<This round reads round 1's fixes: `git -C /co diff aaaaaaa eeeeeee`" in read(
              os.path.join(SCRATCH, 'fixture-ahead.md')) and 'the whole change, `' not in read(
              os.path.join(SCRATCH, 'fixture-ahead.md')))
    code, out = nxt(fixture, 'fixture-old-pushed.md', 'ccccccc9999', STUB_OLD_STATUS='diverged',
                    **dict(merged, STUB_FIX='none'))
    check('--next warns on a force-pushed head with no --fix too', code == 0 and "not in the head's history" in out
          and 'diff bbbbbbb ccccccc' in read(os.path.join(SCRATCH, 'fixture-old-pushed.md')))
    code, out = nxt(fixture, 'fixture-old-unknown.md', 'ccccccc9999', STUB_OLD_STATUS='404',
                    **dict(merged, STUB_FIX='none'))
    check('--next stops when GitHub no longer holds the last head', code != 0 and 'Not Found' in out
          and not os.path.exists(os.path.join(SCRATCH, 'fixture-old-unknown.md')))
    code, out = nxt(fixture, 'fixture-unchanged.md', '--fix', 'aaaaaaa', 'ccccccc9999', STUB_FIX='aaaaaaa',
                    STUB_OLD_STATUS='404', **{k: v for k, v in merged.items() if k != 'STUB_FIX'})
    check('--next takes a fix that is the last head, for a round that changed nothing, with no compare of the two',
          code == 0 and 'diff aaaaaaa aaaaaaa' in read(os.path.join(SCRATCH, 'fixture-unchanged.md')))
    code, out = nxt(fixture, 'fixture-zero.md', '--fix', 'o/r#05=eeeeeee5555', 'o/r#005=ccccccc9999', **merged)
    check('--next reads o/r#05 as the pull request the brief lists as o/r PR #5', code == 0)
    code, out = nxt(fixture, 'fixture-other.md', '--fix', 'o/t#7=eeeeeee5555', 'ccccccc9999', **merged)
    check('--next refuses a fix for a pull request the brief does not list', code != 0 and 'no such pull request' in out)
    code, out = nxt(fixture, 'fixture-twice.md', '--fix', 'o/r#5=eeeeeee5555', '--fix', 'O/R#5=eeeeeee5555', 'ccccccc9999',
                    **merged)
    check('--next refuses two fixes for one pull request', code != 0 and 'named twice' in out and 'FIX' in out)
    code, out = nxt(fixture, 'fixture-dangling.md', 'ccccccc9999', '--fix', **merged)
    check('--next refuses a --fix with no commit after it', code != 0 and '--fix' in out)
    code, out = nxt(fixture, 'fixture-nohead.md', '--fix', 'eeeeeee5555', **merged)
    check('--next refuses a --fix with no head', code != 0 and 'usage' in out)
    code, out = run('o/r#5=/co', 'O/R#05')
    check('the first form refuses one pull request named twice', code != 0 and 'named twice' in out
          and '**o/r PR #5**' not in out)
    code, out = nxt(fixture, 'fixture-heads.md', 'o/r#5=ccccccc9999', 'o/r#5=ddddddd1234', **merged)
    check('--next refuses two heads for one pull request', code != 0 and 'named twice' in out)
    code, out = nxt(fixture, 'fixture-same.md', '--fix', 'ccccccc', 'ccccccc9999', **dict(merged, STUB_FIX='none'))
    check('--next takes a fix that is the head itself, with no compare call', code == 0
          and 'diff aaaaaaa ccccccc' in read(os.path.join(SCRATCH, 'fixture-same.md')))

print('all passed' if not failures else f'{failures} failed')
sys.exit(1 if failures else 0)
