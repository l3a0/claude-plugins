#!/usr/bin/env python3
"""Tests for skills/kindle-highlights/scripts/stitch.py on a synthetic run directory.

    python3 tests/test_stitch.py

The fixture is invented text and arbitrary PNG bytes, so it holds no book text. A stand-in `cutter` module serves
the hand-written OCR lines, so the test needs neither swiftc nor Vision and runs on the Linux CI runner.
"""
import contextlib, io, json, os, sys, tempfile, types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'kindle-highlights', 'scripts'))

failures = 0


def check(name, cond):
    global failures
    print(('ok   ' if cond else 'FAIL ') + name)
    failures += not cond


def line(text, x0, y0, x1=None):
    return {'text': text, 'x0': x0, 'x1': x1 if x1 is not None else min(x0 + 0.4, 0.95), 'y0': y0, 'y1': y0 + 0.02}


LONG = 'body text of a column that runs well past forty characters'
# Two columns: the right column's lines interleave in y with the left column's.
TWO = [line('L1 ' + LONG, 0.06, 0.10), line('R1 ' + LONG, 0.52, 0.11), line('L2 ' + LONG, 0.06, 0.20),
       line('R2 ' + LONG, 0.52, 0.21), line('L3 ' + LONG, 0.06, 0.30), line('R3 ' + LONG, 0.52, 0.31)]
# One column: a right-aligned epigraph and its attribution above the body, a figure label at the right, and a
# full-width line whose centre sits past the middle.
ONE = [line('An epigraph line', 0.60, 0.05), line('Its author', 0.70, 0.08), line('First ' + LONG, 0.06, 0.15),
       line('Wide ' + LONG + ' and more', 0.06, 0.20, x1=0.98), line('label', 0.75, 0.25),
       line('Last ' + LONG, 0.06, 0.30)]
HYPHEN = [line('a broken compu-', 0.06, 0.10), line('tation ends here', 0.06, 0.12),
          line('keeps its dash -', 0.06, 0.14), line('Next sentence starts', 0.06, 0.16)]

import stitch  # noqa: E402  (after the path insert)

check('two-column screen reads left column first',
      stitch.screen_text(TWO).split('\n') == ['L1 ' + LONG, 'L2 ' + LONG, 'L3 ' + LONG,
                                             'R1 ' + LONG, 'R2 ' + LONG, 'R3 ' + LONG])
check('one-column screen keeps top-to-bottom order, epigraph and label in place',
      [t.split()[0] for t in stitch.screen_text(ONE).split('\n')] == ['An', 'Its', 'First', 'Wide', 'label', 'Last'])
check('line-end hyphen joins a lowercase next line and keeps it before an uppercase one',
      stitch.screen_text(HYPHEN) == 'a broken computation ends here\nkeeps its dash -\nNext sentence starts')

with tempfile.TemporaryDirectory() as run:
    pages = os.path.join(run, 'pages')
    os.makedirs(pages)
    screens = {  # name -> (png bytes, ocr lines, label)
        'b000': (b'A', ONE, 'Location 10 of 99'),
        'b001': (b'B', TWO, 'Location 40 of 99'),
        'b002': (b'A', ONE, 'Location 10 of 99'),   # a late flip repeats b000 in mid-book
        'b004': (b'C', HYPHEN, 'Location 70 of 99'),  # b003 is missing
        'b999': (b'D', HYPHEN, 'Location 80 of 99'),
        'b1000': (b'E', HYPHEN, 'Location 90 of 99'),
        'b1001': (b'E', HYPHEN, 'Location 90 of 99'),  # flips past the end
        'b1002': (b'E', HYPHEN, 'Location 90 of 99'),
    }
    ocr_by_name = {}
    for n, (png, lines, label) in screens.items():
        open(os.path.join(pages, n + '.png'), 'wb').write(png)
        json.dump({'label': label}, open(os.path.join(pages, n + '.json'), 'w'))
        ocr_by_name[n] = lines
    for extra in ('crop_10_b000_c0', 'recut_b000_1-2_c0', 'b100r'):
        open(os.path.join(pages, extra + '.png'), 'wb').write(b'X')
    sys.modules['cutter'] = types.SimpleNamespace(ocr=lambda n: ocr_by_name[n])
    cwd = os.getcwd()
    os.chdir(run)
    try:
        stitch.RUN_DIR, stitch.PAGES, stitch.TEXT = run, pages, os.path.join(run, 'text')
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            stitch.main()
    finally:
        os.chdir(cwd)
    report = out.getvalue()
    book = open(os.path.join(run, 'book.txt')).read()
    heads = [l for l in book.split('\n') if l.startswith('=====')]

    check('book.txt holds distinct screens in numeric order, b1000 after b999',
          [h.split()[1] for h in heads] == ['b000', 'b001', 'b004', 'b999', 'b1000'])
    check('each screen is headed by its footer label', heads[0] == '===== b000 | Location 10 of 99 =====')
    check('an odd capture name is reported, crop and recut files are not',
          'skipped b100r.png' in report and 'crop_' not in report and 'recut_' not in report)
    check('missing numbers are reported as ranges', 'series b: missing b003, b005-b998' in report)
    check('a mid-book repeat is named as a likely skip', 'repeat b002 = b000' in report)
    check('the end-of-book repeats are counted, not flagged', 'dropped 2 repeats of b1000 at the end' in report
          and 'repeat b1001' not in report)
    check('every capture gets a text file', len(os.listdir(os.path.join(run, 'text'))) == len(screens))

print(f'{failures} failed')
sys.exit(1 if failures else 0)
