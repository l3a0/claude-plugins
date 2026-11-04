#!/usr/bin/env python3
"""Tests for skills/ask-team/scripts/review_post.py against a stand-in `gh`.

    python3 tests/test_review_post.py

The stand-in keeps one pull request per file in a state folder, so the test needs no network and no GitHub login.
It fails on a call to the wrong repository or number, so a script that dropped `-R` fails too. It is a stand-in,
so these tests say nothing about what the real `gh` prints. The fixture's `## What` list shares its numbers with
the `## Revision` list and the body ends in a closing line and the footer, which is the shape that lost two
`## What` items on l3a0/ithildin-runtime PR #28.
"""
import argparse, contextlib, importlib.util, io, json, os, stat, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, '..', 'skills', 'ask-team', 'scripts', 'review_post.py')

GH = '''#!/usr/bin/env python3
import json, os, sys
state = os.environ['STUB_STATE']
args = sys.argv[1:]
login = os.environ.get('STUB_LOGIN', 'me')
def fail(): sys.exit('stand-in gh: unexpected call: ' + ' '.join(args))
if os.environ.get('STUB_READ_FAIL') == ' '.join(args[:2]): sys.exit('stand-in gh: 401 bad credentials')
if os.environ.get('STUB_READ_FAIL') == 'after edit' and args[1] == 'view' and json.load(open(os.path.join(state, 'o-r-5.json'))).get('edits'):
    sys.exit('stand-in gh: 502')
if args[:2] == ['api', 'user']:
    if args[2:4] != ['--jq', '.login']: fail()
    print(login)
    sys.exit(0)
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
    if os.environ.get('STUB_LOST') == 'edit': sys.exit('stand-in gh: connection lost')
elif args[1] == 'comment' and args[5] == '--body-file':
    if os.environ.get('STUB_COMMENT_FAIL') == args[2]: sys.exit('stand-in gh: comment refused')
    pr['comments'].append({'author': {'login': login}, 'body': open(args[6]).read()})
    json.dump(pr, open(path, 'w'))
    if os.environ.get('STUB_DOUBLE') == args[2]:
        pr['comments'].append({'author': {'login': login}, 'body': open(args[6]).read()})
        json.dump(pr, open(path, 'w'))
    if os.environ.get('STUB_LOST') == 'comment': sys.exit('stand-in gh: connection lost')
    print('https://github.com/' + args[4] + '/pull/' + args[2] + '#issuecomment-1')
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
FOOTER = '🤖 Generated with [Claude Code](https://claude.com/claude-code)\n'

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


def numbered(n):
    return '\n'.join(f'{i}. `r{i}` answers round {i}.' for i in range(1, n + 1))


with tempfile.TemporaryDirectory() as ROOT:
    BIN, STATE, SCRATCH = (os.path.join(ROOT, n) for n in ('bin', 'state', 'scratch'))
    os.makedirs(BIN), os.makedirs(STATE)
    path = os.path.join(BIN, 'gh')
    with open(path, 'w') as f:
        f.write(GH)
    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)

    def seed(num, body=BODY, head='a' * 40, comments=(), repo='o-r', login='me'):
        with open(os.path.join(STATE, f'{repo}-{num}.json'), 'w') as f:
            json.dump({'body': body, 'headRefOid': head,
                       'comments': [{'author': {'login': login}, 'body': c} for c in comments]}, f)

    def state(num, repo='o-r'):
        with open(os.path.join(STATE, f'{repo}-{num}.json')) as f:
            return json.load(f)

    def run(*argv, **env):
        full = dict(os.environ, PATH=BIN + os.pathsep + os.environ['PATH'], STUB_STATE=STATE, **env)
        done = subprocess.run([sys.executable, SCRIPT, *argv], capture_output=True, text=True, env=full)
        return done.returncode, done.stdout + done.stderr

    def revise(*extra, pull='o/r#5', **env):
        extra, line = list(extra), os.path.join(ROOT, 'line.txt')
        if '--line' in extra:
            at = extra.index('--line')
            with open(line, 'w', newline='') as f:
                f.write(extra[at + 1])
            extra[at:at + 2] = ['--file', line]
        return run('revision', pull, '--scratch', SCRATCH, *extra, **env)

    def result(body, *extra):
        seed(20, body)
        code, out = revise(*extra, pull='o/r#20')
        return code, out, state(20)

    def saved_bodies():
        found = []
        for name in os.listdir(SCRATCH):
            if name.startswith('body-'):
                with open(os.path.join(SCRATCH, name), newline='') as f:
                    found.append(f.read())
        return found

    seed(5)
    code, out = revise('--line', '`ccccccc` answers round 3.')
    body = state(5)['body']
    check('adds the next number at the end of the section', '2. `bbbbbbb` answers round 2.\n3. `ccccccc` answers round 3.\n\nCloses' in body)
    check('leaves the What list alone', '3. Adds the third thing.' in body and code == 0)
    check('keeps the closing line and footer last', body.endswith('Closes no issue.\n\n' + FOOTER))
    check('reads the body back', 'read back' in out)
    check('saves the body as read', BODY in saved_bodies())

    code, out = revise('--line', '`ccccccc` answers round 3.')
    check('a retry changes nothing', code == 0 and state(5).get('edits') == 1 and 'nothing changed' in out)

    seed(5)
    code, out = revise('--line', '`ddddddd` answers round 2, corrected.', '--replace', '2')
    body = state(5)['body']
    check('replaces only the Revision item with that number', '2. `ddddddd` answers round 2, corrected.' in body and '2. Adds the second thing.' in body and '`bbbbbbb`' not in body)

    code, out = revise('--line', '`ddddddd` answers round 2, corrected.', '--replace', '2')
    check('a retried replacement sends nothing', code == 0 and state(5)['edits'] == 1 and 'nothing changed' in out)

    code, out = revise('--line', 'x', '--replace', '9')
    check('refuses an item the section does not have', code != 0 and 'no item 9' in out)

    wrapped = '## Revision\n\n1. first\n   wrapped\n2. second\n3. third\n\nCloses no issue.\n'
    code, out, pr = result(wrapped, '--line', 'new', '--replace', '1')
    check('replacing an item takes its wrapped line and keeps the next items', '1. new\n2. second\n3. third\n' in pr['body'] and 'wrapped' not in pr['body'])

    code, out, pr = result('## Revision\n\n1. one\n2. two\n   wrapped\n\nCloses no issue.\n', '--line', 'r3')
    check('an add goes after a wrapped last item', '2. two\n   wrapped\n3. r3\n\nCloses' in pr['body'])

    code, out, pr = result('## Revision\n\n1. a\n   1. nested\n2. c\n', '--line', 'x', '--replace', '1')
    check('a nested number is part of its item', pr['body'] == '## Revision\n\n1. x\n2. c\n')

    code, out, pr = result('## Revision\n\n1. a\n   wrapped\n2. b\n', '--line', 'a', '--replace', '1')
    check('a replacement matching only the first line still drops the wrapped line', pr['body'] == '## Revision\n\n1. a\n2. b\n')

    code, out, pr = result('## Revision\n1. a\n2. b\n', '--line', 'a')
    check('a retry finds an item touching the heading', pr.get('edits') is None and 'nothing changed' in out)
    code, out, pr = result('3. third\n## Revision\n\n1. one\n', '--line', 'r2')
    check('a list above the heading does not count', '\n1. one\n2. r2\n' in pr['body'])
    code, out, pr = result('  ## Revision\n\n1. one\n', '--line', 'r2')
    check('refuses an indented heading', code != 0 and 'Edit it by hand' in out and pr.get('edits') is None)

    code, out, pr = result('## Revision\n\n1. a\n1. b\n', '--line', 'a')
    check('refuses two items with one number', code != 0 and 'Edit it by hand' in out and pr.get('edits') is None)

    code, out, pr = result(wrapped, '--line', 'new', '--replace', '3')
    check('replacing the last item stops at the section end', '3. new\n\nCloses no issue.' in pr['body'])

    after = '## Revision\n\n1. one\n2. two\n\n## Notes\n\n1. note one\n2. note two\n'
    code, out, pr = result(after, '--line', 'r3')
    check('an add stops at the next heading', '2. two\n3. r3\n\n## Notes\n\n1. note one\n2. note two\n' in pr['body'])
    code, out, pr = result(after, '--line', 'x', '--replace', '2')
    check('a replacement leaves the next heading list alone', '2. x\n\n## Notes\n\n1. note one\n2. note two\n' in pr['body'])

    code, out, pr = result('## Revision\n\n1. a\n## Notes\n\n1. n\n', '--line', 'r2')
    check('an add stops at a heading directly under an item', pr['body'] == '## Revision\n\n1. a\n2. r2\n## Notes\n\n1. n\n')
    code, out, pr = result('## Revision\n\n1. a\n  ## Notes\n\n1. n\n', '--line', 'r2')
    check('an add stops at an indented heading', pr['body'] == '## Revision\n\n1. a\n2. r2\n  ## Notes\n\n1. n\n')

    code, out, pr = result('## Revision\n\n1. old\nCloses #61\n\n' + FOOTER, '--line', 'new', '--replace', '1')
    check('a replacement keeps a closing line touching the item', '1. new\nCloses #61\n\n🤖' in pr['body'])
    code, out, pr = result('## Revision\n\n1. a\nCloses #1\n', '--line', 'r2')
    check('an add goes above a closing line touching the item', pr['body'] == '## Revision\n\n1. a\n2. r2\nCloses #1\n')
    code, out, pr = result('## Revision\n\n1. a\n' + FOOTER, '--line', 'x', '--replace', '1')
    check('a replacement keeps a footer touching the item', FOOTER in pr['body'])

    para = '## Revision\n\n1. one\n\nFollow-ups:\n\n1. other one\n2. other two\n'
    code, out, pr = result(para, '--line', 'r2')
    check('an add stops at a paragraph after the items', '1. one\n2. r2\n\nFollow-ups:\n\n1. other one\n' in pr['body'])
    code, out, pr = result(para, '--line', 'x', '--replace', '2')
    check('an item past a paragraph is not in the section', code != 0 and 'no item 2' in out and pr.get('edits') is None)

    code, out, pr = result('## Revision\n\nCloses no issue.\n', '--line', 'r1')
    check('fills a section that has no items yet', '## Revision\n\n1. r1\n\nCloses no issue.\n' == pr['body'] and code == 0)

    many = '## Revision\n\n' + numbered(11) + '\n\nCloses no issue.\n'
    code, out, pr = result(many, '--line', 'next')
    check('counts past nine items', '11. `r11` answers round 11.\n12. next\n' in pr['body'])
    code, out, pr = result(many, '--line', 'x', '--replace', '10')
    check('replaces a two-digit item', '10. x\n11. `r11`' in pr['body'] and '`r10`' not in pr['body'])

    code, out, pr = result('## Revision\n\n1. one\n3. three\n', '--line', 'next')
    check('numbers past a gap', '3. three\n4. next\n' in pr['body'])

    code, out, pr = result('## Revision\n\n1. `a` answers round 1, and more.\n', '--line', '`a` answers round 1')
    check('a line that is part of an earlier one is still added', '2. `a` answers round 1\n' in pr['body'])

    seed(6, BARE)
    code, out = revise('--line', '`aaaaaaa` answers round 1.', pull='o/r#6')
    body = state(6)['body']
    check('adds a missing section before the closing line', '## Revision\n\n1. `aaaaaaa` answers round 1.\n\nPart of #33\n\n🤖' in body)
    check('the added section opens with a blank line', '1. Adds the first thing.\n\n## Revision' in body)

    seed(7, '## Why\n\nBecause.\n')
    code, out = revise('--line', '`aaaaaaa` answers round 1.', pull='o/r#7')
    check('adds a missing section to a body with no footer', state(7)['body'] == '## Why\n\nBecause.\n\n## Revision\n\n1. `aaaaaaa` answers round 1.\n' and code == 0)

    code, out, pr = result('## Why', '--line', 'r1')
    check('adds a section to a body with no final newline', pr['body'] == '## Why\n## Revision\n\n1. r1\n'.replace('## Why\n', '## Why\n\n') and code == 0)

    code, out, pr = result('## Why\n\nPart of #33\n\nCloses #43\n\n' + FOOTER, '--line', 'r1')
    check('steps over every closing line', '## Why\n\n## Revision\n\n1. r1\n\nPart of #33\n\nCloses #43\n\n🤖' in pr['body'])
    code, out, pr = result('## Why\n\nCloses #43\nCloses #44\n\n' + FOOTER, '--line', 'r1')
    check('keeps consecutive closing lines together', '1. r1\n\nCloses #43\nCloses #44\n\n🤖' in pr['body'])
    code, out, pr = result('## Why\n\nCloses #43\n', '--line', 'r1')
    check('a closing line with no footer stays last', pr['body'].endswith('1. r1\n\nCloses #43\n'))
    code, out, pr = result('## Why\n\nBecause.\nCloses #1\n', '--line', 'r1')
    check('a closing line touching prose gets a blank line after the section', pr['body'] == '## Why\n\nBecause.\n\n## Revision\n\n1. r1\n\nCloses #1\n')
    for line in ('Closes no issue.', 'Resolves #5', 'Part of o/r#32', 'Close #1', 'Resolved #5', 'Fix #2'):
        code, out, pr = result('## Why\n\n' + line + '\n\n' + FOOTER, '--line', 'r1')
        check(f'{line} stays after an added section', pr['body'].endswith('1. r1\n\n' + line + '\n\n' + FOOTER))
    code, out, pr = result('', '--line', 'r1')
    check('fills an empty body', '## Revision\n\n1. r1\n' in pr['body'] and code == 0)

    code, out, pr = result('## Why\n\nFixes the loop in the reader.\n\n' + FOOTER, '--line', 'r1')
    check('prose that starts like a closing line is not one', 'Fixes the loop in the reader.\n\n## Revision' in pr['body'])
    code, out, pr = result('## Why\n\nFixed #1\n\n' + FOOTER, '--line', 'r1')
    check('reads the past tense of a closing keyword', '1. r1\n\nFixed #1\n' in pr['body'])

    seed(8, BODY.replace('\n', '\r\n'))
    code, out = revise('--line', '`ccccccc` answers round 3.', pull='o/r#8')
    check('adds to a body written with CRLF line endings', '2. `bbbbbbb` answers round 2.\r\n3. `ccccccc` answers round 3.\n\r\nCloses' in state(8)['body'] and code == 0)
    code, out = revise('--line', 'x', '--replace', '1', pull='o/r#8')
    check('replaces an item in a CRLF body', '1. x\n2. `bbbbbbb`' in state(8)['body'])
    code, out = revise('--line', 'x', '--replace', '2', pull='o/r#8')
    code, out = revise('--line', 'x', '--replace', '2', pull='o/r#8')
    check('a retried CRLF replacement sends nothing', state(8)['edits'] == 3 and 'nothing changed' in out)
    code, out, pr = result(BARE.replace('\n', '\r\n'), '--line', 'r1')
    check('adds a section to a CRLF body', '\n## Revision\n\n1. r1\n' in pr['body'] and code == 0)

    seed(9, BODY.replace('## What', '```\n## Revision\n1. example\n```\n\n## What'))
    code, out = revise('--line', '`ccccccc` answers round 3.', pull='o/r#9')
    check('ignores a heading inside a code fence', '```\n## Revision\n1. example\n```' in state(9)['body'] and '3. `ccccccc`' in state(9)['body'])

    fenced = '```\n~~~\n```\n\n## Revision\n\n1. one\n'
    code, out, pr = result(fenced, '--line', 'r2')
    check('a tilde line inside a backtick fence does not end it', '1. one\n2. r2\n' in pr['body'] and pr['body'].count('## Revision') == 1)
    longer = '````\n```\n````\n\n## Revision\n\n1. one\n'
    code, out, pr = result(longer, '--line', 'r2')
    check('a shorter fence inside a longer one does not end it', '1. one\n2. r2\n' in pr['body'])
    tilde = '~~~\n## Revision\n~~~\n\n## Revision\n\n1. one\n'
    code, out, pr = result(tilde, '--line', 'r2')
    check('reads a tilde fence', code == 0 and '1. one\n2. r2\n' in pr['body'])
    code, out, pr = result('```inline```\n\n## Revision\n\n1. one\n', '--line', 'r2')
    check('backticks closed on their own line open no fence', code == 0 and '1. one\n2. r2\n' in pr['body'] and pr['body'].count('## Revision') == 1)
    code, out, pr = result('```\n```x\n## Revision\n1. example\n```\n\n## Revision\n\n1. one\n', '--line', 'r2')
    check('a fence line with text after it closes nothing', code == 0 and '\n1. one\n2. r2\n' in pr['body'] and pr['body'].count('## Revision') == 2)
    code, out, pr = result('~~old~~ text\n\n## Revision\n\n1. one\n', '--line', 'r2')
    check('two tildes open no fence', '1. one\n2. r2\n' in pr['body'] and pr['body'].count('## Revision') == 1)
    code, out, pr = result('  ```\n## Revision\n1. example\n  ```\n\n## Revision\n\n1. one\n', '--line', 'r2')
    check('reads an indented fence', '1. example\n  ```' in pr['body'] and '\n1. one\n2. r2\n' in pr['body'])
    code, out, pr = result('```\nnever closed\n\n## Revision\n\n1. one\n', '--line', 'r2')
    check('refuses a section an unclosed fence hides', code != 0 and 'second run' in out and pr.get('edits') is None)

    seed(10, BODY + '\n## Revision\n\n1. again\n')
    code, out = revise('--line', 'x', pull='o/r#10')
    check('refuses two Revision sections', code != 0 and 'ambiguous' in out and state(10).get('edits') is None)

    code, out, pr = result('## Revision \n\n1. one\n', '--line', 'r2')
    check('reads a heading with a trailing space', code == 0 and '2. r2' in pr['body'] and pr['body'].count('Revision') == 1)
    code, out, pr = result('### Revision\n\n1. one\n', '--line', 'r2')
    check('refuses a heading at another level', code != 0 and 'Edit it by hand' in out and pr.get('edits') is None)

    seed(5)
    code, out = revise('--line', '`ccccccc` answers round 3.', STUB_EDIT_ADDS='changed')
    check('stops when the body read back differs', code != 0 and 'read back differs' in out and state(5)['edits'] == 1)
    before = saved_bodies().count(BODY)
    revise('--line', '`ccccccc` answers round 3.', '--dry-run')
    check('a later run keeps the body saved before the edit', saved_bodies().count(BODY) == before and before > 0)

    seed(5)
    code, out = revise('--line', '`ccccccc` answers round 3.', STUB_LOST='edit')
    check('a lost reply on an edit says the outcome is unknown', code != 0 and 'outcome is unknown' in out and 'As sent' in out)
    code, out = revise('--line', '`ccccccc` answers round 3.')
    check('the retry after a lost reply edits nothing', code == 0 and state(5)['edits'] == 1 and 'nothing changed' in out)

    seed(5)
    code, out = revise('--line', '`ccccccc` answers round 3.', STUB_READ_FAIL='after edit')
    check('a failed read-back says the edit may have landed', code != 0 and 'may have landed' in out and 'As sent' in out)

    seed(5)
    code, out = revise('--line', '`ccccccc` answers round 3.', '--dry-run')
    check('a dry run sends nothing', state(5).get('edits') is None and '+3. `ccccccc`' in out)

    code, out = revise('--line', 'two\nlines')
    check('refuses an entry of two lines', code != 0 and 'one non-empty line' in out)
    code, out = revise('--line', 'two\rlines')
    check('refuses an entry with a carriage return', code != 0 and 'one non-empty line' in out)
    code, out = revise('--line', '  ')
    check('refuses an empty entry', code != 0 and 'one non-empty line' in out and state(5).get('edits') is None)
    code, out = revise('--line', 'x', pull='not-a-spec')
    check('refuses a malformed pull request', code != 0 and 'not OWNER/REPO#N' in out)
    code, out, pr = result(BARE, '--line', 'x', '--replace', '1')
    check('a replacement on a body with no section refuses', code != 0 and 'no ## Revision section' in out and pr.get('edits') is None)

    module = load()
    check('the second check finds a line changed before the section',
          module.changed_outside(BODY, BODY.replace('2. Adds the second thing.', '2. Overwritten.')))
    check('the second check finds a line changed after the section',
          module.changed_outside(BODY, BODY.replace('Closes no issue.', 'Closes #1')))
    check('the second check passes a change inside the section',
          not module.changed_outside(BODY, BODY.replace('`bbbbbbb`', '`ddddddd`')))
    check('the second check passes an item added at the end of the section',
          not module.changed_outside(BODY, BODY.replace('round 2.\n', 'round 2.\n3. `c` answers round 3.\n')))
    check('the second check finds a line added above the heading',
          module.changed_outside(BODY, BODY.replace('## Revision', 'extra\n## Revision')))
    check('the second check finds the heading changed',
          module.changed_outside(BODY, BODY.replace('## Revision', '## Revisions')))
    check('the second check finds the closing line deleted',
          module.changed_outside(BODY, BODY.replace('Closes no issue.\n\n', '')))
    check('the second check passes a section added to a bare body',
          not module.changed_outside(BARE, module.splice(BARE, 'r1', None)))
    check('the second check finds a bare body changed elsewhere',
          module.changed_outside(BARE, BARE.replace('Because.', 'Why not.')))

    check('the second check finds a last line changed with no final newline',
          module.changed_outside('## Revision\n\n1. a\n\nCloses #1', '## Revision\n\n1. a\n\nCloses #2'))
    check('the second check finds a first line changed',
          module.changed_outside('## Why\n\n## Revision\n\n1. a\n', '## Who\n\n## Revision\n\n1. a\n'))
    check('the second check finds a closing line touching the last item changed',
          module.changed_outside('## Revision\n\n1. a\nCloses #1\n', '## Revision\n\n1. a\nCloses #2\n'))

    done = BODY.split('\n')
    start, end = module.find_section(done)
    check('the section ends at its last item', done[start] == '## Revision' and done[end - 1].startswith('2. `bbbbbbb`'))

    seed(5)
    bad = module.splice
    module.splice = lambda body, text, replace: body.replace('2. Adds the second thing.', '2. Overwritten.')
    stub_line = os.path.join(ROOT, 'stub-line.txt')
    with open(stub_line, 'w') as f:
        f.write('x')
    args = argparse.Namespace(pull='o/r#5', scratch=SCRATCH, file=stub_line, replace=None, dry_run=False)
    old_path, os.environ['PATH'] = os.environ['PATH'], BIN + os.pathsep + os.environ['PATH']
    os.environ['STUB_STATE'] = STATE
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            module.revision(args)
        refused = ''
    except SystemExit as stop:
        refused = str(stop)
    finally:
        os.environ['PATH'] = old_path
        module.splice = bad
    check('a splice that writes outside the section is refused before sending', 'outside ## Revision' in refused and state(5).get('edits') is None)

    A, B = 'b' * 7, 'c' * 7
    note = os.path.join(ROOT, 'note.md')
    with open(note, 'w') as f:
        f.write(f'## Review, round 3\n\nRound 3, of `{A}`, fixed in `{"a" * 7}`.\n')
    other = os.path.join(ROOT, 'other.md')
    with open(other, 'w') as f:
        f.write(f'## Review, round 3\n\nRound 3, of `{B}`, on the companion, fixed in `{"d" * 7}`.\n')
    head5, head6 = 'a' * 40, 'd' * 40

    def post(*targets, round_no='3', **env):
        return run('comment', '--round', round_no, *targets, **env)

    MAIN, COMP = f'o/r#5={head5}={A}={note}', f'o/s#6={head6}={B}={other}'

    seed(5, head=head5), seed(6, head=head6, repo='o-s')
    code, out = post(MAIN, COMP)
    check('posts on every pull request', code == 0 and len(state(5)['comments']) == 1 and len(state(6, 'o-s')['comments']) == 1)
    check('prints where each comment landed', 'issuecomment-1' in out)

    code, out = post(MAIN, COMP)
    check('a retry across companions on different anchors posts nothing twice', len(state(5)['comments']) == 1 and len(state(6, 'o-s')['comments']) == 1 and out.count('skipped') == 2)

    seed(5, head=head5), seed(6, head=head6, repo='o-s')
    moved = os.path.join(ROOT, 'moved.md')
    with open(moved, 'w') as f:
        f.write(f'## Review, round 3\n\nRound 3, of `{B}`, fixed in `{"e" * 7}`.\n')
    code, out = post(MAIN, f'o/s#6={"e" * 40}={B}={moved}')
    check('posts on no companion when one head differs', code != 0 and state(5)['comments'] == [] and state(6, 'o-s')['comments'] == [])
    check('names the head that differs', f'o/s#6 is at {head6[:7]}' in out)

    code, out = post(f'o/r#5={head5[:7]}={A}={note}')
    check('takes a seven-character head', code == 0 and len(state(5)['comments']) == 1)
    seed(5, head=head5)
    code, out = post(f'o/r#5={head5[:6]}={A}={note}')
    check('refuses a six-character head', code != 0 and 'OWNER/REPO#N=HEAD=ANCHOR=FILE' in out and state(5)['comments'] == [])
    code, out = post(f'o/r#5={head5}=={note}')
    check('refuses an empty anchor', code != 0 and 'OWNER/REPO#N=HEAD=ANCHOR=FILE' in out)

    seed(5, head=head5, comments=[f'## Review, round 3\n\nRound 3, of `{"e" * 7}`.\n'])
    code, out = post(MAIN)
    check('a comment on another anchor does not block the post', len(state(5)['comments']) == 2)

    closing = os.path.join(ROOT, 'closing.md')
    with open(closing, 'w') as f:
        f.write(f'## Review complete\n\nCloses round 3, of `{A}`, at `{"a" * 7}`.\n')
    seed(5, head=head5, comments=[f'## Review complete\n\nCloses round 2, of `{A}`.\n'])
    code, out = post(f'o/r#5={head5}={A}={closing}')
    check('a comment on another round does not block the post', len(state(5)['comments']) == 2)

    round13 = os.path.join(ROOT, 'round13.md')
    with open(round13, 'w') as f:
        f.write(f'## Review complete\n\nRound 1, of `{A}`, at `{"a" * 7}`.\n')
    seed(5, head=head5, comments=[f'## Review complete\n\nRound 13, of `{A}`.\n'])
    code, out = post(f'o/r#5={head5}={A}={round13}', round_no='1')
    check('round 1 does not match a comment on round 13', code == 0 and len(state(5)['comments']) == 2)

    seed(5, head=head5, comments=[f'## Review, round 2\n\nRound 3, of `{A}`.\n'])
    code, out = post(MAIN)
    check('a comment under another heading does not block the post', len(state(5)['comments']) == 2)

    seed(5, head=head5)
    code, out = post(f'o/r#5={head5}={A}={closing}')
    code, out = post(f'o/r#5={head5}={A}={closing}')
    check('a retry under the final heading posts once, with the round capitalised or not', len(state(5)['comments']) == 1 and 'skipped' in out)

    long_anchor = os.path.join(ROOT, 'long.md')
    with open(long_anchor, 'w') as f:
        f.write(f'## Review, round 3\n\nRound 3, of `{A}`, fixed in `{"a" * 7}`.\n')
    seed(5, head=head5)
    post(f'o/r#5={head5}={A + "b" * 33}={long_anchor}')
    code, out = post(f'o/r#5={head5}={A + "b" * 33}={long_anchor}')
    check('a full anchor matches a comment naming seven characters', len(state(5)['comments']) == 1 and 'skipped' in out)

    seed(5, head=head5, comments=[f'## Review, round 3\n\nRound 3, of `{A}`, fixed in `{"a" * 7}`.\n'], login='stranger')
    code, out = post(MAIN)
    check("another login's comment does not stop the post", code == 0 and len(state(5)['comments']) == 2 and 'posted' in out)

    seed(5, head=head5, comments=[f'## Review, round 3\n\nRound 3, of `{A}`, earlier text.\n'])
    seed(6, head=head6, repo='o-s')
    code, out = post(MAIN, COMP)
    check('a key with other text stops every post', code != 0 and 'different text' in out and len(state(5)['comments']) == 1 and state(6, 'o-s')['comments'] == [])

    wrong_head = os.path.join(ROOT, 'wrong.md')
    with open(wrong_head, 'w') as f:
        f.write(f'## Review complete\n\nRound 3, of `{A}`, at `{"a" * 7}`.\n')
    seed(5, head=head5), seed(6, head=head6, repo='o-s')
    with open(wrong_head, 'w') as f:
        f.write(f'Round 3, of `{A}`, at `{"a" * 7}`.\n')
    code, out = post(COMP, f'o/r#5={head5}={A}={wrong_head}')
    check('refuses a file that does not open with a heading', code != 0 and 'does not start with' in out and state(6, 'o-s')['comments'] == [])
    blank = os.path.join(ROOT, 'blank.md')
    with open(blank, 'w') as f:
        f.write(f'\n## Review, round 3\n\nRound 3, of `{A}`, at `{"a" * 7}`.\n')
    code, out = post(f'o/r#5={head5}={A}={blank}')
    check('refuses a file with a leading blank line', code != 0 and state(5)['comments'] == [])
    code, out = post(f'o/r#5={head5}={B}={note}')
    check('refuses a file that names another anchor', code != 0 and state(5)['comments'] == [])
    code, out = post(MAIN, round_no='4')
    check('refuses a file that names another round', code != 0 and state(5)['comments'] == [])

    seed(5, head=head5), seed(6, head=head6, repo='o-s')
    code, out = post(MAIN, COMP, STUB_COMMENT_FAIL='6')
    check('a failed post stops and says the outcome is unknown', code != 0 and 'outcome is unknown' in out and len(state(5)['comments']) == 1)
    code, out = post(MAIN, COMP)
    check('the retry posts only what is missing', len(state(5)['comments']) == 1 and len(state(6, 'o-s')['comments']) == 1)

    seed(5, head=head5)
    code, out = post(MAIN, STUB_LOST='comment')
    check('a lost reply on a post says the outcome is unknown', code != 0 and 'outcome is unknown' in out)
    code, out = post(MAIN)
    check('the retry after a lost reply posts nothing more', len(state(5)['comments']) == 1 and 'skipped' in out)

    code, out = post(f'o/r#5={head5}={A}={os.path.join(ROOT, "missing.md")}')
    check('refuses a comment file that does not exist', code != 0 and 'no comment file' in out)
    empty = os.path.join(ROOT, 'empty.md')
    open(empty, 'w').close()
    code, out = post(f'o/r#5={head5}={A}={empty}')
    check('refuses an empty comment file', code != 0 and 'does not start with' in out and 'Traceback' not in out)
    stale = os.path.join(ROOT, 'stale.md')
    with open(stale, 'w') as f:
        f.write(f'## Review, round 3\n\nRound 3, of `{A}`, fixed in `{"e" * 7}`.\n')
    seed(5, head=head5)
    code, out = post(f'o/r#5={head5}={A}={stale}')
    check('refuses a file that does not name the head', code != 0 and 'does not name the head' in out and state(5)['comments'] == [])
    code, out = post(f'o/r#5={head5}={A[:6]}={note}')
    check('refuses a six-character anchor', code != 0 and 'OWNER/REPO#N=HEAD=ANCHOR=FILE' in out)
    seed(5, head=head5)
    code, out = post(MAIN, MAIN)
    check('refuses one pull request named twice', code != 0 and 'named twice' in out and state(5)['comments'] == [])
    code, out = post(MAIN, f'O/R#05={head5}={A}={note}')
    check('refuses one pull request written two ways', code != 0 and 'named twice' in out and state(5)['comments'] == [])
    copy = f'## Review, round 3\n\nRound 3, of `{A}`, fixed in `{"a" * 7}`.\n'
    seed(5, head=head5, comments=[copy, copy])
    code, out = post(MAIN)
    check('reports a double post already there', code != 0 and 'should hold this comment once' in out and len(state(5)['comments']) == 2)
    seed(5, head=head5, comments=[copy, copy]), seed(6, head=head6, repo='o-s')
    code, out = post(MAIN, COMP)
    check('a double post on one companion does not stop the other', code != 0 and 'o/r#5' in out and len(state(6, 'o-s')['comments']) == 1 and len(state(5)['comments']) == 2)
    seed(5, head=head5)
    code, out = post(MAIN, STUB_DOUBLE='5')
    check('a post that landed twice is reported', code != 0 and 'should hold this comment once' in out and 'posted' in out)
    seed(5, head=head5, comments=[copy])
    pr5 = state(5)
    pr5['comments'][0]['author'] = None
    with open(os.path.join(STATE, 'o-r-5.json'), 'w') as f:
        json.dump(pr5, f)
    code, out = post(MAIN)
    check('a comment from a deleted account does not stop the post', code == 0 and len(state(5)['comments']) == 2)
    seed(5, head=head5, comments=[copy])
    code, out = post(MAIN, STUB_READ_FAIL='api user')
    check('a failed login read stops with the gh call named', code != 0 and 'failed' in out and len(state(5)['comments']) == 1)
    seed(5, head=head5)
    code, out = post(MAIN, STUB_READ_FAIL='pr view')
    check('a failed pull request read stops with the gh call named', code != 0 and 'failed' in out and state(5)['comments'] == [])

    code, out = post('not-a-target')
    check('refuses a malformed target', code != 0 and 'OWNER/REPO#N=HEAD=ANCHOR=FILE' in out)

    seed(5, head=head5)
    code, out = post(MAIN, '--dry-run')
    check('a dry run posts nothing', state(5)['comments'] == [] and 'would post' in out)

sys.exit(1 if failures else 0)
