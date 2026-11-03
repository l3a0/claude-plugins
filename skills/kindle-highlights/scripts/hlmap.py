#!/usr/bin/env python3
"""Give each Kindle highlight the printed page it sits on, from the book's full text.

The notebook cites a highlight by Kindle location, which a reader of the printed book cannot use. When the
book's full text exists with one header per printed page, this script finds each highlight in that text and
reports the page it starts on.

    python3 hlmap.py <book_pages.txt> <ASIN>_highlights.json [highlights_pages.json]

<book_pages.txt> holds one block per page, each opened by a header line of the form
"===== <source> | <label> =====", such as "===== pdf 110 | p. 73 =====". The label is what the output records,
and the blocks must run in book order. Text after a "[margin]" marker on a page is left out of the match,
because margin notes and cross-references repeat body text and would pull a highlight onto the wrong page.

A highlight the body text does not hold is then looked for in the margin text alone, and marked "margin": true
when found there. Rapid Development set its chapter epigraphs in the margin column.

Matching ignores case and everything but letters and digits, so OCR spacing and punctuation slips cost
nothing. Each highlight is looked up by a window of its text, 50 characters first, then 35, then 22, taken from
its start, a third of the way in and halfway in, so a garbled opening does not lose it. A window shorter than
18 characters is never tried, which leaves a very short highlight unmatched rather than matched by chance.
A highlight hidden by the export limit has no text and is reported unmatched.

A window can occur on several pages. A heading also sits in the table of contents, and a reference recurs in
a chapter's reading list and in the bibliography. Location order settles most of these: sorted by location,
the highlights must fall on pages in book order, so the script keeps the one candidate page that lies between
the pages of the nearest highlights that matched only once. A highlight still left with several candidates
keeps the first and lists the rest under "also".

Writes highlights_pages.json, one {loc, page, text, note} per highlight in location order, with page "?" where
none matched. Prints the match count, every unmatched highlight and every one still ambiguous.
"""
import bisect
import json
import re
import sys

HEADER = re.compile(r'(?m)^===== (.*?) \| (.*?) =====\n')


def norm(s):
    return re.sub(r'[^a-z0-9]', '', s.lower())


def candidates(text, starts, n):
    """Page indices, in book order, of every place the first window that matches occurs."""
    for k in (50, 35, 22):
        for off in (0, len(n) // 3, len(n) // 2):
            q = n[off:off + k]
            if len(q) < 18:
                continue
            found, at = [], text.find(q)
            while at >= 0:
                page = bisect.bisect_right(starts, at) - 1
                if not found or found[-1] != page:
                    found.append(page)
                at = text.find(q, at + 1)
            if found:
                return found
    return []


def main(pages_path, highlights_path, out_path='highlights_pages.json'):
    parts = HEADER.split(open(pages_path, encoding='utf-8').read())
    # parts = [preamble, source, label, body, source, label, body, ...]
    text, starts, labels, mtext, mstarts = '', [], [], '', []
    for i in range(1, len(parts) - 2, 3):
        body, _, margin = parts[i + 2].partition('\n[margin]')
        starts.append(len(text))
        mstarts.append(len(mtext))
        labels.append(parts[i + 1].strip())
        text += norm(body)
        mtext += norm(margin)
    if not starts:
        sys.exit(f'{pages_path}: no "===== <source> | <label> =====" headers found')
    rows = sorted(json.load(open(highlights_path, encoding='utf-8'))['highlights'], key=lambda h: h['loc'])
    cands = [candidates(text, starts, norm(h.get('text') or '')) for h in rows]
    in_margin = set()
    for i, h in enumerate(rows):
        if not cands[i] and (c := candidates(mtext, mstarts, norm(h.get('text') or ''))):
            cands[i] = c
            in_margin.add(i)

    resolved = 0
    for i, c in enumerate(cands):
        if len(c) < 2:
            continue
        lo = max((d[0] for d in cands[:i] if len(d) == 1), default=0)
        hi = min((d[0] for d in cands[i + 1:] if len(d) == 1), default=len(labels))
        fit = [p for p in c if lo <= p <= hi]
        if len(fit) == 1:
            cands[i] = fit
            resolved += 1

    out, missed, ambiguous = [], [], []
    for i, (h, c) in enumerate(zip(rows, cands)):
        row = {'loc': h['loc'], 'page': labels[c[0]] if c else '?', 'text': h.get('text'), 'note': h.get('note', '')}
        if i in in_margin:
            row['margin'] = True
        if not c:
            missed.append(h)
        elif len(c) > 1:
            row['also'] = [labels[p] for p in c[1:]]
            ambiguous.append(row)
        out.append(row)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print(f'mapped {len(out) - len(missed)} of {len(out)} -> {out_path} '
          f'({len(in_margin)} only in margin text, {resolved} found on several pages and settled by location order, '
          f'{len(ambiguous)} still ambiguous)')
    for h in missed:
        print(f'  unmatched loc {h["loc"]}: {(h.get("text") or "(hidden, no text)")[:80]}')
    for r in ambiguous:
        print(f'  ambiguous loc {r["loc"]}: {r["page"]}, also {", ".join(r["also"])}: {r["text"][:60]}')


if __name__ == '__main__':
    if len(sys.argv) not in (3, 4):
        sys.exit(__doc__)
    main(*sys.argv[1:])
