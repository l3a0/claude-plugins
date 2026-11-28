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
if os.environ.get('STUB_READ_FAIL') == 'after edit' and args[1] == 'view' and len(args) > 4 and \
        os.path.exists(os.path.join(state, args[4].replace('/', '-') + '-' + args[2] + '.json')) and \
        json.load(open(os.path.join(state, args[4].replace('/', '-') + '-' + args[2] + '.json'))).get('edits'):
    sys.exit('stand-in gh: 502')
if args[:2] == ['api', 'user']:
    if args[2:4] != ['--jq', '.login']: fail()
    print(login)
    sys.exit(0)
if args[:3] == ['api', 'graphql', '--paginate']:
    # GitHub's record of force pushes on one pull request: the head each one replaced, one per line, as --jq prints
    # it. A replaced head GitHub no longer holds has no beforeCommit, so the filter prints nothing for it.
    if os.environ.get('STUB_GRAPHQL_FAIL'): sys.exit('stand-in gh: 502 from graphql')
    flags = dict(zip(args[3::2], args[4::2]))
    if len(args) != 13 or args[3::2] != ['-f', '-f', '-f', '-F', '--jq']: fail()
    query = args[4]
    if not query.startswith('query=') or 'HEAD_REF_FORCE_PUSHED_EVENT' not in query or '$endCursor' not in query \
            or 'pageInfo { hasNextPage endCursor }' not in query or 'beforeCommit { oid }' not in query: fail()
    owner, name, num = args[6], args[8], args[10]
    if not (owner.startswith('owner=') and name.startswith('name=') and num.startswith('num=')): fail()
    if args[12] != '.data.repository.pullRequest.timelineItems.nodes[].beforeCommit.oid // empty': fail()
    path = os.path.join(state, owner[6:] + '-' + name[5:] + '-' + num[4:] + '.json')
    if not os.path.exists(path): fail()
    for push in json.load(open(path)).get('replaced', []):
        if not push.get('collected'): print(push['before'])
    sys.exit(0)
if args[0] == 'api' and args[1].startswith('repos/') and '/branches/' in args[1]:
    # GitHub's branches API, read for a branch's tip. Like the real gh and GitHub, a raw "#" or "?" ends the
    # path, a percent escape is decoded, and ".." is resolved, so the name answered can differ from the one asked.
    import posixpath, urllib.parse
    if args[2:] != ['--jq', '.name, .commit.sha']: fail()
    repo, branch = args[1][len('repos/'):].split('/branches/', 1)
    branch = posixpath.normpath(urllib.parse.unquote(branch.split('#')[0].split('?')[0]))
    tips = json.load(open(os.path.join(state, 'branches.json'))) if os.path.exists(os.path.join(state, 'branches.json')) else {}
    if branch not in tips.get(repo, {}): sys.exit('gh: Branch not found (HTTP 404)')
    tip = tips[repo][branch]
    print(tip['out'] if isinstance(tip, dict) else branch + '\\n' + tip)
    sys.exit(0)
if args[0] == 'api' and args[1].startswith('repos/') and '/compare/' in args[1]:
    # GitHub's compare API: "ahead" when the head descends from the anchor, 404 for a commit the repository lacks.
    # Paged, --jq prints the status and the count again at the top of each page, which STUB_PAGES repeats, and
    # STUB_SECOND_STATUS gives the second page a status of its own.
    if args[2:] != ['--paginate', '--jq', '.status, .ahead_by, .commits[].sha'] or not args[1].endswith('?per_page=100'): fail()
    repo, span = args[1][len('repos/'):-len('?per_page=100')].split('/compare/')
    anchor, head = span.split('...')
    prefix = repo.replace('/', '-') + '-'
    # Several seeded pull requests share a head, so the one seeded last answers.
    names = [n for n in os.listdir(state) if n.startswith(prefix) and n.endswith('.json')]
    for name in sorted(names, key=lambda n: os.stat(os.path.join(state, n)).st_mtime_ns, reverse=True):
        pr = json.load(open(os.path.join(state, name)))
        for push in pr.get('replaced', []):
            # A head a force push replaced: "ahead" for a commit it holds, with that head as the one commit after it,
            # "behind" for one that descends from it, "diverged" for any other, and 404 once GitHub no longer holds it.
            if push['before'] != head: continue
            if push.get('gone'): sys.exit('gh: Not Found (HTTP 404)')
            if any(c.startswith(anchor) for c in push.get('descendants', [])):
                print('behind')
            elif any(c.startswith(anchor) for c in push.get('ancestors', [])):
                print('ahead'), print(1), print(head)
            else:
                print('diverged')
            sys.exit(0)
        if pr['headRefOid'] != head: continue
        if any(c.startswith(anchor) for c in pr.get('ancestors', [])):
            later = pr.get('later_than', {}).get(anchor, [head])
            pages = int(os.environ.get('STUB_PAGES', '1'))
            for page in range(pages):
                print(os.environ.get('STUB_SECOND_STATUS', 'ahead') if page else 'ahead')
                print(os.environ.get('STUB_AHEAD_BY', len(later)))
                for c in later[page::pages]: print(c)
        elif any(c.startswith(anchor) for c in pr.get('elsewhere', [])):
            print('diverged')
        elif any(c.startswith(anchor) for c in pr.get('later', [])):
            print('behind')
        elif any(c.startswith(anchor) for c in pr.get('silent', [])):
            print('')
        elif any(c.startswith(anchor) for c in pr.get('twins', [])):
            print('identical')
        else:
            sys.exit('gh: Not Found (HTTP 404)')
        sys.exit(0)
    fail()
if args[0] not in ('pr', 'issue') or args[3] != '-R': fail()
path = os.path.join(state, ('issue-' if args[0] == 'issue' else '') + args[4].replace('/', '-') + '-' + args[2] + '.json')
if not os.path.exists(path): fail()
pr = json.load(open(path))
if args[1] == 'view' and args[5] == '--json' and args[6] == 'closingIssuesReferences' and os.environ.get('STUB_CLOSES_FAIL') and pr.get('edits'):
    sys.exit('stand-in gh: 502 on closingIssuesReferences')
if args[1] == 'view' and args[5] == '--json' and args[6] == 'closingIssuesReferences':
    # GitHub's own reading of closing keywords, approximated: a keyword, an optional colon, then #N, outside fences.
    import re
    text, fence = [], False
    source, lagged = pr['body'], False
    # STUB_LAG stands for GitHub re-reading a body some time after an edit: that many reads still see the body before it.
    if os.environ.get('STUB_LAG') and pr.get('edits') and pr.get('lag_reads', 0) < int(os.environ['STUB_LAG']):
        source, lagged = pr['prev_body'], True
        pr['lag_reads'] = pr.get('lag_reads', 0) + 1
        json.dump(pr, open(path, 'w'))
    for line in source.split(chr(10)):
        if line.lstrip().startswith('```'):
            fence = not fence
        elif not fence:
            text.append(re.sub('`[^`]*`', '', line))
    found = re.findall('(?i)(?:^|[^A-Za-z0-9_])(?:close[sd]?|fix(?:es|ed)?|resolve[sd]?):?[ ]+((?:[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)?)#([0-9]+)', chr(10).join(text))
    nums = [n for r, n in found if not r]
    others = [(r, n) for r, n in found if r]
    # STUB_LOSE stands for a form GitHub reads that the script's patterns miss: closed before the edit, not after.
    if os.environ.get('STUB_LOSE') and not pr.get('edits'):
        nums.append(os.environ['STUB_LOSE'])
    # STUB_GAIN stands for a form GitHub reads that the script's patterns miss: closed after the edit, not before.
    if os.environ.get('STUB_GAIN') and pr.get('edits') and not lagged:
        nums.append(os.environ['STUB_GAIN'])
    owner, name = args[4].split('/')
    refs = [{'number': int(n), 'repository': {'name': name, 'owner': {'login': owner}}} for n in dict.fromkeys(nums)]
    refs += [{'number': int(n), 'repository': {'name': r.split('/')[1], 'owner': {'login': r.split('/')[0]}}} for r, n in dict.fromkeys(others)]
    # STUB_LOSE_OTHER names another repository's issue that only the body before the edit closes.
    if os.environ.get('STUB_LOSE_OTHER') and not pr.get('edits'):
        o, rest = os.environ['STUB_LOSE_OTHER'].split('/')
        n_, num_ = rest.split('#')
        refs.append({'number': int(num_), 'repository': {'name': n_, 'owner': {'login': o}}})
    print(json.dumps({'closingIssuesReferences': refs}))
    sys.exit(0)
if args[1] == 'view' and args[5] == '--json':
    hide = os.path.join(state, 'hide')
    if args[6] == 'comments' and os.path.exists(hide):
        # A read that lags behind a write leaves out the comment just posted, once.
        gone = open(hide).read()
        os.remove(hide)
        print(json.dumps({'comments': [c for c in pr['comments'] if c.get('url') != gone]}))
    else:
        print(json.dumps({args[6]: pr[args[6]]}))
        # STUB_OWNER_EDIT stands for the owner editing the body after the script's first read of it.
        if args[6] == 'body' and os.environ.get('STUB_OWNER_EDIT') and not pr.get('owner_edit'):
            pr['body'] += os.environ['STUB_OWNER_EDIT']
            pr['owner_edit'] = True
            json.dump(pr, open(path, 'w'))
elif args[1] == 'edit' and args[5] == '--body-file' and args[0] == 'pr':
    pr['prev_body'] = pr['body']
    pr['lag_reads'] = 0
    pr['body'] = open(args[6], newline='').read() + os.environ.get('STUB_EDIT_ADDS', '')
    pr['edits'] = pr.get('edits', 0) + 1
    json.dump(pr, open(path, 'w'))
    if os.environ.get('STUB_LOST') == 'edit': sys.exit('stand-in gh: connection lost')
elif args[1] == 'comment' and args[5] == '--body-file':
    if os.environ.get('STUB_COMMENT_FAIL') == args[2]: sys.exit('stand-in gh: comment refused')
    # Like GitHub, each comment gets a link whose number rises with every post.
    counter = os.path.join(state, 'counter')
    def landed(body):
        n = int(open(counter).read()) + 1 if os.path.exists(counter) else 1001
        open(counter, 'w').write(str(n))
        url = 'https://github.com/' + args[4] + ('/issues/' if args[0] == 'issue' else '/pull/') + args[2] + '#issuecomment-' + str(n)
        pr['comments'].append({'author': {'login': login}, 'body': body, 'url': url})
        json.dump(pr, open(path, 'w'))
        return url
    posted = landed(open(args[6], newline='').read())
    if os.environ.get('STUB_HIDE') == args[2]:
        open(os.path.join(state, 'hide'), 'w').write(posted)
    if os.environ.get('STUB_DOUBLE') == args[2]:
        landed(open(args[6], newline='').read())
    if os.environ.get('STUB_RACE') == args[2]:
        # Another run's comment under the same key lands as this one does, with other text.
        landed(open(args[6], newline='').read().rstrip('\\n') + ' Another session.\\n')
    if os.environ.get('STUB_LOST') == 'comment': sys.exit('stand-in gh: connection lost')
    print(posted)
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

    # Every anchor the comment tests name, bbbbbbb and ccccccc, is an ancestor of the head unless a test says otherwise.
    def seed(num, body=BODY, head='a' * 40, comments=(), repo='o-r', login='me', ancestors=('b' * 40, 'c' * 40),
             elsewhere=(), later=(), silent=(), twins=(), later_than=None, replaced=()):
        # later_than maps an anchor to the commits the head holds after it, which is the head alone unless given.
        with open(os.path.join(STATE, f'{repo}-{num}.json'), 'w') as f:
            json.dump({'body': body, 'headRefOid': head, 'ancestors': list(ancestors), 'elsewhere': list(elsewhere), 'later': list(later), 'silent': list(silent), 'twins': list(twins),
                       'later_than': later_than or {}, 'replaced': list(replaced),
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
    seed(5)
    for marked in ('1. `ccccccc` answers round 3.', '12. x', '1) x', '- x', '* x', '+ x', '3.'):
        code, out = revise('--line', marked)
        check(f'refuses a line that starts with its own list marker: {marked!r}',
              code != 0 and 'list marker' in out and 'Remove the marker' in out and state(5).get('edits') is None)
    code, out = revise('--line', '2026-11-26 fixes `ccccccc`.', '--dry-run')
    check('takes a line that starts with a number that is not a list marker', code == 0 and '+3. 2026-11-26' in out)
    code, out = revise('--line', '**Round 3**, `ccccccc`.', '--dry-run')
    check('takes a line that starts with bold text', code == 0 and '+3. **Round 3**' in out)
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

    # outside_history keeps returning only the reason, because a caller tests it with `if (why := ...)`.
    real_compare = module.compare_range
    try:
        module.compare_range = lambda repo, anchor, head: (None, ['c' * 40])
        passed = module.outside_history('o/r', 'b' * 7, 'a' * 40)
        module.compare_range = lambda repo, anchor, head: ('the head is diverged', [])
        refused = module.outside_history('o/r', 'b' * 7, 'a' * 40)
    finally:
        module.compare_range = real_compare
    check('outside_history returns None for an anchor in the history, not a tuple', passed is None)
    check('outside_history returns the reason alone for an anchor outside it', refused == 'the head is diverged')

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
    check('prints where each comment landed', state(5)['comments'][0]['url'] in out and state(6, 'o-s')['comments'][0]['url'] in out)

    code, out = post(MAIN, COMP)
    check('a retry across companions on different anchors posts nothing twice', len(state(5)['comments']) == 1 and len(state(6, 'o-s')['comments']) == 1 and out.count('skipped') == 2)

    seed(5, head=head5), seed(6, head=head6, repo='o-s')
    moved = os.path.join(ROOT, 'moved.md')
    with open(moved, 'w') as f:
        f.write(f'## Review, round 3\n\nRound 3, of `{B}`, fixed in `{"e" * 7}`.\n')
    code, out = post(MAIN, f'o/s#6={"e" * 40}={B}={moved}')
    check('posts on no companion when one head differs', code != 0 and state(5)['comments'] == [] and state(6, 'o-s')['comments'] == [])
    check('names the head that differs in seven characters', f'o/s#6 is at {head6[:7]}, not {"e" * 7}' in out)
    six = os.path.join(ROOT, 'six.md')
    with open(six, 'w') as f:
        f.write(f'## Review, round 3\n\nRound 3, of `{B}`, fixed in `{"d" * 6}e`.\n')
    code, out = post(MAIN, f'o/s#6={"d" * 6 + "e" * 34}={B}={six}')
    check('names heads that share six characters in seven characters each', code != 0
          and 'o/s#6 is at ddddddd, not dddddde' in out
          and state(6, 'o-s')['comments'] == [])
    near = os.path.join(ROOT, 'near.md')
    with open(near, 'w') as f:
        f.write(f'## Review, round 3\n\nRound 3, of `{B}`, fixed in `{"d" * 7}`.\n')
    code, out = post(MAIN, f'o/s#6={"d" * 7 + "e" * 33}={B}={near}')
    check('refuses a head that shares its first seven characters with the real head, and names both in full',
          code != 0 and f'is at {head6}, not {"d" * 7 + "e" * 33}' in out
          and state(5)['comments'] == [] and state(6, 'o-s')['comments'] == [])

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
    check('a key with other text stops every post', code != 0 and 'different text' in out
          and 'checks review-round.md\'s step 7 gives for a hand post' in out and len(state(5)['comments']) == 1 and state(6, 'o-s')['comments'] == [])

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
    check('a double post with no comment numbers names no copy to delete', 'Delete nothing' in out and 'Keep ' not in out)
    seed(5, head=head5, comments=[copy, copy]), seed(6, head=head6, repo='o-s')
    code, out = post(MAIN, COMP)
    check('a double post on one companion does not stop the other', code != 0 and 'o/r#5' in out and len(state(6, 'o-s')['comments']) == 1 and len(state(5)['comments']) == 2)
    seed(5, head=head5)
    code, out = post(MAIN, STUB_DOUBLE='5')
    check('a post that landed twice is reported', code != 0 and 'should hold this comment once' in out and 'posted' in out)
    first, second = (c['url'] for c in state(5)['comments'])
    check('a post that landed twice names the copy with the lowest comment number to keep', f'Keep {first}' in out and f'delete {second}' in out)
    seed(5, head=head5)
    with open(os.path.join(STATE, 'o-r-5.json')) as f:
        held = json.load(f)
    body = open(note).read()
    held['comments'] = [{'author': {'login': 'me'}, 'body': body, 'url': 'https://github.com/o/r/pull/5#issuecomment-1000'},
                        {'author': {'login': 'me'}, 'body': body, 'url': 'https://github.com/o/r/pull/5#issuecomment-999'}]
    with open(os.path.join(STATE, 'o-r-5.json'), 'w') as f:
        json.dump(held, f)
    code, out = post(MAIN)
    check('the copy to keep is the lowest comment number, not the first in text order', code != 0
          and 'Keep https://github.com/o/r/pull/5#issuecomment-999' in out and 'delete https://github.com/o/r/pull/5#issuecomment-1000' in out)
    seed(5, head=head5)
    code, out = post(MAIN, STUB_HIDE='5')
    link = state(5)['comments'][0]['url']
    check('a post the read after posting does not show says to rerun nothing', code != 0 and 'Rerun nothing' in out
          and f'the read after posting {link} shows none' in out and len(state(5)['comments']) == 1)
    seed(5, head=head5)
    code, out = post(MAIN, STUB_RACE='5')
    check('a post that lands beside a copy with other text deletes nothing', code != 0 and 'Delete and edit nothing' in out
          and 'Keep ' not in out and len(state(5)['comments']) == 2)
    seed(5, head=head5)
    code, out = post(MAIN, STUB_HIDE='5')
    check('a post the next read does not show is reported', code != 0 and 'should hold this comment once' in out and 'posted' in out)
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

    # The anchor must be the head or an ancestor of it. Round 8 of l3a0/ithildin-runtime PR #238 posted with another
    # round's anchor, which this check does not catch, because that anchor was an ancestor too. The tests after these
    # cover the check that does.
    seed(5, head=head5)
    code, out = post(MAIN)
    check('posts with an anchor that is an ancestor of the head', code == 0 and len(state(5)['comments']) == 1)

    at_head = os.path.join(ROOT, 'at-head.md')
    with open(at_head, 'w') as f:
        f.write(f'## Review, round 3\n\nRound 3, of `{"a" * 7}`, at `{"a" * 7}`.\n')
    seed(5, head=head5, ancestors=())
    code, out = post(f'o/r#5={head5}={"a" * 7}={at_head}')
    check('posts with an anchor that is the head itself', code == 0 and len(state(5)['comments']) == 1)

    F = 'f' * 7
    unrelated = os.path.join(ROOT, 'unrelated.md')
    with open(unrelated, 'w') as f:
        f.write(f'## Review, round 3\n\nRound 3, of `{F}`, fixed in `{"a" * 7}`.\n')
    seed(5, head=head5, elsewhere=('f' * 40,)), seed(6, head=head6, repo='o-s')
    code, out = post(COMP, f'o/r#5={head5}={F}={unrelated}')
    check('refuses an anchor on another branch, and posts on no companion', code != 0
          and 'an anchor was not shown to be the head or an ancestor' in out and 'is diverged against the anchor' in out
          and 'no force push GitHub records on this pull request replaced a head that holds it' in out
          and 'none of ahead' not in out and f'o/r#5' in out
          and 'post nothing by hand' in out
          and state(5)['comments'] == [] and state(6, 'o-s')['comments'] == [])

    twin = 'a' * 7 + 'b' * 33
    seed(5, head=head5, elsewhere=(twin,))
    code, out = post(f'o/r#5={head5}={twin}={at_head}')
    check('refuses an anchor that shares the head\'s first seven characters but is another commit', code != 0
          and 'is diverged against the anchor' in out and 'none of ahead' not in out and state(5)['comments'] == [])

    seed(5, head=head5, twins=('f' * 40,))
    code, out = post(f'o/r#5={head5}={F}={unrelated}')
    check('refuses an anchor GitHub compares as identical to another head', code != 0
          and 'GitHub answered identical' in out and 'not in its history' not in out and state(5)['comments'] == [])

    seed(5, head=head5, later=('f' * 40,))
    code, out = post(f'o/r#5={head5}={F}={unrelated}')
    check('refuses an anchor that comes after the head when no force push is recorded', code != 0
          and 'is behind against the anchor' in out and 'none of ahead' not in out and state(5)['comments'] == [])

    # A force push, such as a rebase, which the script cannot tie to who pushed it, drops an anchor a round already read.
    # GitHub's timeline records the head each force push replaced, so an anchor that head held still stands, and one
    # copied from another pull request does not.
    G, H = '9' * 40, '8' * 40
    pushed = dict(head=head5, elsewhere=('f' * 40,), replaced=({'before': G, 'ancestors': []},))
    seed(5, **dict(pushed, replaced=({'before': 'f' * 40},)))
    code, out = post(f'o/r#5={head5}={F}={unrelated}')
    check('posts with an anchor that was itself the head a recorded force push replaced, and says so', code == 0
          and len(state(5)['comments']) == 1 and 'GitHub records a force push on this pull request that replaced the '
          f'head {F}, which holds it, so the anchor stands' in out and "review-round.md's step 1" in out)
    seed(5, **dict(pushed, replaced=({'before': G, 'ancestors': ['f' * 40]},)))
    code, out = post(f'o/r#5={head5}={F}={unrelated}')
    check('posts with an anchor in the history of a head a recorded force push replaced', code == 0
          and len(state(5)['comments']) == 1 and f'replaced the head {G[:7]}, which holds it' in out)
    seed(5, **dict(pushed, later=('f' * 40,), elsewhere=(), replaced=({'before': G, 'ancestors': ['f' * 40]},)))
    code, out = post(f'o/r#5={head5}={F}={unrelated}')
    check('posts with an anchor that comes after the head where a recorded force push replaced a head holding it',
          code == 0 and len(state(5)['comments']) == 1 and 'the anchor stands' in out)
    seed(5, **dict(pushed, replaced=({'before': G, 'ancestors': ['e' * 40]}, {'before': H, 'ancestors': []})))
    code, out = post(f'o/r#5={head5}={F}={unrelated}')
    check('refuses an anchor no replaced head holds, as for one copied from another pull request', code != 0
          and 'no force push GitHub records on this pull request replaced a head that holds it' in out
          and 'the anchor stands' not in out and state(5)['comments'] == [])
    seed(5, **dict(pushed, replaced=({'before': G, 'ancestors': ['f' * 40], 'collected': True},)))
    code, out = post(f'o/r#5={head5}={F}={unrelated}')
    check('refuses where the replaced head that held the anchor has no commit on record', code != 0
          and 'no force push GitHub records' in out and state(5)['comments'] == [])
    seed(5, **dict(pushed, replaced=({'before': G, 'descendants': ['f' * 40]},)))
    code, out = post(f'o/r#5={head5}={F}={unrelated}')
    check('refuses an anchor that descends from a replaced head, as from a pull request stacked on it', code != 0
          and 'no force push GitHub records' in out and state(5)['comments'] == [])
    seed(5, **dict(pushed, replaced=({'before': G, 'gone': True}, {'before': H, 'ancestors': []})))
    code, out = post(f'o/r#5={head5}={F}={unrelated}')
    check('refuses and names a replaced head GitHub can no longer compare', code != 0
          and f"compare of the anchor with the replaced head {G[:7]} gave no usable answer" in out and 'Not Found' in out
          and f'replaced head {H[:7]}' not in out and state(5)['comments'] == [])
    # Where one replaced head is gone and another holds the anchor, the anchor stands through the one that holds it.
    seed(5, **dict(pushed, replaced=({'before': G, 'gone': True}, {'before': H, 'ancestors': ['f' * 40]})))
    code, out = post(f'o/r#5={head5}={F}={unrelated}')
    check('posts where one replaced head is gone and another holds the anchor', code == 0
          and len(state(5)['comments']) == 1 and f'replaced the head {H[:7]}' in out)
    # The force-push record is read only when GitHub answers behind or diverged. A compare that failed, or gave no
    # answer GitHub documents, still refuses, even where a replaced head holds the anchor.
    for label, extra, reason in (('GitHub cannot compare', dict(elsewhere=()), 'could not compare'),
                                 ('GitHub gives no documented answer for', dict(elsewhere=(), silent=('f' * 40,)),
                                  'none of ahead')):
        seed(5, **dict(pushed, replaced=({'before': G, 'ancestors': ['f' * 40]},), **extra))
        code, out = post(f'o/r#5={head5}={F}={unrelated}')
        check(f'refuses an anchor {label} even where a replaced head holds it', code != 0 and reason in out
              and 'the anchor stands' not in out and state(5)['comments'] == [])
        gate_found = {}
        os.environ.update(PATH=BIN + os.pathsep + os.environ['PATH'], STUB_STATE=STATE)
        why = load().outside_history('o/r', F, head5, num='5', replaced=gate_found)
        check(f'the gate with a number refuses an anchor {label} even where a replaced head holds it',
              isinstance(why, str) and reason in why and gate_found == {})
    # PR #111's reuse check reads the commits the head holds after the anchor, and the head holds none after an
    # anchor that stands only through a force push, so the check refuses no reuse of it. That limit is stated in
    # review-round.md's step 7, and l3a0/claude-plugins#120 holds the case.
    seed(5, **dict(pushed, replaced=({'before': G, 'ancestors': ['f' * 40]},),
                   comments=[f'## Review, round 2\n\nRound 2, of `{F}`, fixed in `{G[:7]}`.\n']))
    code, out = post(f'o/r#5={head5}={F}={unrelated}')
    check('posts a force-pushed anchor that an earlier round read past, which the reuse check does not read (#120)',
          code == 0 and len(state(5)['comments']) == 2 and 'the anchor stands' in out)
    seed(5, **dict(pushed, replaced=({'before': 'f' * 40},),
                   comments=[f'## Review, round 2\n\nRound 2, of `{F}`, at `{"f" * 7}`.\n']))
    code, out = post(f'o/r#5={head5}={F}={unrelated}')
    check('posts a force-pushed anchor that was itself the replaced head, which no round read past', code == 0
          and len(state(5)['comments']) == 2 and 'the anchor stands' in out)
    seed(5, **dict(pushed, replaced=({'before': G, 'ancestors': ['f' * 40]},)))
    code, out = post(f'o/r#5={head5}={F}={unrelated}', STUB_GRAPHQL_FAIL='1')
    check('refuses when GitHub\'s record of force pushes cannot be read', code != 0
          and 'record of force pushes on o/r#5 could not be read' in out and '502' in out and state(5)['comments'] == [])
    seed(5, **dict(pushed, replaced=({'before': G, 'ancestors': ['f' * 40]},)))
    code, out = post(f'o/r#5={head5}={F}={unrelated}', '--dry-run')
    check('a dry run accepts a force-pushed anchor and says so', code == 0 and 'the anchor stands' in out
          and 'would post' in out and state(5)['comments'] == [])
    seed(5, **dict(pushed, replaced=({'before': G, 'ancestors': ['f' * 40]},))), seed(6, head=head6, repo='o-s')
    code, out = post(COMP, f'o/r#5={head5}={F}={unrelated}')
    check('a force-pushed anchor on one companion posts on both', code == 0 and len(state(5)['comments']) == 1
          and len(state(6, 'o-s')['comments']) == 1 and out.count('the anchor stands') == 1)
    # A closing comment ends the review, and no lens read a head a force push wrote, so the script refuses one whose
    # anchor stands only through a force push, whether the replaced head is the anchor or holds it, and whatever the
    # text says. The review takes a round at the new head first, as review-round.md's step 6 says.
    closing_pushed = os.path.join(ROOT, 'closing-pushed.md')
    for label, push in (('holds', {'before': G, 'ancestors': ['f' * 40]}), ('is', {'before': 'f' * 40})):
        replaced_7 = push['before'][:7]
        with open(closing_pushed, 'w') as f:
            f.write(f'## Review complete\n\nCloses round 3, of `{F}`, at `{"a" * 7}`. A force push replaced '
                    f'`{replaced_7}`, so no lens read this head. Every commit was read.\n')
        seed(5, **dict(pushed, replaced=(push,)))
        code, out = post(f'o/r#5={head5}={F}={closing_pushed}')
        check(f'refuses a closing comment whose anchor stands only through a force push, where the replaced head '
              f'{label} the anchor, even one that names it', code != 0 and 'at a head no lens read' in out
              and f'replaced {replaced_7}' in out and "review-round.md's step 6" in out
              and 'the anchor stands' not in out and state(5)['comments'] == [])
        code, out = post(f'o/r#5={head5}={F}={closing_pushed}', '--dry-run')
        check(f'a dry run refuses that closing comment too, where the replaced head {label} the anchor', code != 0
              and 'at a head no lens read' in out and 'would post' not in out)
    full = os.path.join(ROOT, 'closing-full.md')
    with open(full, 'w') as f:
        f.write(f'## Review complete\n\nCloses round 3, of `{"f" * 40}`, at `{"a" * 7}`.\n')
    seed(5, **dict(pushed, replaced=({'before': 'f' * 40},)))
    code, out = post(f'o/r#5={head5}={"f" * 40}={full}')
    check('refuses a closing comment whose full anchor is the head a force push replaced', code != 0
          and 'at a head no lens read' in out and "'## Review, round <N>' instead, and a closing comment posts nothing" in out
          and state(5)['comments'] == [])
    seed(5, **dict(pushed, replaced=({'before': G, 'ancestors': ['f' * 40]},))), seed(6, head=head6, repo='o-s')
    clean_closing = os.path.join(ROOT, 'clean-closing.md')
    with open(clean_closing, 'w') as f:
        f.write(f'## Review complete\n\nCloses round 3, of `{B}`, at `{"d" * 7}`.\n')
    code, out = post(f'o/s#6={head6}={B}={clean_closing}', f'o/r#5={head5}={F}={closing_pushed}')
    check('a refused closing comment on one companion posts on neither', code != 0 and 'at a head no lens read' in out
          and state(5)['comments'] == [] and state(6, 'o-s')['comments'] == [])
    seed(5, **dict(pushed, replaced=({'before': 'f' * 40},)))
    code, out = post(f'o/r#5={head5}={F}={unrelated}')
    check('a round comment whose anchor is the replaced head still posts', code == 0 and len(state(5)['comments']) == 1)
    seed(5, head=head5)
    code, out = post(f'o/r#5={head5}={A}={closing}')
    check('a closing comment whose anchor is in the head\'s history still posts', code == 0
          and len(state(5)['comments']) == 1)

    # Other callers, such as a check of a branch with no pull request, call the gate with three arguments and test
    # its answer for truth, so that form keeps its meaning and reads no force push.
    gate = load()
    seed(5, **dict(pushed, replaced=({'before': G, 'ancestors': ['f' * 40]},)))
    os.environ.update(PATH=BIN + os.pathsep + os.environ['PATH'], STUB_STATE=STATE)
    check('the three-argument gate returns None for an ancestor', gate.outside_history('o/r', 'b' * 7, head5) is None)
    why = gate.outside_history('o/r', F, head5)
    check('the three-argument gate returns the reason as text, and reads no force push, for an anchor outside the '
          'history', isinstance(why, str) and 'is diverged against the anchor' in why and 'force push' not in why)
    found = {}
    check('the gate with a number returns None and the replaced head for a force-pushed anchor',
          gate.outside_history('o/r', F, head5, num='5', replaced=found) is None and found.get('before') == G)

    seed(5, **dict(pushed, replaced=({'before': G, 'ancestors': ['f' * 40]},))), seed(6, head=head6, repo='o-s', ancestors=())
    code, out = post(f'o/r#5={head5}={F}={unrelated}', COMP)
    check('a force-pushed anchor on one companion does not lift a refusal on the other', code != 0
          and 'o/s#6' in out and state(5)['comments'] == [] and state(6, 'o-s')['comments'] == [])

    seed(5, head=head5, silent=('f' * 40,))
    code, out = post(f'o/r#5={head5}={F}={unrelated}')
    check('refuses an anchor whose compare prints no status, and says GitHub gave no documented answer', code != 0
          and 'none of ahead' in out and state(5)['comments'] == [])

    seed(5, head=head5)
    code, out = post(f'o/r#5={head5}={F}={unrelated}')
    check('refuses an anchor the repository does not hold', code != 0 and 'could not compare' in out
          and 'Not Found' in out and state(5)['comments'] == [])

    code, out = post(f'o/r#5={head5}={F}={unrelated}', '--dry-run')
    check('a dry run checks the anchor too', code != 0 and 'an anchor was not shown to be the head or an ancestor' in out)

    # Two rounds do not share an anchor, unless nothing was pushed on that pull request between them. A round's comment
    # names its head, so an earlier round's comment that names the anchor and a commit after it is the mistake.
    E = 'e' * 7
    fixed = f'## Review, round 2\n\nRound 2, of `{A}`, fixed in `{"a" * 7}`.\n'
    round2 = f'## Review, round 2\n\nRound 2, of `{E}`, fixed in `{A}`.\n'
    seed(5, head=head5, comments=[round2, fixed])
    seed(6, head=head6, repo='o-s')
    code, out = post(MAIN, COMP)
    check("refuses an anchor an earlier round's comment names with a commit after it, and posts on no companion", code != 0
          and 'another round read past this anchor' in out
          and f"o/r#5: round 2's comment names {A} as its anchor and also {'a' * 7}, which the head holds after it" in out
          and 'o/s#6:' not in out and 'report it' in out
          and len(state(5)['comments']) == 2 and state(6, 'o-s')['comments'] == [])
    code, out = post(MAIN, '--dry-run')
    check("a dry run refuses an earlier round's anchor too", code != 0 and 'read past this anchor' in out and 'would post' not in out)
    seed(5, head=head5, comments=[fixed.replace('`aaaaaaa`', f'`{"a" * 40}`')])
    code, out = post(MAIN)
    check('reads a later commit the earlier comment names in full', code != 0 and 'read past this anchor' in out)
    F7 = 'f' * 40
    seed(5, head=head5, comments=[f'## Review, round 2\n\nRound 2, of `{A}`, fixed in `{F7[:7]}`, then merged.\n'],
         later_than={A: [head5, F7]})
    code, out = post(MAIN, STUB_PAGES='2')
    check('finds a later commit on the second page of the compare, and says to report one that is not the pull request\'s own',
          code != 0 and f'also {F7[:7]}' in out and 'report it' in out)
    seed(5, head=head5, comments=[fixed, open(note).read()])
    code, out = post(MAIN)
    check("the refusal names a pull request that already holds this round's comment", code != 0
          and 'read past this anchor' in out and "This round's comment is already on o/r#5" in out)
    seed(5, head=head5, comments=[f'## Review, round 2\n\nRound 2, of `{A + "b" * 33}`, fixed in `{"a" * 7}`.\n'])
    code, out = post(MAIN)
    check('an earlier round that names the anchor in full is refused against seven characters', code != 0
          and 'read past this anchor' in out and len(state(5)['comments']) == 1)
    seed(5, head=head5, comments=[f'## Review, round 2\n\nRound 2, of `{A + "c" * 33}`, fixed in `{"a" * 7}`.\n'])
    code, out = post(f'o/r#5={head5}={"b" * 40}={note}')
    check('an earlier anchor that shares only the first seven characters is another commit', code == 0
          and len(state(5)['comments']) == 2)
    seed(5, head=head5, comments=[f'## Review, round 4\n\nRound 4, of `{A}`, fixed in `{"a" * 7}`.\n'])
    code, out = post(MAIN)
    check('refuses an anchor a later round named with a later commit too', code != 0 and "round 4's comment" in out)
    seed(5, head=head5, comments=[fixed.replace('round 2', 'round 1').replace('Round 2', 'Round 1'), fixed])
    code, out = post(MAIN)
    check('names every other round that read the anchor before a later commit', code != 0
          and "round 1's comment" in out and "round 2's comment" in out)
    seed(5, head=head5, comments=[f'## Review complete\n\nCloses round 2 of `{A}`, at `{"a" * 7}`.\n'])
    code, out = post(MAIN)
    check("reads a closing comment's 'round K of <anchor>' written without the comma", code != 0
          and "round 2's comment" in out and len(state(5)['comments']) == 1)
    seed(5, head=head5, comments=[f'## Review, round 4\n\nTurned around 2, of `{A}`, at `{"a" * 7}`. Round 4, of `{E}`.\n'])
    code, out = post(MAIN)
    check("'around K, of' is not a round", code == 0 and len(state(5)['comments']) == 2)

    seed(5, head=head5, comments=[round2])
    code, out = post(MAIN)
    check("a fresh anchor posts where the earlier round's comment names it only as its fix", code == 0
          and len(state(5)['comments']) == 2 and 'posted' in out)
    code, out = post(MAIN)
    check('a retry of the same round still skips its own comment', code == 0 and 'skipped' in out
          and len(state(5)['comments']) == 2)
    seed(5, head=head5, comments=[fixed.replace('round 2', 'round 3').replace('Round 2', 'Round 3') + 'Earlier text.\n'])
    code, out = post(MAIN)
    check("this round's own comment with other text is not another round's", code != 0 and 'different text' in out
          and 'read past this anchor' not in out)
    seed(5, head=head5, comments=[fixed, fixed.replace('round 2', 'round 3').replace('Round 2', 'Round 3') + 'Earlier text.\n'])
    code, out = post(MAIN)
    check("an earlier round's anchor is reported before the different text that sends the session to post by hand",
          code != 0 and 'read past this anchor' in out and 'different text' not in out)

    seed(5, head=head5, comments=[fixed], login='stranger')
    code, out = post(MAIN)
    check("another login's comment on another round does not stop the post", code == 0 and len(state(5)['comments']) == 2)
    seed(5, head=head5, comments=[f'Owner ruling, 2026-11-27: round 2, of `{A}`, fixed in `{"a" * 7}`, stands.\n'])
    code, out = post(MAIN)
    check('a comment that opens without a heading is not read as a round', code == 0 and len(state(5)['comments']) == 2)
    seed(5, head=head5, comments=[f'## Review, round 2\n\nRound 2 read `{A}`, fixed in `{"a" * 7}`.\n'])
    code, out = post(MAIN)
    check("a comment that does not say 'round K, of' is not read", code == 0 and len(state(5)['comments']) == 2)
    seed(5, head=head5, comments=[f'## Review complete\n\nCloses round 2, of `{A}`.\n', fixed.replace(f'`{A}`', f'`{E}`')])
    code, out = post(MAIN)
    check('an earlier round on this anchor that names no later commit does not stop the post', code == 0
          and len(state(5)['comments']) == 3)

    # A closing comment for round 2 after round 3 read a commit the head holds after round 2's anchor is stale.
    C7 = 'c' * 7
    old_close = os.path.join(ROOT, 'old-close.md')
    with open(old_close, 'w') as f:
        f.write(f'## Review complete\n\nRound 2, of `{A}`, closes at `{"a" * 7}`.\n')
    seed(5, head=head5, comments=[f'## Review, round 2\n\nRound 2, of `{A}`, changes nothing.\n',
                                  f'## Review, round 3\n\nRound 3, of `{C7}`, fixed in `{"a" * 7}`.\n'],
         later_than={A: ['c' * 40, head5]})
    code, out = post(f'o/r#5={head5}={A}={old_close}', round_no='2')
    check("refuses an anchor where another round already read a commit the head holds after it", code != 0
          and f"round 3's comment reads {C7} as its anchor, which the head holds after {A}" in out
          and len(state(5)['comments']) == 2)
    # A round that pushed nothing, followed by a commit such as one applying the owner's ruling, looks like a
    # companion read twice, so the script lets an anchor copied from it through, and step 7 keeps the hand check.
    seed(5, head=head5, comments=[f'## Review, round 2\n\nRound 2, of `{A}`, at `{A}`, waits for the owner.\n'])
    code, out = post(MAIN)
    check('an anchor copied from a round that named no later commit posts, which step 7 checks by hand', code == 0
          and len(state(5)['comments']) == 2)
    seed(5, head=head5, comments=[f'## Review, round 2\n\nRound 2, of `{A}`, base `ff{"a" * 7}0000`.\n'])
    code, out = post(MAIN)
    check('a later commit does not count as the end of a longer hash', code == 0 and len(state(5)['comments']) == 2)
    seed(5, head=head5, comments=[fixed], later_than={A: []})
    code, out = post(MAIN, STUB_AHEAD_BY='1')
    check('refuses an ahead answer that lists no commits after the anchor', code != 0
          and 'is ahead by 1 commits of the anchor bbbbbbb and listed 0' in out and len(state(5)['comments']) == 1)
    seed(5, head=head5, comments=[fixed], later_than={A: []})
    code, out = post(MAIN, STUB_AHEAD_BY='0')
    check('refuses an ahead answer whose count of none matches a list without the head', code != 0
          and 'without the head among them' in out and len(state(5)['comments']) == 1)
    seed(5, head=head5, comments=[fixed], later_than={A: ['c' * 40]})
    code, out = post(MAIN, STUB_AHEAD_BY='1')
    check('refuses an ahead answer whose count matches a list of other commits without the head', code != 0
          and 'without the head among them' in out and len(state(5)['comments']) == 1)
    seed(5, head=head5, comments=[round2], later_than={A: [head5, 'c' * 40]})
    code, out = post(MAIN, STUB_AHEAD_BY='1')
    check('refuses an ahead answer that lists more commits than it counts', code != 0
          and 'is ahead by 1 commits of the anchor bbbbbbb and listed 2' in out and len(state(5)['comments']) == 1)
    seed(5, head=head5, comments=[round2])
    code, out = post(MAIN, STUB_SECOND_STATUS='diverged', STUB_PAGES='2')
    check('refuses a compare whose pages give different statuses', code != 0 and 'gave different statuses, ahead, diverged' in out
          and len(state(5)['comments']) == 1)

    # A round rerun on the same commit after a lens failed keeps its number. Round 3 posts only after its lenses, so
    # the rerun finds no comment of its own, which the fresh-anchor check above already covers. Once round 3 has
    # posted at a commit that is still the head, reading it again is a round of its own, and no compare runs.
    read_head = f'## Review, round 3\n\nRound 3, of `{"a" * 7}`, at `{"a" * 7}`, changes nothing.\n'
    again = os.path.join(ROOT, 'again.md')
    with open(again, 'w') as f:
        f.write(f'## Review, round 4\n\nRound 4, of `{"a" * 7}`, at `{"a" * 7}`, reads it again.\n')
    seed(5, head=head5, comments=[read_head], ancestors=())
    code, out = post(f'o/r#5={head5}={"a" * 7}={again}', round_no='4')
    check('a round that reads the head an earlier round read posts', code == 0 and len(state(5)['comments']) == 2)

    # A companion round 2 left alone is read at the same commit by round 3, whose fixes then move its head.
    seed(5, head=head5, comments=[round2])
    seed(6, head=head6, repo='o-s', comments=[f'## Review, round 2\n\nRound 2, of `{B}`, at `{B}`, changes nothing here.\n'])
    code, out = post(MAIN, COMP)
    check('a companion read again at the commit an earlier round read, then fixed, posts', code == 0
          and len(state(5)['comments']) == 2 and len(state(6, 'o-s')['comments']) == 2)

    first = os.path.join(ROOT, 'first.md')
    with open(first, 'w') as f:
        f.write(f'## Review, round 3\n\nRound 2, of `{E}`, left one finding. Round 3, of `{A}`, fixed in `{"a" * 7}`.\n')
    seed(5, head=head5)
    code, out = post(f'o/r#5={head5}={A}={first}')
    check("refuses a file whose first 'round K, of' names another round", code != 0
          and 'a later round could not read which anchor' in out and state(5)['comments'] == [])
    with open(first, 'w') as f:
        f.write(f'## Review, round 3\n\nRound 2, of `{A}`, is this round. Round 3 fixed it in `{"a" * 7}`.\n')
    code, out = post(f'o/r#5={head5}={A}={first}')
    check("refuses a file whose first 'round K, of' names this anchor under another round", code != 0
          and 'a later round could not read which anchor' in out and state(5)['comments'] == [])
    with open(first, 'w') as f:
        f.write(f'## Review, round 3\n\nRound 3, of `{E}`, read `{A}` again, fixed in `{"a" * 7}`.\n')
    code, out = post(f'o/r#5={head5}={A}={first}')
    check("refuses a file whose first 'round K, of' names this round with another anchor", code != 0
          and 'a later round could not read which anchor' in out and state(5)['comments'] == [])
    with open(first, 'w') as f:
        f.write(f'## Review, round 3\n\nThis is round 3 at `{A}`, fixed in `{"a" * 7}`.\n')
    code, out = post(f'o/r#5={head5}={A}={first}')
    check("refuses a file that does not say 'round K, of <anchor>'", code != 0
          and 'a later round could not read which anchor' in out and state(5)['comments'] == [])

    code, out = post('not-a-target')
    check('refuses a malformed target', code != 0 and 'OWNER/REPO#N=HEAD=ANCHOR=FILE' in out)

    seed(5, head=head5)
    code, out = post(MAIN, '--dry-run')
    check('a dry run posts nothing', state(5)['comments'] == [] and 'would post' in out)

    final_round = os.path.join(ROOT, 'final-round.md')
    with open(final_round, 'w') as f:
        f.write(f'## Review complete\n\nCloses round 3, of `{A}`, at `{"a" * 7}`, and links the round.\n')
    seed(5, head=head5, comments=[f'## Review complete\n\nRound 3, of `{A}`, at `{"a" * 7}`, found nothing.\n'])
    code, out = post(f'o/r#5={head5}={A}={final_round}')
    check('a closing comment after a round comment that already closes the review posts nothing and says so',
          code != 0 and 'which closes the review' in out and 'Report it' in out and f'at the head {head5[:7]}' in out
          and len(state(5)['comments']) == 1)
    seed(5, head=head5, comments=[f'## Review complete\n\nRound 3, of `{A}`, at `{"a" * 6 + "f"}`, found nothing.\n'])
    code, out = post(f'o/r#5={head5}={A}={final_round}')
    check('a closing comment posts where the round comment that took the final heading names an older head',
          code == 0 and 'posted' in out and len(state(5)['comments']) == 2)
    for word in ('complete', '²', '-1', '٣'):
        seed(5, head=head5)
        code, out = post(MAIN, round_no=word)
        check(f'a round given as {word!r} names the round to give', code != 0 and 'the round it closes' in out and 'Traceback' not in out and state(5)['comments'] == [])
    crlf = os.path.join(ROOT, 'crlf.md')
    with open(crlf, 'w', newline='') as f:
        f.write(f'## Review complete\r\n\r\nCloses round 3, of `{A}`, at `{"a" * 7}`.\r\n')
    seed(5, head=head5, comments=[f'## Review complete\r\n\r\nCloses round 3, of `{A}`, at `{"a" * 7}`.\r\n'])
    code, out = post(f'o/r#5={head5}={A}={crlf}')
    check('a copy that differs only in line endings is skipped', code == 0 and 'skipped' in out and len(state(5)['comments']) == 1)
    near = os.path.join(ROOT, 'near.md')
    for heading in ('## Review complete, round 3', '### Review complete', '## review complete', '## Review complete ',
                    ' ## Review complete', '## Review  complete', '## Review-complete', '## Review: complete',
                    '## Review — complete', '## Reviewcomplete', '# Review complete', '###### Review complete',
                    '##Review complete', '## Review_complete', '## Review. complete'):
        with open(near, 'w') as f:
            f.write(f'{heading}\n\nCloses round 3, of `{A}`, at `{"a" * 7}`.\n')
        seed(5, head=head5)
        code, out = post(f'o/r#5={head5}={A}={near}')
        check(f'refuses a closing heading written {heading!r}', code != 0 and 'whole first line' in out and state(5)['comments'] == [])
    with open(near, 'w') as f:
        f.write(f'## Review completeness, round 3\n\nRound 3, of `{A}`, at `{"a" * 7}`.\n')
    code, out = post(f'o/r#5={head5}={A}={near}')
    check('a heading that only shares the first letters still posts', code == 0 and len(state(5)['comments']) == 1)

    # The cost form posts on an issue, which the stand-in keeps in a file of its own, so a call to `gh pr`
    # with the issue's number fails as unexpected.
    def seed_issue(num, comments=(), login='me'):
        with open(os.path.join(STATE, f'issue-o-r-{num}.json'), 'w') as f:
            json.dump({'comments': [{'author': {'login': login}, 'body': c} for c in comments]}, f)

    def issue(num):
        with open(os.path.join(STATE, f'issue-o-r-{num}.json')) as f:
            return json.load(f)['comments']

    def write_cost(text):
        fd, path = tempfile.mkstemp(prefix='cost-', suffix='.md', dir=ROOT)
        with os.fdopen(fd, 'w') as f:
            f.write(text)
        return path

    COST = f'## Cost\n\nReview round 3, of `{A}`, on https://github.com/o/r/pull/5\n\n1. Four review lenses: at least 2.18 US dollars.\n'
    cost_file = write_cost(COST)

    def price(*extra, round_no='3', anchor=A, pull='o/r#5', file=None, **env):
        return run('cost', 'o/r#40', '--round', round_no, '--pull', pull, '--anchor', anchor,
                   '--file', file or cost_file, *extra, **env)

    seed_issue(40)
    code, out = price()
    check('posts the cost comment on the issue', code == 0 and [(c['author'], c['body']) for c in issue(40)] == [({'login': 'me'}, COST)] and '/issues/40' in out)
    code, out = price()
    check('a retried cost post posts nothing more', code == 0 and len(issue(40)) == 1 and 'skipped' in out)

    seed_issue(40, [COST.replace('2.18', '2.19')])
    code, out = price()
    check('a cost comment with other text stops the post', code != 0 and 'different text' in out and len(issue(40)) == 1)
    check('a cost comment with other text is not to be edited, apart from the build line this session added', "edit nothing, since it may hold another session's spend" in out and "the build's line this session added" in out)
    seed_issue(40, [COST.replace('2.18', '2.19')], login='stranger')
    code, out = price()
    check("another login's cost comment does not stop the post", code == 0 and len(issue(40)) == 2)
    seed_issue(40, [COST.replace(f'`{A}`', f'`{B}`')])
    code, out = price()
    check('a cost comment for the same round and pull request under another anchor stops the post',
          code != 0 and f'under the anchor {B}, not {A}' in out and 'count the round twice' in out
          and 'Delete and edit nothing' in out and len(issue(40)) == 1)
    for label, other in (('round', COST.replace(f'`{A}`', f'`{B}`').replace('round 3', 'round 2')),
                         ('pull request', COST.replace(f'`{A}`', f'`{B}`').replace('pull/5', 'pull/6'))):
        seed_issue(40, [other])
        code, out = price()
        check(f'a cost comment for another {label} under another anchor does not stop the post', code == 0 and len(issue(40)) == 2)
    seed_issue(40)
    code, out = price(STUB_RACE='40')
    check('a cost post that lands beside a copy with other text deletes nothing', code != 0
          and 'Delete and edit nothing' in out and 'Keep ' not in out and len(issue(40)) == 2)
    seed_issue(40, [COST.replace(f'`{A}`', f'`{B}`')], login='stranger')
    code, out = price()
    check("another login's cost comment under another anchor does not stop the post", code == 0 and len(issue(40)) == 2)
    for label, other in (('round', COST.replace('round 3', 'round 2')),
                         ('pull request number', COST.replace('pull/5', 'pull/55')),
                         ('repository', COST.replace('o/r/pull/5', 'o/s/pull/5')),
                         ('issue link', COST.replace('pull/5', 'issues/5')),
                         ('heading', COST.replace('## Cost\n', '## Cost total\n'))):
        seed_issue(40, [other])
        code, out = price()
        check(f'a cost comment for another {label} does not block the post', code == 0 and len(issue(40)) == 2)
    seed_issue(40, [COST.replace('o/r/pull/5', 'O/R/pull/5')])
    code, out = price()
    check('a copy linking the repository in other case is the same key, so its other text stops the post',
          code != 0 and 'different text' in out and len(issue(40)) == 1)
    for label, same in (('trailing blank lines', COST + '\n\n'),):
        seed_issue(40, [same])
        code, out = price()
        check(f'a cost copy that differs only in {label} is skipped', code == 0 and 'skipped' in out and len(issue(40)) == 1)
    seed_issue(40, [COST])
    held = issue(40) + [{'author': None, 'body': COST}]
    with open(os.path.join(STATE, 'issue-o-r-40.json'), 'w') as f:
        json.dump({'comments': held}, f)
    code, out = price()
    check('a cost comment from a deleted account is passed over', code == 0 and 'skipped' in out and 'Traceback' not in out)

    seed_issue(40)
    bare = write_cost(COST.replace(f'`{A}`', A))
    code, out = price(file=bare)
    code2, out2 = price(file=bare)
    check('posts and then skips a round line whose anchor has no backticks', code == 0 and code2 == 0 and 'skipped' in out2 and len(issue(40)) == 1)

    seed_issue(40)
    linked = write_cost(COST.replace('https://github.com/o/r/pull/5', '[PR #5](https://github.com/o/r/pull/5)'))
    code, out = price(file=linked)
    check('reads a Markdown link to the pull request', code == 0 and len(issue(40)) == 1)
    code, out = price(anchor=A + 'b' * 33, file=linked)
    check('a full anchor matches a cost comment naming seven characters', code == 0 and 'skipped' in out)

    seed_issue(40)
    for name, text in (('a file without the heading', COST.replace('## Cost\n', '## Costs\n')),
                       ('a file whose round differs', COST.replace('round 3', 'round 4')),
                       ('a file whose anchor differs', COST.replace(f'`{A}`', f'`{B}`')),
                       ('a file that links another pull request', COST.replace('pull/5', 'pull/6')),
                       ('a file whose round line is not the first after the heading', COST.replace('\n\nReview', '\n\nTo date.\n\nReview')),
                       ('a heading with a space after it', COST.replace('## Cost\n', '## Cost \n')),
                       ('a heading with a space before it', ' ' + COST),
                       ('a pull request named in its short form', COST.replace('https://github.com/o/r/pull/5', 'o/r#5')),
                       ('a file that links the pull request of another repository', COST.replace('o/r/pull/5', 'o/s/pull/5')),
                       ('a file that links an issue of that number', COST.replace('pull/5', 'issues/5')),
                       ('a link over plain http', COST.replace('https://', 'http://')),
                       ('a link with no scheme', COST.replace('https://github.com', 'github.com')),
                       ('a link to another host', COST.replace('https://github.com', 'https://evilgithub.com')),
                       ('a link to another host that carries a github.com address', COST.replace('https://github.com', 'https://evil.example/?next=https://github.com')),
                       ('a Markdown link to the pull request after another link', COST.replace('https://github.com/o/r/pull/5', '[x](https://evil.example/) and [y](https://github.com/o/r/pull/5)')),
                       ('a Markdown link to the pull request after another address', COST.replace('https://github.com/o/r/pull/5', 'https://evil.example/ [y](https://github.com/o/r/pull/5)')),
                       ('a round line with words before it', COST.replace('\nReview round', '\nDraft: Review round')),
                       ('an empty file', '')):
        seed_issue(40)
        code, out = price(file=write_cost(text))
        check(f'refuses {name}', code != 0 and 'could not recognise it' in out and issue(40) == [] and 'Traceback' not in out)

    seed_issue(40, [COST.replace('\n', '\r\n')])
    code, out = price()
    check('a cost copy that differs only in line endings is skipped', code == 0 and 'skipped' in out and len(issue(40)) == 1)
    seed_issue(40, [COST, COST])
    code, out = price()
    check('reports a cost comment already there twice', code != 0 and 'should hold this comment once' in out and len(issue(40)) == 2)
    seed_issue(40)
    code, out = price(STUB_DOUBLE='40')
    check('a cost post that landed twice is reported', code != 0 and 'should hold this comment once' in out)
    first, second = (c['url'] for c in issue(40))
    check('a cost post that landed twice names the copy with the lowest comment number to keep', f'Keep {first}' in out and f'delete {second}' in out)
    seed_issue(40)
    code, out = price(STUB_HIDE='40')
    check('a cost post the read after posting does not show says to rerun nothing', code != 0 and 'Rerun nothing' in out
          and f"the read after posting {issue(40)[0]['url']} shows none" in out and len(issue(40)) == 1)
    seed_issue(40)
    code, out = price(STUB_LOST='comment')
    check('a lost reply on a cost post says the outcome is unknown', code != 0 and 'outcome is unknown' in out)
    code, out = price()
    check('the retry after a lost cost reply posts nothing more', code == 0 and len(issue(40)) == 1 and 'skipped' in out)
    seed_issue(40)
    code, out = price('--dry-run')
    check('a cost dry run posts nothing', issue(40) == [] and 'would post' in out)
    code, out = price(pull='not-a-pull')
    check('refuses a malformed pull request', code != 0 and 'OWNER/REPO#N' in out)
    code, out = price(anchor='xyz')
    check('refuses a malformed anchor', code != 0 and 'hex' in out)
    code, out = run('cost', 'bad', '--round', '3', '--pull', 'o/r#5', '--anchor', A, '--file', cost_file)
    check('refuses a malformed issue', code != 0 and 'OWNER/REPO#N' in out and 'Traceback' not in out)
    code, out = price(file=os.path.join(ROOT, 'missing.md'))
    check('refuses a cost file that does not exist', code != 0 and 'no comment file' in out)
    code, out = run('cost', 'o/r#41', '--round', '3', '--pull', 'o/r#5', '--anchor', A, '--file', cost_file)
    check('a cost post names the issue it was given', code != 0 and 'unexpected call' in out)

    # The check form runs the comment form's head and anchor checks and posts nothing, for a comment
    # that goes by hand, and checks that the comment's file names the anchor, and on a pull request the head.
    # A branch's tip is seeded as a pull request of its own, so the stand-in's compare finds it.
    def gate(*targets, **env):
        return run('check', *targets, **env)

    def branches(tips):
        with open(os.path.join(STATE, 'branches.json'), 'w') as f:
            json.dump(tips, f)

    def names(*shas):
        fd, path = tempfile.mkstemp(prefix='hand-', suffix='.md', dir=ROOT)
        with os.fdopen(fd, 'w') as f:
            f.write('## Review, round 3\n\nRound 3, of ' + ', '.join(f'`{x[:7]}`' for x in shas) + '.\n')
        return path

    seed(5, head=head5, elsewhere=('f' * 40,)), seed(6, head=head6, repo='o-s')
    code, out = gate(f'o/r#5={head5}={A}={names(A, head5)}', f'o/s#6={head6}={B}={names(B, head6)}')
    check('check passes a head that matches, an anchor in its history and a file naming both', code == 0
          and f'o/r#5: the anchor {A} is an ancestor of the head {head5[:7]}' in out and 'o/s#6: the anchor' in out)
    check('check posts nothing', state(5)['comments'] == [] and state(6, 'o-s')['comments'] == [])
    seed(5, head=head5, comments=[f'## Review, round 2\n\nRound 2, of `{A}`, fixed in `{"a" * 7}`.\n'])
    code, out = gate(f'o/r#5={head5}={A}={names(A, head5)}')
    check("check refuses an anchor another round's comment shows it read past, as comment does", code != 0
          and 'another round read past this anchor' in out and "round 2's comment names" in out)
    seed(5, head=head5, comments=[f'## Review, round 3\n\nRound 3, of `{A}`, fixed in `{"a" * 7}`.\n'])
    code, out = gate(f'o/r#5={head5}={A}={names(A, head5)}')
    check("check skips the file's own round, whose earlier comment names the anchor and a later commit", code == 0)
    other = os.path.join(ROOT, 'other-round.md')
    with open(other, 'w') as f:
        f.write(f'## Review, round 3\n\nRound 3, of `{"c" * 7}`, then round 4, of `{A}`, at `{head5[:7]}`.\n')
    code, out = gate(f'o/r#5={head5}={A}={other}')
    check("check skips no round when the file's own round line names another anchor", code != 0
          and 'another round read past this anchor' in out)
    seed(5, head=head5, login='stranger', comments=[f'## Review, round 2\n\nRound 2, of `{A}`, fixed in `{"a" * 7}`.\n'])
    code, out = gate(f'o/r#5={head5}={A}={names(A, head5)}')
    check("check reads only the session's own login for a round that read past the anchor", code == 0)
    # On a pull request, check accepts an anchor that stands only through a force push, as comment does, and refuses
    # a file headed "## Review complete" whose anchor stands only that way.
    seed(5, head=head5, elsewhere=('f' * 40,), replaced=({'before': '9' * 40, 'ancestors': ['f' * 40]},))
    code, out = gate(f'o/r#5={head5}={"f" * 7}={names("f" * 7, head5)}')
    check('check passes an anchor that stands through a recorded force push on the pull request', code == 0
          and f'stands through a force push that replaced {"9" * 7}, beside the head {head5[:7]}' in out
          and state(5)['comments'] == [])
    pushed_close = os.path.join(ROOT, 'pushed-close.md')
    with open(pushed_close, 'w') as f:
        f.write(f'## Review complete\n\nCloses round 3, of `{"f" * 7}`, at `{head5[:7]}`.\n')
    code, out = gate(f'o/r#5={head5}={"f" * 7}={pushed_close}')
    check("check refuses a '## Review complete' file whose anchor stands only through a force push", code != 0
          and 'at a head no lens read' in out and state(5)['comments'] == [])
    seed(5, head=head5, elsewhere=('f' * 40,))
    code, out = gate(f'o/r#5={head5}={"f" * 7}={names("f" * 7, head5)}')
    check('check still refuses an anchor outside the history with no force push recorded', code != 0
          and 'no force push GitHub records' in out)
    seed(5, head=head5, elsewhere=('f' * 40,))
    code, out = gate(f'o/r#5={head5}={head5[:7]}={names(head5)}')
    check('check passes an anchor that is the head', code == 0 and 'is the head' in out and 'names them, so it may post' in out)
    code, out = gate(f'o/r#5={head5[:7]}={A}={names(A, head5)}')
    check('check takes a seven-character head', code == 0)
    code, out = gate(f'o/r#5={head5}={A}={names(A, head5)}', f'o/s#6={"e" * 40}={B}={names(B, "e" * 40)}')
    check('check fails when one head differs, naming it', code != 0 and f'o/s#6 is at {head6[:7]}, not {"e" * 7}' in out
          and 'post nothing' in out and 'o/r#5: the anchor' not in out)
    code, out = gate(f'o/r#5={head5}={A}={names(head5)}')
    check('check fails a file that does not name the anchor', code != 0 and f'does not name the anchor {A}' in out)
    code, out = gate(f'o/r#5={head5}={A}={names(A)}')
    check('check fails a file that does not name the head', code != 0 and f'does not name the head {head5[:7]}' in out)
    code, out = gate(f'o/r#5={head5}={A}={names(head5)}', f'o/s#6={"e" * 40}={B}={names(B)}')
    check('check names every file and head that fails, not only the first', code != 0
          and f'does not name the anchor {A}' in out and 'o/s#6 is at' in out and 'does not name the head eeeeeee' in out)
    code, out = gate(f'o/r#5={head5}={A}={os.path.join(ROOT, "missing.md")}')
    check('check refuses a file that does not exist', code != 0 and 'no comment file' in out)
    code, out = gate(f'o/r#5={head5}={"f" * 7}={names("f" * 7, head5)}')
    check('check fails an anchor outside the head\'s history', code != 0 and 'is diverged against the anchor' in out and 'post nothing' in out)
    code, out = gate(f'o/r#5={head5}={"9" * 7}={names("9" * 7, head5)}')
    check('check fails an anchor GitHub does not hold', code != 0 and 'could not compare' in out)
    seed(5, head=head5, silent=('f' * 40,))
    code, out = gate(f'o/r#5={head5}={"f" * 7}={names("f" * 7, head5)}')
    check('check fails an answer GitHub does not document', code != 0 and 'none of ahead' in out)
    seed(5, head=head5)
    for label, spec in (('a target with no file', f'o/r#5={head5}={A}'), ('a target with no anchor', 'o/r#5'),
                        ('a six-character head', f'o/r#5={head5[:6]}={A}={note}'),
                        ('a six-character anchor', f'o/r#5={head5}={A[:6]}={note}'),
                        ('a six-character anchor on a branch', f'o/r@main={A[:6]}={note}'),
                        ('a branch target with no file', f'o/r@main={A}')):
        code, out = gate(spec)
        check(f'check refuses {label}', code != 0 and 'not OWNER/REPO#N=HEAD=ANCHOR=FILE' in out and state(5)['comments'] == [])

    tip = '1' * 40
    seed(90, head=tip, later=('2' * 40,))
    seed(91, head='3' * 40, ancestors=('4' * 40,))
    branches({'o/r': {'main': tip, 'claude/x-1': tip, 'dev': '3' * 40, 'x#1': '3' * 40, 'x': tip,
                      'odd': {'out': 'odd\nnot a commit'}, 'framed': {'out': 'framed\nx' + '1' * 40},
                      'short': {'out': 'short\n' + '1' * 7}, 'one': {'out': tip}, 'old': {'out': 'new\n' + tip}}})
    code, out = gate(f'o/r@main={A}={names(A)}')
    check('check passes an anchor in a branch\'s history', code == 0 and f'o/r@main: the anchor {A} is an ancestor of the head {tip[:7]}' in out)
    code, out = gate(f'o/r@claude/x-1={tip[:7]}={names(tip)}')
    check('check reads a branch whose name holds a slash, and passes its tip', code == 0 and 'o/r@claude/x-1: the anchor' in out and 'is the head' in out)
    code, out = gate(f'o/r@dev={"4" * 7}={names("4" * 7)}')
    check('check compares the anchor with the tip of the branch it names', code == 0 and 'ancestor of the head 3333333' in out)
    code, out = gate(f'o/r@x#1={"4" * 7}={names("4" * 7)}')
    check('check reads a branch whose name holds a hash, rather than the branch before the hash', code == 0 and 'ancestor of the head 3333333' in out)
    code, out = gate(f'o/r@nosuch/../main={A}={names(A)}')
    check('check fails a branch GitHub answers for under another name', code != 0 and "answered for the branch 'main'" in out)
    code, out = gate(f'o/r@old={A}={names(A)}')
    check('check fails a renamed branch that GitHub answers for under its new name', code != 0 and "answered for the branch 'new', not 'old'" in out)
    code, out = gate(f'o/r@main={A}={names(A)}')
    check('check says a branch target\'s file names the anchor, not the head', code == 0 and 'names the anchor, so it may post' in out)
    code, out = gate(f'o/r@main={A}={names("4" * 7)}')
    check('check fails a file that does not name the anchor on a branch', code != 0 and f'does not name the anchor {A}' in out)
    for label, branch in (('gives no commit', 'odd'), ('gives a commit inside other text', 'framed'),
                          ('gives a short commit', 'short'), ('gives one line', 'one')):
        code, out = gate(f'o/r@{branch}={A}={names(A)}')
        check(f'check fails a branch read that {label}', code != 0 and f'did not give the tip of {branch}' in out)
    code, out = gate(f'o/r@main={"2" * 7}={names("2" * 7)}')
    check('check fails an anchor that is ahead of the branch', code != 0 and 'is behind against the anchor' in out)
    # A branch has no pull request, so check reads no force push for it, even where one on a pull request would hold
    # the anchor.
    seed(1, head='5' * 40, replaced=({'before': '6' * 40, 'ancestors': ['2' * 40]},))
    code, out = gate(f'o/r@main={"2" * 7}={names("2" * 7)}')
    check('check reads no force push for a branch target', code != 0 and 'is behind against the anchor' in out
          and 'force push' not in out)
    code, out = gate(f'o/r@gone={A}={names(A)}')
    check('check fails a branch GitHub does not give', code != 0 and 'did not give the tip of gone' in out and 'post nothing' in out)
    code, out = gate(f'o/r#5={head5}={A}={names(A, head5)}', f'o/r@main={"2" * 7}={names("2" * 7)}')
    check('check fails the whole run when one target fails', code != 0 and 'o/r#5: the anchor' not in out)

    # The cost form runs no anchor check, so an anchor GitHub cannot compare still posts.
    lost = '9' * 7
    seed_issue(40)
    code, out = price(anchor=lost, file=write_cost(COST.replace(A, lost)))
    check('a cost post runs no anchor check', code == 0 and len(issue(40)) == 1)

    # The section form replaces one named section of the body and refuses a change anywhere else.
    # The fixture names its Decision heading inside an earlier sentence, the shape that cut item 4
    # of PR #110's What list when a hand edit sliced the body at the heading's name.
    SECTIONED = """## Why

Because.

## What

1. Adds the first thing.
2. Names the reasoning under `## Decision`.
3. Adds the third thing.

## Decision

Two facts decide it.

1. The first fact.
2. The second fact.

## Scope

Out of scope: nothing.

```markdown
## Decision
```

Closes #109

🤖 Generated with [Claude Code](https://claude.com/claude-code)
"""

    def part(heading, text, *extra, num=30, **env):
        path = os.path.join(ROOT, 'section.md')
        with open(path, 'w', newline='') as f:
            f.write(text)
        return run('section', f'o/r#{num}', '--heading', heading, '--scratch', SCRATCH, '--file', path, *extra, **env)

    seed(30, SECTIONED)
    code, out = part('## Decision', 'One fact decides it.\n')
    body = state(30)['body']
    check('section replaces only the named section', code == 0 and 'One fact decides it.' in body and 'Two facts' not in body
          and '2. Names the reasoning under `## Decision`.\n3. Adds the third thing.' in body and 'read back' in out)
    check('section keeps the sections around it', body.startswith('## Why\n\nBecause.\n\n## What\n') and '\n\n## Scope\n\nOut of scope' in body
          and body.endswith('Closes #109\n\n🤖 Generated with [Claude Code](https://claude.com/claude-code)\n'))
    check('section saves the body as read', SECTIONED in saved_bodies())
    code, out = part('## Decision', 'One fact decides it.\n')
    check('a retried section edit changes nothing', code == 0 and state(30).get('edits') == 1 and 'nothing changed' in out)

    seed(30, SECTIONED)
    code, out = part('## Scope', 'Out of scope: #106 and #108.\n')
    body = state(30)['body']
    check('section ends the last section at the closing lines and footer', code == 0
          and '## Scope\n\nOut of scope: #106 and #108.\n\nCloses #109\n\n🤖' in body and '```markdown' not in body)
    seed(30, SECTIONED)
    code, out = part('## Decision', 'Fact.\n\n### A subheading inside\n\nMore.\n')
    check('section takes a deeper heading inside its text', code == 0 and '### A subheading inside' in state(30)['body'])

    for label, heading, text, want in (
            ('a heading the body lacks', '## Missing', 'x\n', 'missing'),
            ('a heading named at another level', '### Decision', 'x\n', 'not '),
            ('a file holding a heading of the same level', '## Decision', 'x\n\n## Another\n', 'end the section early'),
            ('a file holding a higher heading', '## Decision', '# Top\n', 'end the section early'),
            ('a line that is not a heading', 'Decision', 'x\n', 'not a heading line'),
            ('an empty heading', '## ', 'x\n', 'not a heading line')):
        seed(30, SECTIONED)
        code, out = part(heading, text)
        check(f'section refuses {label}', code != 0 and want in out and state(30).get('edits') is None and 'Traceback' not in out)
    seed(30, SECTIONED.replace('## Scope', '## Decision'))
    code, out = part('## Decision', 'x\n')
    check('section refuses a body where the heading\'s line appears twice', code != 0 and 'ambiguous' in out and state(30).get('edits') is None)
    seed(30, SECTIONED.replace('## Scope', '## Decision ##').replace('## Decision\n\nTwo', '## Decision #\n\nTwo'))
    code, out = part('## Decisions', 'x\n')
    check('section names a missing heading as missing', code != 0 and 'missing' in out)
    notes = SECTIONED.replace('3. Adds the third thing.\n', '3. Adds the third thing.\n\n### Notes\n\nA note.\n').replace('## Scope', '## Notes')
    seed(30, notes)
    code, out = part('### Notes', 'Another note.\n')
    body = state(30)['body']
    check('section tells apart two headings with the same words by their exact line', code == 0
          and '### Notes\n\nAnother note.\n\n## Decision' in body and '## Notes\n\nOut of scope' in body)
    seed(30, SECTIONED.replace('## Decision\n\nTwo', '## Decision  \n\nTwo'))
    code, out = part('## Decision', 'One fact.\n')
    check('section finds a heading with trailing spaces', code == 0 and 'One fact.' in state(30)['body'])
    seed(30, SECTIONED.replace('## Decision', '## Using C#').replace('## Scope', '## Using C'))
    code, out = part('## Using C#', 'One fact.\n')
    check('section keeps a trailing # with no space before it as part of the words', code == 0
          and '## Using C#\n\nOne fact.\n\n## Using C\n' in state(30)['body'])
    code, out = part('## using c#', 'One fact.\n')
    check('a trailing # keeps two headings apart by their words too', code != 0 and "written '## Using C#'" in out)
    seed(30, SECTIONED.replace('3. Adds the third thing.\n', '3. Adds the third thing.\n\n### Revision\n\nA subsection.\n'))
    code, out = part('### Revision', 'Another subsection.\n')
    check('section edits a Revision subsection at another level', code == 0 and '### Revision\n\nAnother subsection.' in state(30)['body'])
    seed(30, SECTIONED.replace('## Decision\n\nTwo', '## Decision ##\n\nTwo'))
    code, out = part('## Decision', 'x\n')
    check('section strips a closing run of #s from the words, and names the heading as written', code != 0
          and "written '## Decision ##'" in out and state(30).get('edits') is None)
    seed(30, SECTIONED.replace('## Scope', '### Decision'))
    code, out = part('## decision', 'x\n')
    check('section calls a heading line it cannot find ambiguous when two headings share its words', code != 0
          and 'ambiguous' in out and state(30).get('edits') is None)
    seed(30, SECTIONED + '## Revision\n\n1. `r1` answers round 1.\n')
    code, out = part('## Revision', '1. only one now\n')
    check('section refuses the Revision section and names revision', code != 0 and 'Use revision' in out and state(30).get('edits') is None)
    seed(30, SECTIONED.replace('```\n\nCloses #109', '```\n\nFixes #12 in the parser only.\n\nCloses #109'))
    code, out = part('## Scope', 'New.\n')
    check('section refuses an edit that removes a line which may close an issue, naming it', code != 0
          and "removes 'Fixes #12 in the parser only.', which may close an issue" in out and state(30).get('edits') is None)
    seed(30, SECTIONED.replace('```\n\nCloses #109', '```\n\nFixes #12 in the parser only.\n\nCloses #109'))
    code, out = part('## Decision', 'One fact.\n')
    check('a line which may close an issue does not stop an edit to another section', code == 0 and 'One fact.' in state(30)['body'])
    seed(30, SECTIONED.replace('```\n\nCloses #109', '```\n\nFixes #12 in the parser only.\n\nCloses #109'))
    code, out = part('## Scope', 'New.\n\nFixes #12 in the parser only.\n')
    check('an edit that keeps a line which may close an issue goes through', code == 0
          and '## Scope\n\nNew.\n\nFixes #12 in the parser only.\n\nCloses #109' in state(30)['body'])
    for closing in ('Closes: #12', 'Part of: #108'):
        seed(30, SECTIONED.replace('Closes #109', closing))
        code, out = part('## Scope', 'New.\n')
        check(f'section keeps a closing line with a colon outside the last section: {closing}', code == 0
              and f'## Scope\n\nNew.\n\n{closing}\n\n🤖' in state(30)['body'])
    for closing in ('Closes https://github.com/l3a0/other/issues/3', '- Closes #12', 'Fixes #1; fixes #2', '1. Closes #12',
                    'This change fixes #12.'):
        seed(30, SECTIONED.replace('Closes #109', closing))
        code, out = part('## Scope', 'New.\n')
        check(f'section refuses to remove a closing line it cannot read: {closing}', code != 0
              and 'which may close an issue' in out and state(30).get('edits') is None)
    seed(30, SECTIONED.replace('## Scope', '# Top'))
    code, out = part('## Decision', 'One fact.\n')
    check('section ends at a higher heading', code == 0 and '# Top\n\nOut of scope: nothing.' in state(30)['body'])
    seed(30, SECTIONED)
    code, out = part('## Decision', 'x\n\n```markdown\n## Decision\n```\n')
    check('section takes a heading inside a code fence in its text', code == 0 and state(30)['edits'] == 1)
    for label, heading, text in (('a text whose code fence never closes', '## Decision', '```\ncode\n'),
                                 ('a last section whose text ends in a closing line', '## Scope', 'S.\n\nCloses #5\n')):
        seed(30, SECTIONED)
        code, out = part(heading, text)
        check(f'section refuses {label}, which a second run would change again', code != 0
              and 'a second run would change' in out and state(30).get('edits') is None)
    for closing in ('Closes #118, part of #109.', 'Closes #118 and closes #119', 'Fixes #1, fixes #2'):
        seed(30, SECTIONED.replace('Closes #109', closing))
        code, out = part('## Scope', 'New.\n')
        check(f'section keeps a closing line with several references outside the last section: {closing}', code == 0
              and f'## Scope\n\nNew.\n\n{closing}\n\n🤖' in state(30)['body'])
    for label, line, text in (('a reworded mention of a fix in passing', 'Fixed the stale link from #12 in round 3.', 'New.\n'),
                              ('an example in a code span', '- `Closes #12` now counts as a closing line.', 'New.\n'),
                              ('a closing line kept with other indentation', '  Fixes #12 in the parser.', 'New.\n\nFixes #12 in the parser.\n')):
        seed(30, SECTIONED.replace('Out of scope: nothing.', 'Out of scope: nothing.\n\n' + line))
        code, out = part('## Scope', text)
        check(f'section takes {label}', code == 0 and state(30)['edits'] == 1)
    seed(30, SECTIONED.replace('Out of scope: nothing.', 'Out of scope: nothing.\n\nFixes #12 in the parser.'))
    code, out = part('## Scope', 'New.\n\n```text\nFixes #12 in the parser.\n```\n')
    check('section refuses to count a closing line moved into a code fence as kept', code != 0 and 'which may close an issue' in out)
    seed(30, SECTIONED)
    code, out = part('## Scope', 'New.\n', STUB_LOSE='12')
    check('section reports an issue GitHub no longer reads as closed after the edit, naming it and the body to restore',
          code != 0 and 'no longer reads it as closing o/r#12' in out and 'gh pr edit --body-file' in out)
    seed(30, SECTIONED.replace('Closes #109', 'Closes #3'))
    code, out = part('## Scope', 'New.\n', STUB_LOSE_OTHER='l3a0/other#3')
    check('section names a lost issue of another repository that shares a number with one it still closes', code != 0
          and 'closing l3a0/other#3' in out)
    seed(30, SECTIONED)
    code, out = part('## Decision', 'This change closes #77 as well.\n')
    check('section refuses before sending an edit that adds a closing line, and points at reword',
          code != 0 and 'adds' in out and 'may close an issue' in out and 'reword' in out and state(30).get('edits') is None)
    seed(30, SECTIONED)
    code, out = part('## Decision', 'One fact.\n', STUB_GAIN='77')
    check('section reports an issue GitHub reads as closed after the edit in a form its pattern misses, naming the body to restore',
          code != 0 and 'now reads it as closing o/r#77' in out and 'gh pr edit --body-file' in out and 'reword' in out)
    seed(31)
    code, out = revise('--line', '`ccccccc` answers round 3, which closes #78.', pull='o/r#31')
    check('revision refuses before sending a line that may close an issue', code != 0 and 'closes nothing' in out
          and state(31).get('edits') is None)
    seed(32, SECTIONED)
    part('## Decision', 'One fact.\n', num=32, STUB_LOST='edit')
    pr = state(32)
    pr['body'] = pr['body'].replace('Out of scope: nothing.', 'Out of scope: nothing. This closes #55.')
    json.dump(pr, open(os.path.join(STATE, 'o-r-32.json'), 'w'))
    code, out = part('## Decision', 'One fact.\n', num=32)
    check('a section rerun says what GitHub reads the body as closing', code == 0
          and 'already holds this text' in out and 'closing o/r#109, o/r#55' in out)
    seed(33)
    revise('--line', '`ccccccc` answers round 3.', pull='o/r#33', STUB_LOST='edit')
    code, out = revise('--line', '`ccccccc` answers round 3.', pull='o/r#33')
    check('a revision rerun after a lost edit says what GitHub reads the body as closing', code == 0
          and 'already holds this text' in out and 'GitHub reads the body as closing' in out)
    seed(34, BODY.replace('2. `bbbbbbb` answers round 2.', '2. `bbbbbbb` answers round 2, and fixes #12.'))
    code, out = revise('--line', '`bbbbbbb` answers round 2.', '--replace', '2', pull='o/r#34')
    check('revision refuses to replace an item that holds closing words', code != 0 and 'holds' in out
          and 'by hand' in out and state(34).get('edits') is None)
    seed(31)
    code, out = revise('--line', '`ccccccc` answers round 3, where `fixes #5` was the old wording.', pull='o/r#31')
    check('revision accepts closing words inside a code span', code == 0 and state(31)['edits'] == 1)
    seed(31)
    code, out = revise('--line', '`ccccccc` answers round 3, part of #117.', pull='o/r#31')
    check('revision accepts a line that is part of an issue, which closes nothing', code == 0 and state(31)['edits'] == 1)
    seed(30, SECTIONED)
    code, out = part('## Decision', 'The rest is part of #117.\n')
    check('section accepts an added line that is part of an issue', code == 0 and state(30)['edits'] == 1)
    seed(31)
    code, out = revise('--line', '`ccccccc` answers round 3.', pull='o/r#31', STUB_GAIN='78')
    check('revision reports an issue GitHub reads as closed after its edit, naming revision --replace',
          code != 0 and 'now reads it as closing o/r#78' in out and 'revision --replace' in out)
    seed(31)
    code, out = revise('--line', '`ccccccc` answers round 3.', pull='o/r#31', STUB_LOSE='12')
    check('revision reports an issue GitHub no longer reads as closed after its edit', code != 0 and 'no longer reads it as closing o/r#12' in out)
    module = load()
    inside = SECTIONED.replace('Two facts decide it.', 'One fact decides it.')
    check('the guard passes a change inside the section', not module.changed_outside_section(SECTIONED, inside, '## Decision'))
    grown = SECTIONED.replace('2. The second fact.\n', '2. The second fact.\n\nA paragraph added at the end.\n')
    check('the guard passes a paragraph added at the end of the section', grown != SECTIONED
          and not module.changed_outside_section(SECTIONED, grown, '## Decision'))
    check('the guard refuses a new body shorter than the lines around the section',
          module.changed_outside_section(SECTIONED, SECTIONED.split('## Decision')[0], '## Decision'))
    # The last section before the closing lines ends on a blank line, which the old guard counted twice.
    last = BARE.replace('1. Adds the first thing.\n', '1. Adds the first thing.\n\nA paragraph added at the end.\n')
    check('the guard passes a paragraph added at the end of the section before the closing lines', last != BARE
          and not module.changed_outside_section(BARE, last, '## What'))
    check('the guard still refuses a change to the closing line after that section',
          module.changed_outside_section(BARE, last.replace('Part of #33', 'Part of #34'), '## What'))
    for label, changed in (('before the section', SECTIONED.replace('Because.', 'Why not.')),
                           ('in the heading itself', SECTIONED.replace('\n## Decision\n\nTwo', '\n## Decided\n\nTwo')),
                           ('after the section', SECTIONED.replace('Out of scope: nothing.', 'Out of scope: all.')),
                           ('in the closing line', SECTIONED.replace('Closes #109', 'Part of #109'))):
        check(f'the guard refuses a change {label}', changed != SECTIONED and module.changed_outside_section(SECTIONED, changed, '## Decision'))
    seed(5, SECTIONED)
    code, out = part('## Decision', 'One fact.\n', num=5, STUB_READ_FAIL='after edit')
    check('a failed read after a section edit says the edit may have landed', code != 0 and 'may have landed' in out and 'As sent' in out)
    seed(30, SECTIONED.replace('## Decision\n\nTwo', '## decision\n\nTwo'))
    code, out = part('## Decision', 'x\n')
    check('section refuses a heading written another way, naming how it is written', code != 0 and "'## decision'" in out and state(30).get('edits') is None)
    seed(30, SECTIONED)
    code, out = part('## Decision', 'One fact.\n', '--dry-run')
    check('a section dry run sends nothing and prints the change as a diff', code == 0 and state(30).get('edits') is None
          and '+One fact.' in out and '-Two facts decide it.' in out)
    seed(30, SECTIONED)
    code, out = part('## Decision', 'One fact.\n', STUB_EDIT_ADDS='changed')
    check('a section edit that reads back differently is reported', code != 0 and 'differs from what was sent' in out)
    seed(30, SECTIONED)
    code, out = part('## Decision', 'One fact.\n', STUB_LOST='edit')
    check('a lost section edit says the outcome is unknown', code != 0 and 'outcome is unknown' in out)
    code, out = part('## Decision', 'One fact.\n')
    check('the retry after a lost section edit sends nothing more', code == 0 and state(30)['edits'] == 1 and 'nothing changed' in out)

    # reword: the route for a line that may close an issue, checked against what GitHub then reads the body as closing.
    WORDED = BODY.replace('Because.', 'Round 1 of the review of o/r#265, which closes #247, stalled.')

    def reword(old, new, closes, *extra, num=40, **env):
        paths = []
        for label, text in (('old', old), ('new', new)):
            p = os.path.join(ROOT, f'{label}.txt')
            with open(p, 'w', newline='') as f:
                f.write(text + '\n')
            paths.append(p)
        return run('reword', f'o/r#{num}', '--old', paths[0], '--new', paths[1], '--closes', closes,
                   '--scratch', SCRATCH, '--wait', '0.5', *extra, **env)

    seed(40, WORDED)
    why = os.path.join(ROOT, 'why.txt')
    with open(why, 'w') as f:
        f.write('Round 1 stalled.\n')
    code, out = run('section', 'o/r#40', '--heading', '## Why', '--scratch', SCRATCH, '--file', why)
    check('section points at reword when it refuses to remove a closing line', code != 0 and 'reword' in out and state(40).get('edits') is None)
    code, out = reword('which closes #247,', 'which tracks #247,', 'none')
    check('reword replaces the passage and confirms GitHub no longer reads it as closing', code == 0
          and state(40)['body'] == WORDED.replace('which closes #247,', 'which tracks #247,') and 'as --closes asks' in out)
    check('reword changes nothing outside the passage', state(40)['body'].replace('which tracks #247,', 'which closes #247,') == WORDED)
    code, out = reword('which closes #247,', 'which tracks #247,', 'none')
    check('a rerun after reword sends nothing and checks again', code == 0 and state(40)['edits'] == 1 and 'nothing was sent' in out
          and 'as --closes asks' in out)
    code, out = reword('which closes #247,', 'which tracks #247,', 'none', STUB_GAIN='300')
    check('a rerun after reword still compares what GitHub reads with --closes', code != 0 and 'still closes o/r#300' in out)
    seed(40, WORDED)
    code, out = reword('which closes #247,', 'which tracks #247,', 'none', '--wait', '5', STUB_LAG='3')
    check('reword waits while GitHub still reads the old body as closing', code == 0 and 'as --closes asks' in out)
    seed(40, WORDED)
    code, out = reword('which closes #247,', 'which tracks #247,', 'none', STUB_LAG='1000')
    check('reword exits non-zero naming the issue still closed once its wait runs out', code != 0
          and 'still closes o/r#247' in out and 'gh pr edit --body-file' in out)
    seed(40, WORDED)
    code, out = reword('which closes #247,', 'which fixes #247,', 'none')
    check('reword refuses before sending a new wording that still closes an issue --closes leaves out', code != 0
          and 'names o/r#247' in out and state(40).get('edits') is None)
    seed(40, WORDED.replace('Because.', 'x').replace('stalled.', 'stalled.\n\nRun this, which closes #247:'))
    code, out = reword('Run this, which closes #247:', 'Run this:', '#247')
    check('reword drops a closing phrase from one line while another still closes the issue', code == 0 and 'as --closes asks' in out)
    seed(40, WORDED)
    code, out = reword('which closes #247,', 'the fix for #247,', '#247')
    check('reword refuses before sending a new text that drops an issue --closes still names', code != 0
          and 'does not name o/r#247' in out and state(40).get('edits') is None)
    seed(40, WORDED)
    code, out = reword('stalled.', 'stalled, and fixes #99.', 'o/r#247')
    check('reword refuses before sending a new text that closes an issue --closes does not name', code != 0
          and 'names o/r#99' in out and state(40).get('edits') is None)
    seed(40, WORDED)
    code, out = reword('Round 1 of', 'Round one of', 'o/r#247', STUB_LAG='2', STUB_GAIN='99')
    check('reword keeps reading after a stale read that matches, when --closes asks for the set the body already closed',
          code != 0 and 'still closes o/r#99' in out)
    seed(40, WORDED)
    code, out = reword('Round 1 of', 'Round one of', 'o/r#247', STUB_LAG='2')
    check('reword reports a steady read once every read for the whole wait matches', code == 0 and 'on every read' in out)
    for label, old_text, new_text, closes in (('wraps the passage in a code span', 'o/r#265, which closes #247', '`o/r#265, which closes #247`', 'none'),
                                               ('appends to the passage', 'which closes #247,', 'which closes #247, and tracks #248,', '#247')):
        seed(40, WORDED)
        reword(old_text, new_text, closes, STUB_LOST='edit')
        code, out = reword(old_text, new_text, closes)
        check(f'a rerun after a lost reword edit that {label} sends nothing more', code == 0 and state(40)['edits'] == 1
              and state(40)['body'].count(new_text) == 1 and 'nothing was reworded' in out)
    seed(40, WORDED.replace('stalled.', 'stalled. Closes #123.'))
    code, out = reword('Closes #12', 'Part of #12', 'none')
    check('reword refuses a passage that ends inside a number', code != 0 and 'inside a word or a number' in out
          and state(40).get('edits') is None)
    seed(40, WORDED)
    code, out = reword('loses #247', 'tracks #247', 'none')
    check('reword refuses a passage that starts inside a word', code != 0 and 'inside a word or a number' in out
          and state(40).get('edits') is None)
    seed(40, WORDED)
    code, out = reword('What', 'Changes', 'o/r#247')
    check('reword refuses an edit that changes a heading', code != 0 and 'heading or a code fence' in out
          and state(40).get('edits') is None)
    code, out = reword('Adds the third thing.', 'Adds the third thing.\n```', 'o/r#247')
    check('reword refuses an edit that opens a code fence', code != 0 and 'heading or a code fence' in out
          and state(40).get('edits') is None)
    seed(40, WORDED.replace('stalled.', 'stalled. ab ab ab'))
    code, out = reword('ab ab', 'cd', 'none')
    check('reword counts copies of the passage that overlap', code != 0 and '2 times' in out and state(40).get('edits') is None)
    seed(40, WORDED)
    reword('Adds the first', 'Adds the 1st', 'o/r#247')
    code, out = reword('Adds the first', 'Adds the 1st', 'o/r#247')
    check('a rerun after a finished reword says nothing was reworded', code == 0 and 'nothing was reworded' in out)
    seed(40, WORDED.replace('#247', 'l3a0/other#247'))
    code, out = reword('which closes l3a0/other#247,', 'which tracks l3a0/other#247,', 'none')
    check('reword drops a closing line that names another repository', code == 0 and 'as --closes asks' in out)
    seed(40, WORDED.replace('#247', 'l3a0/other#247'))
    code, out = reword('Round 1 of', 'Round one of', 'l3a0/other#247')
    check('reword keeps an issue of another repository that --closes names with its repository', code == 0 and 'as --closes asks' in out)
    seed(40, WORDED.replace('#247', 'l3a0/other#247'))
    code, out = reword('Round 1 of', 'Round one of', '#247')
    check('reword reads #N in --closes as this repository, not another', code != 0 and 'l3a0/other#247' in out)
    seed(40, WORDED)
    code, out = reword('Round 1 of', 'Round one of', 'O/R#247')
    check('reword reads --closes without regard to case', code == 0 and 'as --closes asks' in out)
    seed(40, WORDED)
    code, out = reword('Round 1 of', 'Round one of', 'o/r#247', STUB_READ_FAIL='after edit')
    check('a failed read after a reword edit says the edit may have landed', code != 0 and 'may have landed' in out and 'As sent' in out)
    seed(40, WORDED)
    code, out = reword('Round 1 of', '## Round 1 of', 'o/r#247')
    check('reword refuses a new passage that makes a heading', code != 0 and 'heading or a code fence' in out and state(40).get('edits') is None)
    seed(40, WORDED.replace('stalled.', 'stalled.\n\n```bash\n# run the tests\nmake test\n```'))
    code, out = reword('make test', 'make check', 'o/r#247')
    check('reword edits a line inside a code fence beside a comment that looks like a heading', code == 0 and 'as --closes asks' in out)
    seed(40, WORDED)
    code, out = reword('which closes #247,', 'which closes #247, part of #14,', '#247')
    check('reword accepts a new passage that is part of an issue --closes does not name', code == 0 and 'as --closes asks' in out)
    seed(40, WORDED.replace('stalled.', 'stalled.\n\n```x``` is the command to run.'))
    code, out = reword('is the command to run.', 'is the command to use.', 'o/r#247')
    check('reword accepts an edit beside a line of inline triple backticks', code == 0 and 'as --closes asks' in out)
    seed(40, WORDED.replace('which closes #247,', 'which tracks #247,'))
    code, out = reword('tracks', 'closes', 'none', STUB_LAG='1000')
    check('reword refuses before sending a passage that turns on a keyword outside it', code != 0
          and 'names o/r#247 after a closing keyword' in out and state(40).get('edits') is None)
    seed(40, WORDED)
    code, out = reword('#247', '#248', '#247', STUB_LAG='1000')
    check('reword refuses before sending a passage that changes the reference after a keyword outside it', code != 0
          and 'o/r#248' in out and state(40).get('edits') is None)
    for wait in ('0', '-5', 'nan'):
        code, out = run('reword', 'o/r#40', '--old', os.path.join(ROOT, 'old.txt'), '--new', os.path.join(ROOT, 'new.txt'),
                        '--closes', 'none', '--scratch', SCRATCH, '--wait', wait)
        check(f'reword refuses --wait {wait}', code != 0 and 'above 0' in out and state(40).get('edits') is None)
    seed(40, WORDED)
    reword('which closes #247,', 'which tracks #247,', 'none', STUB_LAG='1000')
    code, out = reword('which closes #247,', 'which tracks #247,', 'none', STUB_LAG='1000')
    named = out.split('--body-file ')[-1].strip() if '--body-file ' in out else ''
    check('a rerun that still finds a mismatch names a body from before the edit to restore', code != 0 and named
          and 'which closes #247,' in open(named).read())
    seed(40, WORDED)
    code, out = reword('stalled.', 'stalled, and closes l3a0/other#5.', 'o/r#247,#5')
    check('reword refuses before sending an issue of another repository that --closes names only as #N', code != 0
          and 'l3a0/other#5' in out and state(40).get('edits') is None)
    seed(40, WORDED.replace('stalled.', 'stalled.\n\n```text\ncloses #5\n```'))
    code, out = reword('Round 1 of', 'Round one of', 'o/r#247')
    check('reword reads no closing words inside a code fence in the body', code == 0 and 'as --closes asks' in out)
    seed(40, WORDED)
    code, out = reword('stalled.', 'stalled, quoting `closes #5`.', 'o/r#247')
    check('reword reads no closing words inside a code span in the new passage', code == 0 and 'as --closes asks' in out)
    seed(40, WORDED)
    code, out = reword('Round 1 of', 'Round one of', 'o/r#247', STUB_CLOSES_FAIL='1')
    check('a failed closing read after a reword edit says the edit landed and names the body to restore', code != 0
          and 'The edit landed' in out and 'from before the edit is at' in out)
    seed(35, BODY.replace('2. `bbbbbbb` answers round 2.\n\nCloses no issue.', '2. `bbbbbbb` answers round 2.\nCloses no issue.'))
    code, out = reword('Closes no issue.', 'Part of no issue.', 'none', num=35)
    check('reword edits the line right after the Revision list', code == 0 and 'as --closes asks' in out)
    seed(40, WORDED)
    code, out = reword('Adds the', 'Brings the', 'none')
    check('reword refuses a passage the body holds more than once', code != 0 and '3 times' in out and state(40).get('edits') is None)
    code, out = reword('not in the body', 'x', 'none')
    check('reword refuses a passage the body does not hold', code != 0 and 'missing' in out and state(40).get('edits') is None)
    code, out = reword('', 'x', 'none')
    check('reword refuses an empty passage', code != 0 and 'holds no passage' in out and state(40).get('edits') is None)
    code, out = reword('## What', '## Changes', 'o/r#247')
    check('reword refuses a passage that changes a heading', code != 0 and 'heading or a code fence' in out and state(40).get('edits') is None)
    code, out = reword('`bbbbbbb` answers round 2.', '`bbbbbbb` answers round two.', 'none')
    check('reword leaves a Revision line to revision', code != 0 and 'revision with --replace' in out and state(40).get('edits') is None)
    code, out = reword('which closes #247,', 'which tracks #247,', 'o/r#x')
    check('reword refuses a --closes it cannot read', code != 0 and '--closes takes' in out and state(40).get('edits') is None)
    code, out = reword('which closes #247,', 'which tracks #247,', 'none', '--dry-run')
    check('a reword dry run sends nothing and prints the diff and both closing sets', code == 0 and state(40).get('edits') is None
          and '+Round 1 of the review of o/r#265, which tracks #247, stalled.' in out and 'closing o/r#247 now' in out)
    code, out = reword('which closes #247,', 'which tracks #247,', 'none', STUB_OWNER_EDIT='\nAn owner note.')
    check('reword sends nothing over an edit made after its first read', code != 0 and 'changed after it was read' in out
          and state(40).get('edits') is None)
    seed(40, WORDED)
    code, out = reword('which closes #247,', 'which tracks #247,', 'none', STUB_LOST='edit')
    check('a lost reword edit says the outcome is unknown', code != 0 and 'outcome is unknown' in out)
    code, out = reword('which closes #247,', 'which tracks #247,', 'none')
    check('the retry after a lost reword edit sends nothing more', code == 0 and state(40)['edits'] == 1)
    seed(40, WORDED)
    code, out = reword('which closes #247,', 'which tracks #247,', 'none', STUB_EDIT_ADDS='changed')
    check('a reword edit that reads back differently is reported', code != 0 and 'differs from what was sent' in out)

sys.exit(1 if failures else 0)
