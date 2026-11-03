#!/usr/bin/env python3
"""Tests for skills/book-to-rules/scripts on a synthetic book.

    python3 tests/test_book_to_rules.py

The fixture is invented text in both header forms the scripts read, printed pages and Kindle locations, so it holds
no book text and runs on the Linux CI runner.
"""
import contextlib, io, json, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, '..', 'skills', 'book-to-rules', 'scripts')
sys.path.insert(0, SCRIPTS)

failures = 0


def check(name, cond):
    global failures
    print(('ok   ' if cond else 'FAIL ') + name)
    failures += not cond


PAGES = """===== pdf 1 | front 0 =====
Front matter about the edition.
===== pdf 2 | p. 1 =====
Chapter one opens with a claim about one writer per fact, which the
book makes once here.
===== pdf 3 | p. 2 =====
A sentence that breaks across the page with a hyphenated compu-
tation and ends on a “curly” quote. The tuning procedure starts
===== pdf 4 | p. 3 =====
measured before and after every change.
[margin]
A margin quote the owner highlighted.
===== pdf 5 | p. 4 =====
Chapter two talks about estimates that converge late.
"""

SCREENS = """===== b000 | Page 7 of 90 ● 0% | Location 52 =====
Preface text on the first screen.
===== b001 | Location 80 of 900 ● 9% =====
Screen two holds the lease and the fencing token.
===== b002 | Location 112 of 900 ● 12% =====
Screen three holds the outbox.
"""


def run(script, *args):
    p = subprocess.run([sys.executable, '-I', os.path.join(SCRIPTS, script), *args], capture_output=True, text=True)
    return p.returncode, p.stdout


with tempfile.TemporaryDirectory() as d:
    pages, screens = os.path.join(d, 'book_pages.txt'), os.path.join(d, 'book.txt')
    open(pages, 'w', encoding='utf-8').write(PAGES)
    open(screens, 'w', encoding='utf-8').write(SCREENS)

    import booktext
    blocks = booktext.load(pages)
    check('loader reads every block', [b.cite() for b in blocks] == ['front0', '1', '2', '3', '4'])
    check('parse_key reads every key form', [booktext.parse_key(k) for k in ('73', 'xiv', 'front2', 'loc1500', 'L1500')]
          == [('p', '73'), ('p', 'xiv'), ('front', 2), ('loc', 1500), ('loc', 1500)])
    check('a location falls in the screen that starts at or before it',
          booktext.find(booktext.load(screens), 'loc100') == 1)
    check('a location before the first screen names none', booktext.find(booktext.load(screens), 'loc10') is None)

    code, out = run('pg.py', pages, '1:one writer per fact', '2:computation', '2:"curly" quote',
                    '2:procedure starts measured before', '3:margin quote')
    check('pg passes a phrase on its page, across a hyphen, a curly quote, a page break and a margin',
          code == 0 and out.count('OK') == 6, )
    code, out = run('pg.py', pages, '2:one writer per fact')
    check('pg flags a citation one page off as NEAR and fails', code == 1 and out.startswith('NEAR') and "'1'" in out)
    code, out = run('pg.py', pages, '4:one writer per fact')
    check('pg flags a citation two pages off as MISS and names the right page',
          code == 1 and out.startswith('MISS') and "['1']" in out)
    code, out = run('pg.py', pages, '99:outbox')
    check('pg flags a page the text lacks as NOKEY', code == 1 and out.startswith('NOKEY'))
    code, out = run('pg.py', screens, 'loc100:fencing token', 'L130:outbox')
    check('pg checks Kindle locations', code == 0 and out.count('OK') == 3)
    cites = os.path.join(d, 'cites.txt')
    open(cites, 'w').write('# a comment\n1:one writer\n\n4:converge late\n')
    code, out = run('pg.py', pages, '--file', cites)
    check('pg reads citations from a file and skips comments', code == 0 and '2 of 2 OK' in out)

    code, out = run('ctx.py', pages, '4:estimates')
    check('ctx prints the passage around the phrase', 'chapter two talks about estimates' in out)
    code, out = run('ctx.py', pages, '4:one writer')
    check('ctx says where a phrase it cannot find on the page is', 'NOT FOUND' in out and "['1']" in out)

    parts = os.path.join(d, 'parts')
    code, out = run('split_parts.py', pages, parts, '1-ch1=1', '2-ch2=4')
    one = open(os.path.join(parts, '1-ch1.txt'), encoding='utf-8').read()
    two = open(os.path.join(parts, '2-ch2.txt'), encoding='utf-8').read()
    check('split keeps headers and splits at the chapter start',
          one.startswith('===== pdf 2 | p. 1 =====') and '| p. 3 =====' in one and 'Chapter two' not in one
          and two.startswith('===== pdf 5 | p. 4 ====='))
    check('split reports the front matter it left out', 'left out 1 blocks' in out)
    code, out = run('split_parts.py', pages, parts, '1-a=3', '2-b=1')
    check('split refuses starts out of book order', code != 0)
    code, out = run('pg.py', os.path.join(parts, '1-ch1.txt'), '3:margin quote')
    check('a part file is itself checkable', code == 0)

    hl = os.path.join(d, 'hl.json')
    json.dump({'highlights': [
        {'loc': '10', 'text': 'Chapter one opens with a claim about one writer per fact', 'note': 'keep'},
        {'loc': '20', 'text': 'A margin quote the owner highlighted.', 'note': ''},
        {'loc': '30', 'text': 'Nothing in this book says this sentence at all', 'note': ''}]}, open(hl, 'w'))
    out_json = os.path.join(d, 'hl_pages.json')
    code, out = run('hlmap.py', pages, hl, out_json)
    got = [h['page'] for h in json.load(open(out_json, encoding='utf-8'))]
    check('hlmap maps body and margin highlights and marks a miss', got == ['1', '3', '?'] and 'mapped 2 of 3' in out)

print('all passed' if not failures else f'{failures} failed')
sys.exit(1 if failures else 0)
