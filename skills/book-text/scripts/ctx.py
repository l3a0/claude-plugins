#!/usr/bin/env python3
"""Check citations against a book's page-numbered text.

    python3 ctx.py BOOK_PAGES.txt PAGE:QUOTE [PAGE:QUOTE ...] [--check] [--width 260]

For each PAGE:QUOTE, prints the text around the quote on that printed page, in the book's own case, or NOT FOUND.
A quote that starts on the cited page and runs onto the next one counts as on the cited page. With --check, prints
one verdict per citation instead.

1. OK: the quote is on the cited page, or starts there and runs onto the next.
2. NEAR: the whole quote is on the page before or after instead, so the cited page is probably off by one.
3. MISS: it is on none of them.

Matching ignores case, runs of whitespace, curly against straight quotes, and hyphens, so a word split across lines
and a compound broken at its hyphen both match. Exits 1 when any citation is NOT FOUND or MISS, so a script can stop
on a bad citation. Front matter pages carry no printed number, so they cannot be cited here.
"""
import argparse, pathlib, re, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import booktext  # noqa: E402

FOLD = str.maketrans({'‘': "'", '’': "'", '“': '"', '”': '"'})


def norm(s):
    """Normalize text for matching, and map each output character back to its index in `s`."""
    s = s.translate(FOLD)
    out, where, i = [], [], 0
    while i < len(s):
        ch = s[i]
        if ch == '-':  # drop a hyphen, and the line break after it, so compu-\ntation and self-contained match
            j = i + 1
            while j < len(s) and s[j].isspace() and s[j] != '\n':
                j += 1
            i = j + 1 if j < len(s) and s[j] == '\n' else i + 1
            while i < len(s) and s[i].isspace() and s[i] != '\n':
                i += 1
            continue
        if ch.isspace():
            if not out or out[-1] != ' ':
                out.append(' ')
                where.append(i)
        else:
            out.append(ch.lower())
            where.append(i)
        i += 1
    return ''.join(out), where


def find(text, quote):
    """Find a quote in text. Returns the original text's (start, end), or None."""
    t, where = norm(text)
    q = norm(quote)[0].strip()
    i = t.find(q) if q else -1
    return (where[i], where[i + len(q) - 1] + 1) if i >= 0 else None


def citation(arg):
    m = re.fullmatch(r'(\d+):(.+)', arg, re.S)
    if not m:
        raise argparse.ArgumentTypeError(f'{arg!r} is not PAGE:QUOTE')
    return int(m.group(1)), m.group(2)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('book_pages')
    ap.add_argument('citations', nargs='+', type=citation, metavar='PAGE:QUOTE')
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--width', type=int, default=260, help='characters of context on each side')
    a = ap.parse_args(argv)

    pages = booktext.read_book(a.book_pages)
    bad = 0
    for page, quote in a.citations:
        here = pages.get(page, '')
        spread = here + '\n' + pages.get(page + 1, '')  # a quote may run over the page break
        hit = find(spread, quote)
        if hit and hit[0] >= len(here):
            hit = None  # it starts on the next page, which is not this citation
        if a.check:
            near = [p for p in (page - 1, page + 1) if not hit and find(pages.get(p, ''), quote)]
            verdict = 'OK  ' if hit else 'NEAR' if near else 'MISS'
            bad += verdict == 'MISS'
            print(verdict, page, [page] if hit else near, quote)
        elif hit:
            context = spread[max(0, hit[0] - a.width):hit[1] + a.width]
            print(f'--- p.{page} [{quote}]:', re.sub(r'\s+', ' ', context))
        else:
            bad += 1
            print(f'--- p.{page} [{quote}]: NOT FOUND')
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
