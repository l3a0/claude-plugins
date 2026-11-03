#!/usr/bin/env python3
"""Print the passage around a phrase on the page or screen it is cited to, to judge what the page supports.

    python3 -I ctx.py book_pages.txt "199:make up the time" "loc1500:one writer per fact"

pg.py says whether a phrase is on its page. This shows the 260 characters either side of it, in the same text
pg.py judged, which is what a reviewer reads to decide whether a rule claims more than the page says. When the
phrase is not there, it names every block where it is. What it prints is book text, so keep it out of every
repository, pull request body and comment.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from booktext import load, locate, norm, where  # noqa: E402

SPAN = 260


def main(argv):
    if len(argv) < 2:
        sys.exit(__doc__)
    blocks = load(argv[0])
    for arg in argv[1:]:
        key, _, phrase = arg.partition(':')
        verdict, text, at = locate(blocks, key, phrase)
        if at < 0:
            print(f'--- {key} [{phrase}] {verdict}: found on {where(blocks, phrase) or "no block"}')
        else:
            print(f'--- {key} [{phrase}] {verdict}:', text[max(0, at - SPAN):at + len(norm(phrase)) + SPAN])


if __name__ == '__main__':
    main(sys.argv[1:])
