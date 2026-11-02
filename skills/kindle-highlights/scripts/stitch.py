#!/usr/bin/env python3
"""Stitch a full-book Cloud Reader sweep into plain text.

Run from the RUN DIRECTORY after a reader_capture.js sweep has filled pages/ with <name>.png + <name>.json:

    python3 stitch.py            # OCR every capture once (cached as pages/<name>.ocr.jsonl), then write text/ and book.txt

Writes:
  text/<name>.txt   one file per screen, in reading order
  book.txt          every distinct screen in capture order, each headed by its capture name and the reader's footer
                    label. A screen whose PNG has the same md5 as an earlier one is dropped.

Prints what it skipped or doubts, so nothing drops silently: a PNG whose name is not a capture name, more than one
series letter, a missing number inside a series, and each dropped repeat. A repeat that is not part of the final
unbroken run of identical screens (the flips past the end of the book) is flagged, because a flip that landed late
repeats a screen and the next flip then skips one.

OCR is Apple Vision through cutter.py's ocr(), which compiles ocr_words.swift and crop.swift into the run directory's
bin/ on first use (needs swiftc). A line that ends in a hyphen joins the next line without it when the next line
starts lowercase. The price is that a real compound hyphen that falls at a line end is lost.
"""
import glob, hashlib, json, os, re, sys

RUN_DIR = os.getcwd()
PAGES = os.path.join(RUN_DIR, 'pages')
TEXT = os.path.join(RUN_DIR, 'text')
CAPTURE = re.compile(r'([a-z])(\d{3,})')  # reader_capture.js names: series letter + number padded to 3 digits
RIGHT_COLUMN_X0 = 0.48  # normalized to the padded PNG; the gutter of a two-column render sits at the middle
LONG_LINE = 40          # characters; body text, as opposed to figure labels and right-aligned short lines


def two_columns(lines):
    """True when the screen has a real right column: at least 3 long lines start past the middle, and they are at
    least a quarter of its long lines.

    Counting every line that starts past the middle is wrong on a one-column render. On the sixth run, 102 of 464
    one-column screens had such lines (figure labels, right-aligned epigraphs, 764 lines in all), and splitting them
    off moved them below the body. Only 10 of those lines were long, never more than one on a screen.
    """
    long_lines = [L for L in lines if len(L['text']) >= LONG_LINE]
    right = [L for L in long_lines if L['x0'] >= RIGHT_COLUMN_X0]
    return len(right) >= 3 and 4 * len(right) >= len(long_lines)


def screen_text(lines):
    """Order lines top to bottom, left column first on a two-column screen; join a trailing hyphen to the next line."""
    if two_columns(lines):
        cols = [[L for L in lines if L['x0'] < RIGHT_COLUMN_X0], [L for L in lines if L['x0'] >= RIGHT_COLUMN_X0]]
    else:
        cols = [list(lines)]
    out = []
    for col in cols:
        col.sort(key=lambda L: (round(L['y0'], 3), L['x0']))
        out.extend(L['text'] for L in col)
    text = ''
    for t in out:
        if text.endswith('-') and t[:1].islower():
            text = text[:-1] + t
        else:
            text += ('\n' if text else '') + t
    return text


def capture_names():
    """Capture names in pages/, sorted by series letter then number (b1000 after b999); print every other PNG."""
    names, other = [], []
    for p in glob.glob(os.path.join(PAGES, '*.png')):
        n = os.path.basename(p)[:-4]
        if CAPTURE.fullmatch(n):
            names.append(n)
        elif not n.startswith(('crop_', 'recut_')):  # inspect_highlight.py and cutter.py write these
            other.append(n)
    for n in sorted(other):
        print(f'skipped {n}.png: not a capture name (series letter + 3 or more digits)')
    names.sort(key=lambda n: (n[0], int(n[1:])))
    series = sorted({n[0] for n in names})
    if len(series) > 1:
        print(f'more than one series: {", ".join(series)}. book.txt holds them in letter order')
    for s in series:
        nums = [int(n[1:]) for n in names if n[0] == s]
        gaps = [(a + 1, b - 1) for a, b in zip(nums, nums[1:]) if b > a + 1]
        if gaps:
            print(f'series {s}: missing ' + ', '.join(f'{s}{a:03d}' if a == b else f'{s}{a:03d}-{s}{b:03d}'
                                                     for a, b in gaps))
    return names


def main():
    from cutter import ocr  # imported here so the tests can load this module without swiftc

    os.makedirs(TEXT, exist_ok=True)
    names = capture_names()
    first_of, repeats = {}, []
    parts = []
    for n in names:
        with open(os.path.join(PAGES, n + '.png'), 'rb') as f:
            md5 = hashlib.md5(f.read()).hexdigest()
        meta_path = os.path.join(PAGES, n + '.json')
        label = ''
        if os.path.exists(meta_path):
            with open(meta_path) as f:
                label = json.load(f).get('label', '')
        t = screen_text(ocr(n))
        with open(os.path.join(TEXT, n + '.txt'), 'w') as f:
            f.write(t + '\n')
        if md5 in first_of:
            repeats.append((n, first_of[md5]))
            continue
        first_of[md5] = n
        parts.append(f'===== {n} | {label} =====\n{t}\n')
    # the final unbroken run of repeats of one screen is the flips past the end of the book
    tail = 0
    while (tail < len(repeats) and repeats[-1 - tail][0] == names[-1 - tail]
           and repeats[-1 - tail][1] == repeats[-1][1]):
        tail += 1
    for n, twin in repeats[:len(repeats) - tail]:
        print(f'repeat {n} = {twin}: a late flip, so check for a skipped screen after {twin}')
    if tail:
        print(f'dropped {tail} repeats of {repeats[-1][1]} at the end (flips past the last screen)')
    with open(os.path.join(RUN_DIR, 'book.txt'), 'w') as f:
        f.write('\n'.join(parts))
    print(f'{len(names)} captures, {len(parts)} distinct screens, {sum(len(p) for p in parts):,} chars -> book.txt')


if __name__ == '__main__':
    sys.exit(main())
