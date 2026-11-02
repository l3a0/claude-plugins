#!/usr/bin/env python3
"""Stitch a full-book Cloud Reader sweep into plain text.

Run from the RUN DIRECTORY after a reader_capture.js sweep has filled pages/ with <name>.png + <name>.json:

    python3 stitch.py            # OCR every capture once (cached as pages/<name>.ocr.jsonl), then write text/ and book.txt

Writes:
  text/<name>.txt   one file per screen: left column, then right column, top to bottom
  book.txt          every distinct screen in name order, each headed by its capture name and the reader's footer
                    label. A screen whose PNG has the same md5 as an earlier one is dropped: missed flips, and the
                    flips past the end of the book that leave the image unchanged.

OCR is Apple Vision through cutter.py's ocr(), which compiles ocr_words.swift into the run directory's bin/ on first
use. A line that ends in a hyphen joins the next line without it when the next line starts lowercase. The price is
that a real compound hyphen that falls at a line end is lost, so check the book's own form where it matters.
"""
import glob, hashlib, json, os, re

from cutter import ocr, PAGES, RUN_DIR

TEXT = os.path.join(RUN_DIR, 'text')
RIGHT_COLUMN_X0 = 0.48  # normalized to the padded PNG


def screen_text(lines):
    """Order lines left column first, then top to bottom; join a trailing hyphen to the next line.

    A line joins the right column only when it STARTS past the page middle, so a single-column page (every line
    starts at the left margin) stays in one column and a two-column page splits cleanly. Splitting by line centre
    instead scrambled single-column pages, because a long line's centre can sit either side of the middle.
    """
    cols = [[], []]
    for L in lines:
        cols[0 if L['x0'] < RIGHT_COLUMN_X0 else 1].append(L)
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


def main():
    os.makedirs(TEXT, exist_ok=True)
    # captures only: a series letter + digits (s000, b492), not the crop_*/recut_* PNGs inspect_highlight.py and cutter.py write
    names = sorted(n for n in (os.path.basename(p)[:-4] for p in glob.glob(os.path.join(PAGES, '*.png')))
                   if re.fullmatch(r'[a-z]\d{3,}', n))
    seen, parts = set(), []
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
        if md5 in seen:
            continue
        seen.add(md5)
        parts.append(f'===== {n} | {label} =====\n{t}\n')
    with open(os.path.join(RUN_DIR, 'book.txt'), 'w') as f:
        f.write('\n'.join(parts))
    print(f'{len(names)} captures, {len(parts)} distinct screens, {sum(len(p) for p in parts):,} chars -> book.txt')


if __name__ == '__main__':
    main()
