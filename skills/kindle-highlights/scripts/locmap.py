#!/usr/bin/env python3
"""Label each stitched screen of book.txt with an approximate Kindle location.

Some books' reader footer shows Kindle page numbers ("Page 7 of 1054") rather than locations, while the
highlights and every citation use locations. Each highlight is a known passage at a known location, so this
script finds the opening words of every highlight in the OCR text of each screen, pins that screen to the
smallest location found on it, and interpolates the screens between two pinned ones by their order.

    python3 locmap.py [book.txt] [<ASIN>_highlights.json] [book_loc.txt] [--force]

With no arguments it reads book.txt and the one pages/*_highlights.json in the current directory, where the
receiver saves the scrape, or else the one *_highlights.json beside book.txt. Pins must rise with the screens,
so a phrase that also matched an earlier repeat would break the order. The script keeps the longest run of
pins whose locations rise with their screens and drops the rest, so one wrong early pin cannot knock out the
correct pins after it.

Writes book_loc.txt: book.txt with each header extended to "===== b123 | Page P of 1054 | Location N =====" for
a pinned screen and "Location ~N" for an interpolated one. It refuses to write over an input, and over an
existing output unless --force is given. Prints how many screens were pinned, every pin it dropped and every
highlight it did not find.
"""
import bisect
import glob
import json
import os
import re
import sys


def norm(s):
    return re.sub(r'[^a-z0-9]', '', s.lower())


def rising(pins):
    """The longest run of screens, in screen order, whose pinned locations strictly rise."""
    screens = sorted(pins)
    tails, tail_at, back = [], [], [None] * len(screens)
    for j, s in enumerate(screens):
        k = bisect.bisect_left(tails, pins[s])
        if k == len(tails):
            tails.append(pins[s])
            tail_at.append(j)
        else:
            tails[k] = pins[s]
            tail_at[k] = j
        back[j] = tail_at[k - 1] if k else None
    keep, j = [], tail_at[-1] if tail_at else None
    while j is not None:
        keep.append(screens[j])
        j = back[j]
    return keep[::-1]


def main(book='book.txt', highlights=None, out='book_loc.txt', force=False):
    if highlights is None:
        found = glob.glob('pages/*_highlights.json') or glob.glob('*_highlights.json')
        if len(found) != 1:
            sys.exit(f'name the highlights file: found {len(found)} *_highlights.json in pages/ or here')
        highlights = found[0]
    if os.path.realpath(out) in (os.path.realpath(book), os.path.realpath(highlights)):
        sys.exit(f'refusing to write {out} over an input')
    if os.path.exists(out) and not force:
        sys.exit(f'{out} exists: pass --force to replace it, or name another output')
    raw = open(book, encoding='utf-8').read()
    blocks = re.split(r'(?m)^(===== \S+ \| .*? =====)\n', raw)
    preamble, heads, bodies = blocks[0], blocks[1::2], blocks[2::2]
    loose = len(re.findall(r'(?m)^=====.*=====$', raw))
    if loose != len(heads):
        sys.exit(f'{book}: {loose} header-like lines but only {len(heads)} of the form "===== <name> | <label> ====="')
    nbodies = [norm(b) for b in bodies]
    hl = json.load(open(highlights, encoding='utf-8'))['highlights']

    pins, missed, short = {}, [], 0
    for h in hl:
        key = norm(h.get('text') or '')[:45]
        if len(key) < 25:
            short += 1
            continue
        hits = [i for i, b in enumerate(nbodies) if key in b]
        if not hits:
            missed.append(h['loc'])
            continue
        i = hits[0]
        pins[i] = min(pins.get(i, h['loc']), h['loc'])

    keep = rising(pins)
    dropped = {i: pins[i] for i in sorted(set(pins) - set(keep))}
    pins = {i: pins[i] for i in keep}
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

    lines = [preamble]
    for i, (h, body) in enumerate(zip(heads, bodies)):
        loc, exact = loc_of(i)
        lines.append(h[:-6] + f' | Location {"" if exact else "~"}{loc} =====\n' + body)
    open(out, 'w', encoding='utf-8').write(''.join(lines))
    print(f'{len(heads)} screens, {len(pins)} pinned by a highlight, {len(dropped)} pins dropped for breaking '
          f'location order, {len(missed)} highlights not found, {short} too short to look for -> {out}')
    for i, loc in dropped.items():
        print(f'  dropped pin: location {loc} on {heads[i]}')
    for loc in missed:
        print(f'  not found: loc {loc}')


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if a != '--force']
    if len(args) > 3:
        sys.exit(__doc__)
    main(*args, force='--force' in sys.argv[1:])
