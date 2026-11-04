#!/usr/bin/env python3
"""Tests for skills/ask-team/scripts/review_post.py against a stand-in `gh`.

    python3 tests/test_review_post.py

The stand-in keeps one pull request per file in a state folder, so the test needs no network and no GitHub login.
It fails on a call to the wrong repository or number, so a script that dropped `-R` fails too. The fixture's
`## What` list shares its numbers with the `## Revision` list and the body ends in a closing line and the footer,
which is the shape that lost two `## What` items on l3a0/ithildin-runtime PR #28.
"""
import importlib.util, json, os, stat, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, '..', 'skills', 'ask-team', 'scripts', 'review_post.py')

GH = '''#!/usr/bin/env python3
import json, os, sys
state = os.environ['STUB_STATE']
args = sys.argv[1:]
def fail(): sys.exit('stand-in gh: unexpected call: ' + ' '.join(args))
if args[0] != 'pr' or args[3] != '-R': fail()
path = os.path.join(state, args[4].replace('/', '-') + '-' + args[2] + '.json')
if not os.path.exists(path): fail()
pr = json.load(open(path))
if args[1] == 'view' and args[5] == '--json':
    print(json.dumps({args[6]: pr[args[6]]}))
elif args[1] == 'edit' and args[5] == '--body-file':
    pr['body'] = open(args[6], newline='').read() + os.environ.get('STUB_EDIT_ADDS', '')
    pr['edits'] = pr.get('edits', 0) + 1
    json.dump(pr, open(path, 'w'))
elif args[1] == 'comment' and args[5] == '--body-file':
    if os.environ.get('STUB_COMMENT_FAIL') == args[2]: sys.exit('stand-in gh: comment refused')
    pr['comments'].append({'body': open(args[6]).read()})
    json.dump(pr, open(path, 'w'))
else:
    fail()
'''

BODY = '''## Why

Because.

## What

1. Adds the first thing.
2. Adds the second thing.
3. Adds the third thing.

## Revision

1. `aaaaaaa` answers round 1.
2. `bbbbbbb` answers round 2.

Closes no issue.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
'''
BARE = '''## Why

Because.

## What

1. Adds the first thing.

Part of #33

🤖 Generated with [Claude Code](https://claude.com/claude-code)
'''

failures = 0


def check(name, cond):
    global failures
    print(('ok   ' if cond else 'FAIL ') + name)
    failures += not cond


def load():
    spec = importlib.util.spec_from_file_location('review_post', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


with tempfile.TemporaryDirectory() as ROOT:
    BIN, STATE, SCRATCH = (os.path.join(ROOT, n) for n in ('bin', 'state', 'scratch'))
    os.makedirs(BIN), os.makedirs(STATE)
    path = os.path.join(BIN, 'gh')
    with open(path, 'w') as f:
        f.write(GH)
    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)

    def seed(num, body=BODY, head='a' * 40, comments=(), repo='o-r'):
        with open(os.path.join(STATE, f'{repo}-{num}.json'), 'w') as f:
            json.dump({'body': body, 'headRefOid': head, 'comments': [{'body': c} for c in comments]}, f)

    def state(num, repo='o-r'):
        with open(os.path.join(STATE, f'{repo}-{num}.json')) as f:
            return json.load(f)

    def run(*argv, **env):
        full = dict(os.environ, PATH=BIN + os.pathsep + os.environ['PATH'], STUB_STATE=STATE, **env)
        done = subprocess.run([sys.executable, SCRIPT, *argv], capture_output=True, text=True, env=full)
        return done.returncode, done.stdout + done.stderr

    def revise(*extra, pull='o/r#5', **env):
        return run('revision', pull, '--scratch', SCRATCH, *extra, **env)

    seed(5)
    code, out = revise('--line', '`ccccccc` answers round 3.')
    body = state(5)['body']
    check('adds the next number at the end of the section', '2. `bbbbbbb` answers round 2.\n3. `ccccccc` answers round 3.\n\nCloses' in body)
    check('leaves the What list alone', '3. Adds the third thing.' in body and code == 0)
    check('keeps the closing line and footer last', body.endswith('Closes no issue.\n\n🤖 Generated with [Claude Code](https://claude.com/claude-code)\n'))
    check('reads the body back', 'read back' in out)
    with open(os.path.join(SCRATCH, 'body-o-r-5.md'), newline='') as f:
        check('saves the body as read', f.read() == BODY)

    code, out = revise('--line', '`ccccccc` answers round 3.')
    check('a retry changes nothing', code == 0 and state(5).get('edits') == 1 and 'nothing changed' in out)

    seed(5)
    code, out = revise('--line', '`ddddddd` answers round 2, corrected.', '--replace', '2')
    body = state(5)['body']
    check('replaces only the Revision item with that number', '2. `ddddddd` answers round 2, corrected.' in body and '2. Adds the second thing.' in body and '`bbbbbbb`' not in body)

    code, out = revise('--line', 'x', '--replace', '9')
    check('refuses an item the section does not have', code != 0 and 'no item 9' in out)

    seed(6, BARE)
    code, out = revise('--line', '`aaaaaaa` answers round 1.', pull='o/r#6')
    body = state(6)['body']
    check('adds a missing section before the closing line', '## Revision\n\n1. `aaaaaaa` answers round 1.\n\nThe review comments list each finding and what was refuted.\n\nPart of #33\n\n🤖' in body)

    seed(7, '## Why\n\nBecause.\n')
    code, out = revise('--line', '`aaaaaaa` answers round 1.', pull='o/r#7')
    check('adds a missing section to a body with no footer', '## Why\n\nBecause.\n\n## Revision\n\n1. `aaaaaaa` answers round 1.\n' in state(7)['body'] and code == 0)

    seed(8, BODY.replace('\n', '\r\n'))
    code, out = revise('--line', '`ccccccc` answers round 3.', pull='o/r#8')
    check('keeps a body written with CRLF line endings', '3. `ccccccc` answers round 3.\r\n\r\nCloses' in state(8)['body'] and code == 0)

    seed(9, BODY.replace('## What', '```\n## Revision\n1. example\n```\n\n## What'))
    code, out = revise('--line', '`ccccccc` answers round 3.', pull='o/r#9')
    check('ignores a heading inside a code fence', '```\n## Revision\n1. example\n```' in state(9)['body'] and '3. `ccccccc`' in state(9)['body'])

    seed(10, BODY + '\n## Revision\n\n1. again\n')
    code, out = revise('--line', 'x', pull='o/r#10')
    check('refuses two Revision sections', code != 0 and 'ambiguous' in out and state(10).get('edits') is None)

    seed(5)
    code, out = revise('--line', '`ccccccc` answers round 3.', STUB_EDIT_ADDS='changed')
    check('stops when the body read back differs', code != 0 and 'read back differs' in out and state(5)['edits'] == 1)

    seed(5)
    code, out = revise('--line', '`ccccccc` answers round 3.', '--dry-run')
    check('a dry run sends nothing', state(5).get('edits') is None and '+3. `ccccccc`' in out)

    code, out = revise('--line', 'two\nlines')
    check('refuses an entry of two lines', code != 0)

    module = load()
    check('the second check finds a line changed outside the section',
          module.changed_outside(BODY, BODY.replace('2. Adds the second thing.', '2. Overwritten.'), 12, 16) != [])
    check('the second check passes a change inside the section',
          module.changed_outside(BODY, BODY.replace('`bbbbbbb`', '`ddddddd`'), 12, 16) == [])

    check('the second check flags a line deleted beside the section',
          module.changed_outside(BODY, BODY.replace('## Why\n\nBecause.\n\n', ''), 12, 16) != [])

    done = BODY.split('\n')
    start, end = module.find_section(done)
    check('the section ends at its last item', done[start] == '## Revision' and done[end - 1].startswith('2. `bbbbbbb`'))

    note = os.path.join(ROOT, 'note.md')
    with open(note, 'w') as f:
        f.write('## Review, round 3\n\nRound 3, of `bbbbbbb`.\n')
    other = os.path.join(ROOT, 'other.md')
    with open(other, 'w') as f:
        f.write('## Review, round 3\n\nRound 3, of `bbbbbbb`, on the companion.\n')
    head5, head6 = 'a' * 40, 'c' * 40

    def post(*targets, **env):
        return run('comment', '--round', '3', '--anchor', 'bbbbbbb', '--heading', '## Review, round 3', *targets, **env)

    seed(5, head=head5), seed(6, head=head6, repo='o-s')
    code, out = post(f'o/r#5={head5}={note}', f'o/s#6={head6}={other}')
    check('posts on every pull request', code == 0 and len(state(5)['comments']) == 1 and len(state(6, 'o-s')['comments']) == 1)

    code, out = post(f'o/r#5={head5}={note}', f'o/s#6={head6}={other}')
    check('a retry posts nothing twice', len(state(5)['comments']) == 1 and out.count('skipped') == 2)

    seed(5, head=head5), seed(6, head=head6, repo='o-s')
    code, out = post(f'o/r#5={head5}={note}', f'o/s#6={"d" * 40}={other}')
    check('posts on no companion when one head differs', code != 0 and state(5)['comments'] == [] and state(6, 'o-s')['comments'] == [])
    check('names the head that differs', 'o/s#6 is at ccccccc' in out)

    seed(5, head=head5, comments=['## Review, round 3\n\nRound 3, of `eeeeeee`.\n'])
    code, out = post(f'o/r#5={head5}={note}')
    check('a comment on another anchor does not block the post', len(state(5)['comments']) == 2)

    seed(5, head=head5, comments=['## Review complete\n\nCloses round 2, of `bbbbbbb`.\n'])
    code, out = run('comment', '--round', '3', '--anchor', 'bbbbbbb', '--heading', '## Review complete', f'o/r#5={head5}={note}')
    check('a comment on another round does not block the post', len(state(5)['comments']) == 2)

    seed(5, head=head5, comments=['## Review, round 2\n\nRound 3, of `bbbbbbb`.\n'])
    code, out = post(f'o/r#5={head5}={note}')
    check('a comment under another heading does not block the post', len(state(5)['comments']) == 2)

    seed(5, head=head5), seed(6, head=head6, repo='o-s')
    code, out = post(f'o/r#5={head5}={note}', f'o/s#6={head6}={other}', STUB_COMMENT_FAIL='6')
    check('a failed post stops with an error', code != 0 and len(state(5)['comments']) == 1)
    code, out = post(f'o/r#5={head5}={note}', f'o/s#6={head6}={other}')
    check('the retry posts only what is missing', len(state(5)['comments']) == 1 and len(state(6, 'o-s')['comments']) == 1)

    code, out = post(f'o/r#5={head5}={os.path.join(ROOT, "missing.md")}')
    check('refuses a comment file that does not exist', code != 0 and 'no comment file' in out)

    seed(5, head=head5)
    code, out = post(f'o/r#5={head5}={note}', '--dry-run')
    check('a dry run posts nothing', state(5)['comments'] == [] and 'would post' in out)

sys.exit(1 if failures else 0)
