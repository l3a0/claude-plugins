#!/usr/bin/env python3
"""Find the printed page or screen of each of the owner's Kindle highlights in the book's text.

    python3 -I hlmap.py book_pages.txt <ASIN>_highlights.json highlights_pages.json

The highlights file is the kindle-highlights skill's JSON, whose `highlights` list carries `loc`, `text` and `note`.
The output lists each highlight with `page`, the citation key of the block it was found on, or `?` when no probe
matched. Matching keeps only letters and digits after booktext.norm, and tries probes of 50, 35 and 22 characters
from the start, a third and the middle of the highlight, so OCR damage in one spot does not lose the match.
Margin text is searched too.

A probe can match in more than one place, such as a reading-list entry that recurs in the bibliography, or a
heading that also sits in the table of contents. Kindle locations run in book order, so the highlights with one
match that also keep that order serve as anchors, and a repeated match takes the copy nearest where the anchors
around its location put it. Such a highlight lists its other pages under `also`. A highlight whose page still
breaks location order is marked `"check": "out of location order"`, since its only match may be the wrong copy.
"""
import bisect
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from booktext import load, squash  # noqa: E402

MAX_COPIES = 50


def matches(cat, n):
    """Every position of the first probe that matches anywhere, or []."""
    for k in (50, 35, 22):
        for off in (0, len(n) // 3, len(n) // 2):
            q = n[off:off + k]
            if len(q) >= 18 and (at := cat.find(q)) >= 0:
                found = [at]
                while len(found) < MAX_COPIES and (at := cat.find(q, at + 1)) >= 0:
                    found.append(at)
                return found
    return []


def longest_in_order(points):
    """The longest run of (loc, pos) points, in loc order, whose positions never go backwards."""
    tails, prev, ends = [], [None] * len(points), []
    for i, (_, pos) in enumerate(points):
        k = bisect.bisect_right(tails, pos)
        prev[i] = ends[k - 1] if k else None
        if k == len(tails):
            tails.append(pos)
            ends.append(i)
        else:
            tails[k], ends[k] = pos, i
    keep, i = [], ends[-1] if ends else None
    while i is not None:
        keep.append(points[i])
        i = prev[i]
    return keep[::-1]


def location(h):
    try:
        return int(h.get('loc'))
    except (TypeError, ValueError):
        return None


def main(argv):
    if len(argv) != 3:
        sys.exit(__doc__)
    if os.path.realpath(argv[2]) in {os.path.realpath(p) for p in argv[:2]}:
        sys.exit('the output path is one of the inputs, so it would overwrite them')
    blocks = load(argv[0])
    cat, starts = '', []
    for b in blocks:
        starts.append(len(cat))
        cat += squash(b.text)

    def block_at(pos):
        return blocks[bisect.bisect_right(starts, pos) - 1]

    with open(argv[1], encoding='utf-8') as f:
        highlights = json.load(f)['highlights']
    found = [matches(cat, squash(h.get('text') or '')) for h in highlights]
    anchors = longest_in_order(sorted((location(h), c[0]) for h, c in zip(highlights, found)
                                      if len(c) == 1 and location(h) is not None))
    locs = [loc for loc, _ in anchors]

    def bounds(loc):
        """Positions of the nearest anchors at an earlier and a later location, or None where there is none."""
        i, j = bisect.bisect_left(locs, loc), bisect.bisect_right(locs, loc)
        return (anchors[i - 1][1] if i else None), (anchors[j][1] if j < len(anchors) else None)

    def index(pos):
        return bisect.bisect_right(starts, pos) - 1

    out, missed, resolved, unordered = [], 0, 0, 0
    for h, copies in zip(highlights, found):
        row = {'loc': h.get('loc'), 'page': '?', 'text': h.get('text'), 'note': h.get('note', '')}
        loc = location(h)
        if not copies:
            missed += 1
        else:
            lo, hi = bounds(loc) if loc is not None and anchors else (None, None)
            pick = copies[0]
            if len(copies) > 1 and (lo is not None or hi is not None):
                guess = lo if hi is None else hi if lo is None else (lo + hi) / 2
                pick = min(copies, key=lambda p: abs(p - guess))
                resolved += 1
            row['page'] = block_at(pick).cite()
            others = sorted({block_at(p).cite() for p in copies if block_at(p) is not block_at(pick)})
            if others:
                row['also'] = others
            # Compare blocks, not positions, since a page's margin text follows its body whatever the location.
            if (lo is not None and index(pick) < index(lo)) or (hi is not None and index(pick) > index(hi)):
                row['check'] = 'out of location order'
                unordered += 1
        out.append(row)
    with open(argv[2], 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print(f'mapped {len(out) - missed} of {len(out)}, {resolved} repeats placed by location order, '
          f'{unordered} out of location order; notes {sum(bool(h["note"]) for h in out)}')


if __name__ == '__main__':
    main(sys.argv[1:])
