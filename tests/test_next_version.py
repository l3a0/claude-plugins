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
    print(os.environ['STUB_PULLS'])
elif args[0] == 'api' and args[1].startswith('repos/' + repo + '/contents/.claude-plugin/plugin.json?ref='):
    ref = args[1].split('ref=')[1]
    if ref not in versions: sys.exit('stand-in gh: 404 for ' + ref)
    print(base64.b64encode(json.dumps({'version': versions[ref]}).encode()).decode())
else:
    sys.exit('stand-in gh: unexpected call: ' + ' '.join(args))
'''

failures = 0


def check(name, cond):
    global failures
    print(('ok   ' if cond else 'FAIL ') + name)
    failures += not cond


def pull(number, head, title='feat: x'):
    return {'number': number, 'headRefOid': head, 'title': title}


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

    code, out = run([pull(8, 'a')], {'main': '0.6.24', 'a': '0.6.24'})
    check('a pull request at main claims nothing', 'PR 8 claims' not in out and 'next free version is 0.6.25' in out)

    code, out = run([pull(8, 'a'), pull(9, 'b')], {'main': '0.6.9', 'a': '0.6.10', 'b': '0.6.12'})
    check('numbers compare as numbers, not as text', 'next free version is 0.6.13' in out)

    code, out = run([pull(8, 'a')], {'main': '0.6.24', 'a': '0.7.0'})
    check('a minor bump moves the next free version with it', 'next free version is 0.7.1' in out)

    code, out = run([pull(8, 'a')], {'main': '0.6.24', 'a': '0.6.20'}, '--pr', '8')
    check('a claim below main moves', 'PR 8 claims nothing above main, so it takes 0.6.25' in out)

    code, out = run([pull(8, 'a'), pull(9, 'b')], {'main': '0.6.24', 'a': '0.6.25', 'b': '0.6.26'}, '--pr', '8')
    check('a claim above main with no clash stays', 'PR 8 keeps 0.6.25' in out)

    code, out = run([pull(8, 'a'), pull(9, 'b')], {'main': '0.6.24', 'a': '0.6.25', 'b': '0.6.25'}, '--pr', '9')
    check('two claims on one number move', 'PR 9 shares 0.6.25 with PR 8' in out and 'takes 0.6.26' in out)

    code, out = run([pull(8, 'a', 'feat: x (v0.6.25)')], {'main': '0.6.24', 'a': '0.6.26'})
    check('flags a title that names another version', "PR 8's title says 0.6.25, not 0.6.26" in out)

    code, out = run([pull(8, 'a', 'feat: x (v0.6.26)')], {'main': '0.6.24', 'a': '0.6.26'})
    check('no flag when the title matches', 'title says' not in out)

    code, out = run([pull(8, 'a'), pull(9, 'gone')], {'main': '0.6.24', 'a': '0.6.25'})
    check('stops rather than print a list with one missing', code != 0 and 'next free version' not in out)

    code, out = run([pull(8, 'a')], {'main': '0.6.24', 'a': '0.6.25'}, '--pr', '77')
    check('refuses a pull request that is not open', code != 0 and 'PR 77 is not open' in out)

sys.exit(1 if failures else 0)
