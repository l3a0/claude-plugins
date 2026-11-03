#!/usr/bin/env python3
"""Check that each cited phrase is on the page or screen it is cited to.

    python3 -I pg.py book_pages.txt "199:make up the time" "loc1500:one writer per fact"
    python3 -I pg.py book_pages.txt --file cites.txt        # one KEY:PHRASE per line, # starts a comment

Keys are those booktext.py's docstring lists: a printed page (73), front matter (front3), a Kindle location
(loc1500, or L~1500 for an estimated one) or a Kindle page (kp160). Each line of output is one verdict.

    OK     the phrase starts on the cited page, or runs from the end of its body onto the next page
    OK~    the key was written approximate (L~1500) and the phrase is on a neighbouring screen
    NEAR   the phrase is on a neighbouring page only, so the citation is off by one
    MISS   the phrase is not on the cited page or its neighbours
    NOKEY  the text has no page or screen for that key
    SHORT  the phrase has fewer than three words, which is too little to place a citation
    BAD    the argument is not KEY:PHRASE

Every verdict but OK and OK~ names where the phrase does occur. The exit status is 1 when any citation is not OK
or OK~, or when none was given, so a session can run every citation in a pull request through it as a gate.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from booktext import load, locate, norm, parse_key, where  # noqa: E402

MIN_WORDS = 3


def check(blocks, arg):
    key, sep, phrase = arg.partition(':')
    if not sep or not key.strip() or not phrase.strip():
        return 'BAD', f'{arg!r} is not KEY:PHRASE'
    if len(norm(phrase).split()) < MIN_WORDS:
        return 'SHORT', f'{key} {phrase!r} has fewer than {MIN_WORDS} words'
    verdict, _, _ = locate(blocks, key, phrase)
    if verdict == 'NEAR' and parse_key(key)[2]:
        verdict = 'OK~'
    if verdict.startswith('OK'):
        return verdict, f'{key} {phrase!r}'
    return verdict, f'{key} {phrase!r} found on {where(blocks, phrase) or "no block"}'


def main(argv):
    if len(argv) < 2:
        sys.exit(__doc__)
    blocks, args = load(argv[0]), argv[1:]
    if args[0] == '--file':
        with open(args[1], encoding='utf-8') as f:
            args = [ln.strip() for ln in f if ln.strip() and not ln.lstrip().startswith('#')]
    if not args:
        print('no citations to check')
        return 1
    bad = 0
    for arg in args:
        verdict, detail = check(blocks, arg)
        print(f'{verdict:<6} {detail}')
        bad += not verdict.startswith('OK')
    print(f'{len(args) - bad} of {len(args)} OK')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
