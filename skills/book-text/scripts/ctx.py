#!/usr/bin/env python3
"""Check citations against a book's page-numbered text.

    python3 ctx.py BOOK_PAGES.txt PAGE:QUOTE [PAGE:QUOTE ...] [--check] [--width 260]

For each PAGE:QUOTE, prints the text around the quote on that printed page, or NOT FOUND. With --check, prints one
verdict per citation instead: OK when the quote is on the cited page, NEAR when it is only on the page before or
after, and MISS otherwise. Matching ignores case, line breaks and a hyphen that splits a word across lines. Exits 1
when any citation is NOT FOUND or MISS, so a script can stop on a bad citation.
"""
import argparse, pathlib, re, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import booktext  # noqa: E402


def norm(s):
    return re.sub(r'\s+', ' ', re.sub(r'-\n(?=[a-z])', '', s)).lower()


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

    pages = {p: norm(t) for p, t in booktext.read_book(a.book_pages).items()}
    bad = 0
    for page, quote in a.citations:
        q = norm(quote)
        if a.check:
            hits = [p for p in (page - 1, page, page + 1) if q in pages.get(p, '')]
            verdict = 'OK  ' if page in hits else 'NEAR' if hits else 'MISS'
            bad += verdict == 'MISS'
            print(verdict, page, hits, quote)
        else:
            t = pages.get(page, '')
            i = t.find(q)
            bad += i < 0
            print(f'--- p.{page} [{quote}]:', t[max(0, i - a.width):i + len(q) + a.width] if i >= 0 else 'NOT FOUND')
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
