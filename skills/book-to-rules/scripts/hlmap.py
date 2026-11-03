#!/usr/bin/env python3
"""Find the printed page or screen of each of the owner's Kindle highlights in the book's text.

    python3 hlmap.py book_pages.txt <ASIN>_highlights.json highlights_pages.json

The highlights file is the kindle-highlights skill's JSON, whose `highlights` list carries `loc`, `text` and `note`.
The output lists each highlight with the citation key of the block it was found on, `page`, or `?` when no probe
matched. Matching ignores everything but letters and digits, and tries probes of 50, 35 and 22 characters from
the start, a third and the middle of the highlight, so OCR damage in one spot does not lose the match.
"""
import bisect
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from booktext import load  # noqa: E402


def squash(s):
    return re.sub(r'[^a-z0-9]', '', s.lower())


def main(argv):
    if len(argv) != 3:
        sys.exit(__doc__)
    blocks = load(argv[0])
    cat, keys = '', []
    for b in blocks:
        keys.append(len(cat))
        cat += squash(b.text)
    with open(argv[1], encoding='utf-8') as f:
        highlights = json.load(f)['highlights']
    out, missed = [], 0
    for h in highlights:
        n, found = squash(h.get('text') or ''), -1
        for k in (50, 35, 22):
            for off in (0, len(n) // 3, len(n) // 2):
                q = n[off:off + k]
                if len(q) >= 18 and (found := cat.find(q)) >= 0:
                    break
            if found >= 0:
                break
        page = blocks[bisect.bisect_right(keys, found) - 1].cite() if found >= 0 else '?'
        missed += found < 0
        out.append({'loc': h.get('loc'), 'page': page, 'text': h.get('text'), 'note': h.get('note', '')})
    with open(argv[2], 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print(f'mapped {len(out) - missed} of {len(out)}; notes {sum(bool(h["note"]) for h in out)}')


if __name__ == '__main__':
    main(sys.argv[1:])
