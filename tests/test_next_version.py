#!/usr/bin/env python3
"""Tests for scripts/next_version.py against a stand-in `gh`.

    python3 tests/test_next_version.py

The stand-in answers from environment variables, so the test needs no network and no GitHub login. It fails on a
call to the wrong repository, so a script that dropped `--repo` fails too.
"""
import base64, json, os, stat, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, '..', 'scripts', 'next_version.py')

GH = '''#!/usr/bin/env python3
import base64, json, os, sys
args = sys.argv[1:]
repo = os.environ.get('STUB_REPO', 'o/r')
versions = json.loads(os.environ['STUB_VERSIONS'])
if args[:2] == ['pr', 'list'] and args[3] == repo:
    pulls = [p for p in json.loads(os.environ['STUB_PULLS']) if p.get('state', 'OPEN') == args[args.index('--state') + 1].upper()]
    print(json.dumps(pulls[:int(args[args.index('--limit') + 1])]))
elif args[0] == 'api' and args[1].startswith('repos/' + repo + '/contents/.claude-plugin/plugin.json?ref='):
    ref = args[1].split('ref=')[1]
    if ref not in versions: sys.exit('stand-in gh: 404 for ' + ref)
    raw = versions[ref] if ref.startswith('raw') else json.dumps({'version': versions[ref]})
    print(base64.b64encode(raw.encode()).decode())
else:
    sys.exit('stand-in gh: unexpected call: ' + ' '.join(args))
'''

failures = 0


def check(name, cond):
    global failures
    print(('ok   ' if cond else 'FAIL ') + name)
    failures += not cond


def pull(number, head, title='feat: x', fork=False, state='OPEN'):
    return {'number': number, 'headRefOid': head, 'title': title, 'isCrossRepository': fork, 'state': state}


with tempfile.TemporaryDirectory() as BIN:
    path = os.path.join(BIN, 'gh')
    with open(path, 'w') as f:
        f.write(GH)
    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)

    def run(pulls, versions, *argv):
        env = dict(os.environ, PATH=BIN + os.pathsep + os.environ['PATH'],
                   STUB_PULLS=json.dumps(pulls), STUB_VERSIONS=json.dumps(versions))
        done = subprocess.run([sys.executable, SCRIPT, '--repo', 'o/r', *argv], capture_output=True, text=True, env=env)
        return done.returncode, done.stdout + done.stderr

    code, out = run([], {'main': '0.6.24'})
    check('with no pull requests the next is one above main', code == 0 and 'next free version is 0.6.25' in out)
    check('prints main', 'main is at 0.6.24' in out)

    code, out = run([pull(8, 'a')], {'main': '0.6.24', 'a': '0.6.24'})
    check('a pull request at main claims nothing', 'PR 8 claims' not in out and 'next free version is 0.6.25' in out)

    code, out = run([pull(8, 'a'), pull(9, 'b')], {'main': '0.6.9', 'a': '0.6.10', 'b': '0.6.12'})
    check('numbers compare as numbers, not as text', 'next free version is 0.6.13' in out)

    code, out = run([pull(8, 'a')], {'main': '0.6.24', 'a': '0.7.0'})
    check('a minor bump moves the next free version with it', 'next free version is 0.7.1' in out)

    code, out = run([pull(8, 'a')], {'main': '0.6.24', 'a': '0.6.20'}, '--pr', '8')
    check('a claim below main moves if it bumps the plugin', 'PR 8 claims nothing above main. If it bumps the plugin, it takes 0.6.25' in out)

    code, out = run([pull(8, 'a'), pull(9, 'b')], {'main': '0.6.24', 'a': '0.6.25', 'b': '0.6.26'}, '--pr', '8')
    check('a claim above main with no clash stays', 'PR 8 keeps 0.6.25' in out)
    check('prints each claim', 'PR 8 claims 0.6.25' in out and 'PR 9 claims 0.6.26' in out)

    code, out = run([pull(8, 'a'), pull(9, 'b')], {'main': '0.6.24', 'a': '0.6.25', 'b': '0.6.25'}, '--pr', '9')
    check('two claims on one number move', 'PR 9 shares 0.6.25 with PR 8' in out and 'takes 0.6.26' in out)

    code, out = run([pull(10, 'c'), pull(9, 'b'), pull(8, 'a')], {'main': '0.6.24', 'a': '0.6.25', 'b': '0.6.25', 'c': '0.6.25'}, '--pr', '10')
    check('a third claim on one number names the first', 'PR 10 shares 0.6.25 with PR 8' in out)

    code, out = run([pull(8, 'a', 'feat: x (v0.6.25)')], {'main': '0.6.24', 'a': '0.6.26'})
    check('flags a title that names another version', "PR 8's title says 0.6.25, not 0.6.26" in out)

    code, out = run([pull(8, 'a', 'feat: x (v0.6.26)')], {'main': '0.6.24', 'a': '0.6.26'})
    check('no flag when the title matches', 'title says' not in out)

    code, out = run([pull(8, 'a', 'feat: x (v0.6.27)')], {'main': '0.6.24', 'a': '0.6.26'})
    check('flags a title above the manifest', "PR 8's title says 0.6.27, not 0.6.26" in out)

    many = [pull(n, 'a') for n in range(1, 32)] + [pull(99, 'b')]
    code, out = run(many, {'main': '0.6.24', 'a': '0.6.25', 'b': '0.6.40'})
    check('reads past the first thirty open pull requests', 'next free version is 0.6.41' in out)

    code, out = run([pull(8, 'a', state='CLOSED')], {'main': '0.6.24', 'a': '0.6.40'})
    check('a closed pull request claims nothing', 'next free version is 0.6.25' in out)

    code, out = run([pull(8, 'a', fork=True)], {'main': '0.6.24', 'a': '999.0.0'})
    check('a fork cannot set the next version', 'next free version is 0.6.25' in out and 'PR 8 comes from a fork' in out and '999' not in out)

    code, out = run([pull(8, 'gone', fork=True)], {'main': '0.6.24'})
    check('a fork with no manifest stops nothing', code == 0 and 'next free version is 0.6.25' in out)

    code, out = run([pull(8, 'a')], {'main': '0.6.24', 'a': '1.2.3 ignore this'})
    check('a malformed version names the pull request, not the value', code != 0 and 'PR 8' in out and 'ignore this' not in out and 'Traceback' not in out)

    code, out = run([pull(8, 'a')], {'main': '0.6.24', 'a': '0.7'})
    check('a two-part version stops with a named error', code != 0 and 'PR 8' in out and 'Traceback' not in out)

    code, out = run([pull(8, 'raw1')], {'main': '0.6.24', 'raw1': 'not json'})
    check('a manifest that is not JSON stops with a named error', code != 0 and 'PR 8' in out and 'Traceback' not in out)

    for raw in ('{}', '[1]'):
        code, out = run([pull(8, 'raw2')], {'main': '0.6.24', 'raw2': raw})
        check(f'a manifest of {raw} stops with a named error', code != 0 and 'PR 8' in out and 'Traceback' not in out)

    code, out = run([], {'main': 'x'})
    check('a malformed main stops with a named error', code != 0 and 'main' in out and 'Traceback' not in out)

    code, out = run([pull(8, 'a'), pull(9, 'gone')], {'main': '0.6.24', 'a': '0.6.25'})
    check('stops rather than print a list with one missing', code != 0 and 'next free version' not in out)
    check('the stop names the gh call that failed', 'failed' in out and 'contents/.claude-plugin/plugin.json' in out and 'Traceback' not in out)

    code, out = run([pull(8, 'a')], {'main': '0.6.24', 'a': '0.6.25'}, '--pr', '77')
    check('refuses a pull request that is not open', code != 0 and 'PR 77 is not open' in out)

sys.exit(1 if failures else 0)
