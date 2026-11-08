#!/usr/bin/env python3
"""Check hlmap.py, locmap.py, notebook_pages.js, extract_highlights.js, cjs.sh's in-page guard and the reader sweep.

Every input is made up here, so no book text enters the repository. The JavaScript checks run the scripts
against a small DOM mock under macOS's built-in JavaScriptCore shell, `jsc`, and skip where it is missing,
unless `REQUIRE_JSC=1`, which makes a missing `jsc` fail.

    python3 skills/kindle-highlights/tests/test_scripts.py

Prints one line per check and exits non-zero when any fails.
"""
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile

SCRIPTS = pathlib.Path(__file__).resolve().parent.parent / 'scripts'
JSC = '/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc'
failed = []


def check(name, ok, detail=''):
    print(('ok   ' if ok else 'FAIL ') + name + ('' if ok else f'  [{detail}]'))
    if not ok:
        failed.append(name)


def run(*args, cwd=None):
    return subprocess.run([sys.executable, '-I', *map(str, args)], cwd=cwd, capture_output=True, text=True)


PAGES = """===== pdf 1 | front =====
Contents
Sandwich Integration Strategy Overview
===== pdf 2 | p. 10 =====
The first chapter opens with a long sentence about building software carefully and slowly.
===== pdf 3 | p. 11 =====
Sandwich Integration Strategy Overview
Some body text here.
===== pdf 4 | p. 12 =====
Sandwich Integration Strategy Overview appears again as a running head.
===== pdf 5 | p. 13 =====
The last chapter closes with another long sentence about shipping software on time.
[margin] An epigraph that sits only in the margin column of this page, said by somebody.
===== pdf 6 | p. 14 =====
Body text on the final page.
"""
HIGHLIGHTS = {'highlights': [
    {'loc': 100, 'text': 'The first chapter opens with a long sentence about building software', 'note': ''},
    {'loc': 110, 'text': 'Sandwich Integration Strategy Overview', 'note': ''},
    {'loc': 120, 'text': 'The last chapter closes with another long sentence about shipping software', 'note': ''},
    {'loc': 125, 'text': 'An epigraph that sits only in the margin column of this page', 'note': '', 'truncated': True},
    {'loc': 130, 'text': None, 'hidden': True, 'note': ''},
    {'loc': 140, 'text': 'on time', 'note': ''},
]}


def test_hlmap(d):
    (d / 'book_pages.txt').write_text(PAGES)
    (d / 'hl.json').write_text(json.dumps(HIGHLIGHTS))
    r = run(SCRIPTS / 'hlmap.py', 'book_pages.txt', 'hl.json', cwd=d)
    check('hlmap runs', r.returncode == 0, r.stderr)
    out = {x['loc']: x for x in json.loads((d / 'highlights_pages.json').read_text())}
    check('hlmap maps a unique highlight to its page', out[100]['page'] == 'p. 10', out[100])
    check('hlmap keeps a repeated heading off the table of contents',
          out[110]['page'] == 'p. 11' and out[110].get('also') == ['p. 12'], out[110])
    check('hlmap finds a highlight in margin text only', out[125]['page'] == 'p. 13' and out[125].get('margin'), out[125])
    check('hlmap carries the truncated flag', out[125]['truncated'] is True, out[125])
    check('hlmap leaves a hidden highlight unmatched', out[130]['page'] == '?' and out[130]['hidden'], out[130])
    check('hlmap never tries a window under 18 characters', out[140]['page'] == '?', out[140])
    check('hlmap prints its counts', 'mapped 4 of 6' in r.stdout, r.stdout)
    r = run(SCRIPTS / 'hlmap.py', 'book_pages.txt', 'hl.json', cwd=d)
    check('hlmap refuses to replace an existing output', r.returncode != 0 and 'exists' in r.stderr, r.stderr)
    r = run(SCRIPTS / 'hlmap.py', 'book_pages.txt', 'hl.json', 'hl.json', '--force', cwd=d)
    check('hlmap refuses to write over an input even with --force',
          r.returncode != 0 and json.loads((d / 'hl.json').read_text()) == HIGHLIGHTS, r.stderr)
    r = run(SCRIPTS / 'hlmap.py', 'book_pages.txt', 'hl.json', '--force', cwd=d)
    check('hlmap replaces an existing output with --force', r.returncode == 0, r.stderr)


BOOK = """front matter before the first screen
===== b0 | Page 1 of 6 =====
alpha alpha opening screen with the first highlighted passage of the book here
===== b1 | Page 2 of 6 =====
second screen says a recurring phrase that the author repeats later in the book verbatim
===== b2 | Page 3 of 6 =====
third screen carries the second highlighted passage about something quite different
===== b3 | Page 4 of 6 =====
fourth screen carries the third highlighted passage about yet another different subject
===== b4 | Page 5 of 6 =====
fifth screen repeats a recurring phrase that the author repeats later in the book verbatim and more
===== b5 | Page 6 of 6 =====
sixth screen is the last one with the closing highlighted passage of the whole book
"""
LOC_HL = {'highlights': [
    {'loc': 10, 'text': 'opening screen with the first highlighted passage of the book'},
    {'loc': 30, 'text': 'the second highlighted passage about something quite different'},
    {'loc': 40, 'text': 'the third highlighted passage about yet another different subject'},
    {'loc': 50, 'text': 'a recurring phrase that the author repeats later in the book verbatim'},
    {'loc': 60, 'text': 'the closing highlighted passage of the whole book'},
]}


def test_locmap(d):
    (d / 'book.txt').write_text(BOOK)
    (d / 'pages').mkdir()
    (d / 'pages' / 'B000TEST01_highlights.json').write_text(json.dumps(LOC_HL))
    r = run(SCRIPTS / 'locmap.py', cwd=d)
    check('locmap finds the highlights under pages/ with no arguments', r.returncode == 0, r.stderr)
    out = (d / 'book_loc.txt').read_text()
    heads = re.findall(r'(?m)^===== (b\d) \| .*\| Location (~?\d+) =====$', out)
    check('locmap keeps the pins that rise and drops the earlier repeat',
          heads == [('b0', '10'), ('b1', '~20'), ('b2', '30'), ('b3', '40'), ('b4', '~50'), ('b5', '60')], heads)
    check('locmap reports the dropped pin', '1 pins dropped' in r.stdout and 'location 50' in r.stdout, r.stdout)
    check('locmap keeps text before the first header', out.startswith('front matter before the first screen\n'), out[:60])
    r = run(SCRIPTS / 'locmap.py', cwd=d)
    check('locmap refuses to replace an existing output', r.returncode != 0 and 'exists' in r.stderr, r.stderr)
    r = run(SCRIPTS / 'locmap.py', 'book.txt', 'pages/B000TEST01_highlights.json', 'book.txt', '--force', cwd=d)
    check('locmap refuses to write over an input', r.returncode != 0 and (d / 'book.txt').read_text() == BOOK, r.stderr)
    (d / 'odd.txt').write_text(BOOK.replace('===== b3 | Page 4', '===== b3 extra | Page 4'))
    r = run(SCRIPTS / 'locmap.py', 'odd.txt', 'pages/B000TEST01_highlights.json', 'odd_loc.txt', cwd=d)
    check('locmap stops on a header it cannot parse', r.returncode != 0 and 'header-like' in r.stderr, r.stderr)


MOCK = r"""
var SCRIPT = arguments[0], SCEN = arguments[1], EXTRACT = arguments[2];
var window = globalThis;
function Row(loc, text, hidden) {
  return { loc, text, hidden, textContent: hidden ? 'hidden or truncated due to export limits' : text,
    querySelector(sel) {
      if (sel === '#kp-annotation-location') return { value: String(loc) };
      if (sel === 'span#highlight') return hidden ? null : { textContent: text };
      if (sel === '#annotationHighlightHeader') return { textContent: 'Yellow highlight | Location: ' + loc };
      if (sel === '#note') return { textContent: '' };
      return null;
    } };
}
var ann = { rows: [], querySelectorAll() { return this.rows; }, appendChild(r) { this.rows.push(r); } };
var tok0 = 'a', pages = {}, fetched = [], clicks = 0, dpHref = 'https://www.amazon.com/dp/DPASIN0001';
function page(rows, next) { return { rows, next }; }
if (SCEN === 'circular') {
  ann.rows = [Row(1, 'alpha one'), Row(2, 'beta two'), Row(3, 'gamma three'), Row(4, 'delta four')];
  pages.a = page([Row(5, 'eps five'), Row(6, 'zeta six'), Row(7, 'beta two'), Row(5, 'eps five longer')], 'b');
  pages.b = page([Row(9, 'nine'), Row(10, null, true), Row(10, null, true), Row(12, 'twelve')], 'c');
  pages.c = page([Row(1, 'alpha one'), Row(2, 'beta two'), Row(3, 'gamma three'), Row(4, 'delta four')], 'a');
} else if (SCEN === 'long') {
  ann.rows = [Row(1, 'r0')]; tok0 = 'p1';
  for (let i = 1; i <= 70; i++) pages['p' + i] = page([Row(10 + i, 'r' + i)], i < 70 ? 'p' + (i + 1) : '');
} else if (SCEN === 'empty') {
  ann.rows = [Row(1, 'r0')]; pages.a = page([], '');
} else if (SCEN === 'mismatch') {
  ann.rows = [Row(1, 'r0')]; pages.a = page([Row(2, 'r2')], ''); window.__khAsin = 'KHASIN0001';
}
var document = {
  title: 'Mock notebook', body: { appendChild() {} },
  querySelector(sel) {
    if (sel === '#kp-notebook-annotations') return ann;
    if (sel === '.kp-notebook-annotations-next-page-start') return { value: tok0 };
    if (sel === '.kp-notebook-content-limit-state') return { value: 's0' };
    if (sel.indexOf('/dp/') >= 0) return { href: dpHref };
    return null;
  },
  querySelectorAll() { return ann.rows; },
  importNode(r) { return r; },
  createElement() { return { click() { clicks++; }, remove() {} }; },
};
var location = { pathname: '/notebook', search: '?asin=URLASIN000', href: 'https://read.amazon.com/notebook?asin=URLASIN000' };
function URLSearchParams(q) { this.q = q; }
URLSearchParams.prototype.get = function (k) { var m = this.q.match(new RegExp('[?&]' + k + '=([^&]*)')); return m ? m[1] : null; };
function Blob() {}
var URL = { createObjectURL() { return 'blob:x'; }, revokeObjectURL() {} };
var setTimeout = function () {};
function DOMParser() {}
DOMParser.prototype.parseFromString = function (key) {
  var p = pages[key] || page([], '');
  return { querySelectorAll() { return p.rows; },
    querySelector(sel) {
      if (sel === '.kp-notebook-annotations-next-page-start') return p.next ? { value: p.next } : null;
      if (sel === '.kp-notebook-content-limit-state') return { value: 's1' };
      return null; } };
};
var fetch = async function (url) {
  fetched.push(url);
  var tok = decodeURIComponent(url.match(/token=([^&]*)/)[1]);
  return { ok: true, status: 200, text: async () => tok };
};
function settle() { for (var i = 0; i < 2000; i++) drainMicrotasks(); }
function runPages() {
  load(SCRIPT); settle();
  var asins = [...new Set(fetched.map(u => u.match(/asin=([^&]*)/)[1]))];
  return { pg: window.__pg, fetchAsins: asins, total: ann.rows.length };
}
var res = {};
if (SCRIPT) { res.run1 = runPages(); if (SCEN === 'long') { fetched = []; res.run2 = runPages(); } }
if (EXTRACT) {
  if (arguments[3] === 'nodl') window.__khNoDownload = true;
  res.ret = JSON.parse(load(EXTRACT));
  res.clicks = clicks;
  res.payload = JSON.parse(window.__khl);
}
print(JSON.stringify(res));
"""


def jsc(d, *args):
    r = subprocess.run([JSC, str(d / 'mock.js'), '--', *map(str, args)], capture_output=True, text=True)
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except (IndexError, ValueError):
        return {'error': r.stdout + r.stderr}


def test_notebook(d):
    (d / 'mock.js').write_text(MOCK)
    nb, ex = SCRIPTS / 'notebook_pages.js', SCRIPTS / 'extract_highlights.js'
    r = jsc(d, nb, 'circular')['run1']
    check('notebook_pages stops when the token loops back', r['pg']['done'] and not r['pg']['capped'] and r['pg']['pages'] == 3, r)
    # 4 rows on the page, 4 new on page a, then 9, two hidden rows at location 10, and 12 on page b.
    check('notebook_pages keeps two hidden rows at one location and drops repeats', r['total'] == 12, r)
    check('notebook_pages takes the ASIN from the /dp/ link, not the URL', r['fetchAsins'] == ['DPASIN0001'], r)
    r = jsc(d, nb, 'long')
    check('notebook_pages stops at its 60-page cap', r['run1']['pg']['capped'] and r['run1']['total'] == 61, r['run1'])
    check('notebook_pages resumes where the cap stopped it', not r['run2']['pg']['capped'] and r['run2']['total'] == 71, r['run2'])
    r = jsc(d, nb, 'empty')['run1']
    check('notebook_pages reports a page with no rows', 'no rows' in (r['pg']['err'] or '') and r['total'] == 1, r)
    r = jsc(d, nb, 'mismatch')['run1']
    check('notebook_pages stops when window.__khAsin disagrees with the page', 'disagrees' in (r['pg']['err'] or '') and not r['fetchAsins'], r)
    r = jsc(d, '', 'circular', ex, 'nodl')
    check('extract_highlights skips the download when asked', r['clicks'] == 0 and r['ret']['downloaded'] is None, r)
    check('extract_highlights names the /dp/ link, not the URL', r['payload']['book']['asin'] == 'DPASIN0001', r)
    r = jsc(d, '', 'circular', ex)
    check('extract_highlights downloads by default', r['clicks'] == 1 and r['ret']['downloaded'] == 'DPASIN0001_highlights.json', r)


SWEEP_MOCK = r"""
// Drives reader_capture.js's sweep against a mocked book on a fake clock. A flip renders RENDER_MS after the click,
// later than the 1.3 s settle, so the sweep only sees it if it waits. SCEN picks the book and what goes wrong.
var SCEN = arguments[1], PLAN = arguments[2] ? JSON.parse(readFile(arguments[2])) : null;
var posted = [], bodies = [], atPost = [], now = 0, RENDER_MS = 2000;
Date.now = function () { return now; };
var window = this;
var document = { visibilityState: 'visible', querySelector: function () { return null; }, querySelectorAll: function () { return []; } };
var localStorage = { getItem: function () { return '{}'; }, setItem: function () {} };
// The post and its reply each settle on a later timer, and the state is recorded as each settles, so code that
// publishes sweepEnd between starting the post and reading its reply is caught.
function settle(f) {
  return new Promise(function (res, rej) {
    setTimeout(function () { atPost.push({ endNull: K.sweepEnd === null, sweeping: K.sweeping }); f(res, rej); }, 0);
  });
}
function fetch(url, o) {
  posted.push(url); bodies.push(o.body);
  if (SCEN === 'postfail') return settle(function (res, rej) { rej(new Error('receiver down')); });
  var reply = 'saved ' + url.split('name=')[1] + ' ' + o.body.length;
  return settle(function (res) { res({ text: function () { return settle(function (r2) { r2(reply); }); } }); });
}
load(arguments[0]);
var K = window.__kh;
if (SCEN === 'slow') { K.END_AFTER = 4; K.FLIP_WAIT_MS = 3000; }
var page = 0, pending = null, flips = 0, captured = 0, out = {};
var LAST = PLAN ? PLAN.filter(function (x) { return x.changed; }).length : 5;
K.sleep = function (ms) { now += ms; return Promise.resolve(); };
K.label = function () { return 'screen ' + page; };
K.imgSrc = function () { if (pending && now >= pending.at) { page = pending.to; pending = null; } return 'blob:' + page; };
K.next = function () {
  flips++;
  var moves = PLAN ? (PLAN[flips - 1] || { changed: false }).changed
    : page < LAST && !(SCEN === 'stall' && flips === 2) && !(SCEN === 'slowstart' && flips <= 2);
  if (moves) pending = { at: now + RENDER_MS, to: page + 1 };
};
K.capture = function (name) {
  captured++;
  if ((SCEN === 'stopped' || SCEN === 'twice') && captured === 2) K.stopSweep();
  if (SCEN === 'hidden' && captured === 2) document.visibilityState = 'hidden';
  if (SCEN === 'err' && captured === 2) return Promise.reject(new Error('canvas failed'));
  return Promise.resolve({ label: K.label() });
};
function report(r) {
  var body = bodies.length ? JSON.parse(bodies[bodies.length - 1]) : [];
  return { end: r, logged: K.sweepLog.length, posted: posted.slice(), sweeping: K.sweeping, page: page,
           bodyLen: body.length, bodyLast: body.length ? body[body.length - 1].name : null,
           unchangedWaits: K.sweepLog.filter(function (x) { return !x.changed; }).map(function (x) { return x.waited; }),
           changedWaits: K.sweepLog.filter(function (x) { return x.changed; }).map(function (x) { return x.waited; }),
           atPost: atPost.slice(), published: JSON.stringify(K.sweepEnd) === JSON.stringify(r),
           bodyBytes: bodies.length ? bodies[bodies.length - 1].length : 0,
           errs: K.sweepLog.filter(function (x) { return x.err; }).map(function (x) { return x.name; }) };
}
var n = SCEN === 'count' ? 3 : 500;
var run = K.sweep(1, n, 'b');
out.endNullWhileRunning = K.sweepEnd === null;
run.then(function (r) {
  out.first = report(r);
  if (SCEN !== 'twice') { print(JSON.stringify(out.first)); return; }
  posted = []; bodies = []; atPost = [];
  var again = K.sweep(100, 500, 'c');
  out.endNullAtSecondStart = K.sweepEnd === null;
  return again.then(function (r2) { out.second = report(r2); print(JSON.stringify(out)); });
});
"""

SWEEP_FIXTURE = pathlib.Path(__file__).parent / 'fixtures' / 'sweeplog-2026-11-08.json'


def test_sweep(d):
    (d / 'sweep.js').write_text(SWEEP_MOCK)
    def run(scen, plan=''):
        try:
            r = subprocess.run([JSC, str(d / 'sweep.js'), '--', str(SCRIPTS / 'reader_capture.js'), scen, str(plan)],
                               capture_output=True, text=True, timeout=60)
        except subprocess.TimeoutExpired:
            return {'error': 'timed out: the sweep never ended'}
        try:
            return json.loads(r.stdout.strip().splitlines()[-1])
        except (IndexError, ValueError):
            return {'error': r.stdout + r.stderr}
    log = 'http://127.0.0.1:8931/json?name=b-sweeplog.json'
    def ended(r, why, logged, last):
        e = r.get('end') or {}
        return (e.get('why') == why and r.get('logged') == logged and e.get('last') == last
                and r.get('posted') == [log] and e.get('saved') == 'saved b-sweeplog.json %d' % r.get('bodyBytes', -1)
                and r.get('published') is True and r.get('sweeping') is False
                and r.get('atPost') == [{'endNull': True, 'sweeping': True}] * 2
                and r.get('bodyLen') == logged and r.get('bodyLast') == last)
    r = run('end')
    # Five flips render the five screens, each 2 s after the click, then three flips change nothing.
    check('sweep waits for each render and stops after three unchanged flips', ended(r, 'end', 8, 'b008') and r['page'] == 5
          and r['end'].get('label') == 'screen 5', r)
    # An unchanged flip waits the full six seconds for a render, then the 1.3-second settle.
    check('an unchanged flip waits FLIP_WAIT_MS for a render', r.get('unchangedWaits') == [7300, 7300, 7300], r)
    # A flip whose page changes stops waiting at the next 150 ms poll after the 2 s render, then settles 1.3 s.
    check('a flip that changes the page stops waiting once it renders', r.get('changedWaits') == [3400] * 5, r)
    r = run('slowstart')
    # Two unchanged flips at the start, one short of END_AFTER, then the book turns: the sweep goes on.
    check('two unchanged flips at the start do not end the sweep', ended(r, 'end', 10, 'b010') and r['page'] == 5, r)
    r = run('slow')
    check('raising END_AFTER gives the sweep more unchanged flips', ended(r, 'end', 9, 'b009'), r)
    check('lowering FLIP_WAIT_MS shortens the wait on an unchanged flip', r.get('unchangedWaits') == [4300] * 4, r)
    r = run('postfail')
    e = r.get('end') or {}
    check('a log post that fails is reported and the sweep still ends', e.get('why') == 'end' and 'receiver down' in (e.get('saveErr') or '')
          and 'saved' not in e and r.get('sweeping') is False and r.get('published') is True
          and r.get('atPost') == [{'endNull': True, 'sweeping': True}], r)
    r = run('stall')
    # The second flip renders nothing, then the book carries on: one unchanged flip mid-book does not end it.
    check('one unchanged flip mid-book resets once the page changes', ended(r, 'end', 9, 'b009') and r['page'] == 5, r)
    r = run('count')
    check('sweep stops after n screens and posts its log', ended(r, 'count', 3, 'b003'), r)
    r = run('stopped')
    check('stopSweep ends a sweep after the screen it is on and posts its log', ended(r, 'stopped', 2, 'b002'), r)
    r = run('hidden')
    check('sweep stops when the tab goes hidden and posts its log', ended(r, 'hidden', 2, 'b002'), r)
    r = run('err')
    check('a capture that fails is logged with its error and the sweep goes on', ended(r, 'end', 8, 'b008') and r['errs'] == ['b002'], r)
    r = run('twice')
    check('sweepEnd is null while a sweep runs', r.get('endNullWhileRunning') is True, r)
    check('a second sweep starts with sweepEnd cleared', r.get('endNullAtSecondStart') is True, r)
    check('a stop from the first sweep does not stop the second', (r.get('first') or {}).get('end', {}).get('why') == 'stopped'
          and (r.get('second') or {}).get('end', {}).get('why') == 'end', r)
    # The first sweep logs two screens before its stop. The second picks up at screen 2 and adds screens 3 to 5 and three
    # unchanged flips, so its log holds eight entries, and six if each sweep started a fresh log.
    f, g = r.get('first') or {}, r.get('second') or {}
    check('the log stays cumulative across sweeps in one page load', f.get('logged') == 2 and g.get('logged') == 8 and g.get('bodyLen') == 8, r)
    plan = json.loads(SWEEP_FIXTURE.read_text())
    tail = next(k for k, x in enumerate(plan) if not x['changed'])
    r = run('replay', SWEEP_FIXTURE)
    # The 2026-11-08 sweep's own sequence of changed and unchanged flips: it stops three flips past the last change.
    check('the recorded 2026-11-08 sweep would stop three flips past its last screen',
          (r.get('end') or {}).get('why') == 'end' and r.get('logged') == tail + 3, {'tail': tail, 'r': r})
    (d / 'empty.json').write_text('[]')
    r = run('replay', d / 'empty.json')
    # A sweep started on the last screen: its first three flips change nothing, so it stops at the third.
    check('a sweep started at the end stops after END_AFTER flips', ended(r, 'end', 3, 'b003'), r)


def test_cjs_guard(d):
    guard = re.search(r"^GUARD='(.*)'$", (SCRIPTS / 'cjs.sh').read_text(), re.M).group(1)
    for origin, ok in (('https://read.amazon.com', True), ('https://read.amazon.com.evil.example', False),
                       ('https://www.amazon.com', False), ('http://read.amazon.com', False)):
        (d / 'g.js').write_text(f'var location = {{ origin: {json.dumps(origin)} }};\n'
                                f'try {{ {guard}\nprint("ran"); }} catch (e) {{ print("refused"); }}\n')
        out = subprocess.run([JSC, str(d / 'g.js')], capture_output=True, text=True).stdout.strip()
        check(f'cjs.sh guard {"runs" if ok else "refuses"} on {origin}', out == ('ran' if ok else 'refused'), out)


with tempfile.TemporaryDirectory() as t:
    t = pathlib.Path(t)
    for name, fn in (('hlmap', test_hlmap), ('locmap', test_locmap)):
        (t / name).mkdir()
        fn(t / name)
    if os.path.exists(JSC):
        for name, fn in (('notebook', test_notebook), ('cjs', test_cjs_guard), ('sweep', test_sweep)):
            (t / name).mkdir()
            fn(t / name)
    elif os.environ.get('REQUIRE_JSC') == '1':
        check('jsc exists, as REQUIRE_JSC asks', False, JSC)
    else:
        print('skip JavaScript checks: no jsc at ' + JSC)
print(f'{len(failed)} failed' if failed else 'all passed')
sys.exit(1 if failed else 0)
