#!/usr/bin/env python3
"""Find the printed page or screen of each of the owner's Kindle highlights in the book's text.

    python3 -I hlmap.py book_pages.txt <ASIN>_highlights.json highlights_pages.json

The highlights file is the kindle-highlights skill's JSON, whose `highlights` list carries `loc`, `text` and `note`.
The output lists each highlight with `page`, the citation key of the block it was found on, or `?` when no probe
matched. When the matching probe also occurs on another block, `page` names both, as `28?612`, and the summary
counts them, since the first match may be the wrong one. Matching keeps only letters and digits after
booktext.norm, and tries probes of 50, 35 and 22 characters from the start, a third and the middle of the
highlight, so OCR damage in one spot does not lose the match. Margin text is searched too.
"""
import bisect
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from booktext import load, squash  # noqa: E402


def main(argv):
    if len(argv) != 3:
        sys.exit(__doc__)
    blocks = load(argv[0])
    cat, starts = '', []
    for b in blocks:
        starts.append(len(cat))
        cat += squash(b.text)

    def block_at(pos):
        return blocks[bisect.bisect_right(starts, pos) - 1]

    with open(argv[1], encoding='utf-8') as f:
        highlights = json.load(f)['highlights']
    out, missed, unsure = [], 0, 0
    for h in highlights:
        n, found, q = squash(h.get('text') or ''), -1, ''
        for k in (50, 35, 22):
            for off in (0, len(n) // 3, len(n) // 2):
                q = n[off:off + k]
                if len(q) >= 18 and (found := cat.find(q)) >= 0:
                    break
            if found >= 0:
                break
        if found < 0:
            page, missed = '?', missed + 1
        else:
            page = block_at(found).cite()
            again = cat.find(q, found + 1)
            if again >= 0 and block_at(again) is not block_at(found):
                page, unsure = f'{page}?{block_at(again).cite()}', unsure + 1
        out.append({'loc': h.get('loc'), 'page': page, 'text': h.get('text'), 'note': h.get('note', '')})
    with open(argv[2], 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print(f'mapped {len(out) - missed} of {len(out)}, {unsure} on two blocks; '
          f'notes {sum(bool(h["note"]) for h in out)}')


if __name__ == '__main__':
    main(sys.argv[1:])
