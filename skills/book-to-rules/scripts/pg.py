#!/usr/bin/env python3
"""Check that each cited phrase is on the page or screen it is cited to.

    python3 pg.py book_pages.txt "199:make up" "loc1500:one writer per fact"
    python3 pg.py book_pages.txt --file cites.txt        # one KEY:PHRASE per line, # starts a comment

A key is a printed page (73, xiv), front matter (front2) or a Kindle location (loc1500). Each line of output is

    OK    the phrase is on the cited block, or runs from it onto the next
    NEAR  the phrase is on a neighbouring block only, so the citation is off by one
    MISS  the phrase is not on the cited block or its neighbours
    NOKEY the text has no block with that key

NEAR, MISS and NOKEY also name every block where the phrase does occur. The exit status is 1 when any line is
not OK, so a session can run every citation in a pull request through it and stop on the first wrong one.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from booktext import find, load, norm, where  # noqa: E402


def check(blocks, arg):
    key, sep, phrase = arg.partition(':')
    if not sep or not phrase.strip():
        return 'BAD', f'{arg!r} is not KEY:PHRASE'
    q, i = norm(phrase), find(blocks, key)
    if i is None:
        return 'NOKEY', f'{key} {phrase!r} found on {where(blocks, phrase) or "no block"}'
    here = norm(blocks[i].text)
    nxt = norm(blocks[i + 1].text) if i + 1 < len(blocks) else ''
    if q in here or q in here + ' ' + nxt[:len(q)]:
        return 'OK', f'{key} {phrase!r}'
    near = [blocks[j].cite() for j in (i - 1, i + 1) if 0 <= j < len(blocks) and q in norm(blocks[j].text)]
    if near:
        return 'NEAR', f'{key} {phrase!r} is on {near}'
    return 'MISS', f'{key} {phrase!r} found on {where(blocks, phrase) or "no block"}'


def main(argv):
    if len(argv) < 2:
        sys.exit(__doc__)
    blocks, args = load(argv[0]), argv[1:]
    if args[0] == '--file':
        with open(args[1], encoding='utf-8') as f:
            args = [ln.strip() for ln in f if ln.strip() and not ln.lstrip().startswith('#')]
    bad = 0
    for arg in args:
        verdict, detail = check(blocks, arg)
        print(f'{verdict:<5} {detail}')
        bad += verdict != 'OK'
    print(f'{len(args) - bad} of {len(args)} OK')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
