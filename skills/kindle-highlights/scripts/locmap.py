#!/usr/bin/env python3
"""Label each stitched screen of book.txt with an approximate Kindle location.

Some books' reader footer shows Kindle page numbers ("Page 7 of 1054") rather than locations, while the
highlights and every citation use locations. Each highlight is a known passage at a known location, so this
script finds the opening words of every highlight in the OCR text of each screen, pins that screen to the
smallest location found on it, and interpolates the screens between two pinned ones by their order.

    python3 locmap.py [book.txt] [<ASIN>_highlights.json] [book_loc.txt]

With no arguments it reads book.txt and the one *_highlights.json in the current directory, which is how
stitch.py leaves a run directory. Writes book_loc.txt: book.txt with each header extended to
"===== b123 | Page P of 1054 | Location N =====" for a pinned screen and "Location ~N" for an interpolated one,
and prints how many screens were pinned and how many highlights were not found.
"""
import glob
import json
import re
import sys


def norm(s):
    return re.sub(r'[^a-z0-9]', '', s.lower())


def main(book='book.txt', highlights=None, out='book_loc.txt'):
    if highlights is None:
        found = glob.glob('*_highlights.json')
        if len(found) != 1:
            sys.exit(f'name the highlights file: found {len(found)} *_highlights.json here')
        highlights = found[0]
    blocks = re.split(r'(?m)^(===== \S+ \| .*? =====)\n', open(book, encoding='utf-8').read())
    heads, bodies = blocks[1::2], blocks[2::2]
    nbodies = [norm(b) for b in bodies]
    hl = json.load(open(highlights, encoding='utf-8'))['highlights']

    pins, missed, short = {}, 0, 0
    for h in hl:
        key = norm(h.get('text') or '')[:45]
        if len(key) < 25:
            short += 1
            continue
        hits = [i for i, b in enumerate(nbodies) if key in b]
        if not hits:
            missed += 1
            continue
        i = hits[0]
        pins[i] = min(pins.get(i, h['loc']), h['loc'])

    # Drop pins that break the order, such as a short key that matched an earlier repeat of the phrase.
    clean, last = {}, -1
    for i in sorted(pins):
        if pins[i] > last:
            clean[i] = pins[i]
            last = pins[i]
    pins = clean
    if len(pins) < 2:
        sys.exit(f'only {len(pins)} screen(s) pinned by a highlight, too few to interpolate')
    ks = sorted(pins)
    slope = (pins[ks[-1]] - pins[ks[0]]) / (ks[-1] - ks[0])

    def loc_of(i):
        if i in pins:
            return pins[i], True
        before = [k for k in ks if k < i]
        after = [k for k in ks if k > i]
        if before and after:
            a, b = before[-1], after[0]
            return round(pins[a] + (pins[b] - pins[a]) * (i - a) / (b - a)), False
        # Past the first or last pin, extrapolate at the pinned span's average locations per screen.
        if before:
            a = before[-1]
            return round(pins[a] + slope * (i - a)), False
        b = after[0]
        return max(1, round(pins[b] - slope * (b - i))), False

    lines = []
    for i, (h, body) in enumerate(zip(heads, bodies)):
        loc, exact = loc_of(i)
        lines.append(h[:-6] + f' | Location {"" if exact else "~"}{loc} =====\n' + body)
    open(out, 'w', encoding='utf-8').write(''.join(lines))
    print(f'{len(heads)} screens, {len(pins)} pinned by a highlight, {missed} highlights not found, '
          f'{short} too short to look for -> {out}')


if __name__ == '__main__':
    if len(sys.argv) > 4:
        sys.exit(__doc__)
    main(*sys.argv[1:])
