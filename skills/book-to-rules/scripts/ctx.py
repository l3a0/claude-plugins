#!/usr/bin/env python3
"""Print the passage around a phrase on the page or screen it is cited to, to judge what the page supports.

    python3 ctx.py book_pages.txt "199:make up" "loc1500:one writer per fact"

pg.py says whether a phrase is on its page. This shows the 260 characters either side, which is what a reviewer
reads to decide whether a rule claims more than the page says. When the phrase is not on the cited block, it
names every block where it is. Keep what it prints out of every repository and comment, since it is book text.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from booktext import find, load, norm, where  # noqa: E402

SPAN = 260


def main(argv):
    if len(argv) < 2:
        sys.exit(__doc__)
    blocks = load(argv[0])
    for arg in argv[1:]:
        key, _, phrase = arg.partition(':')
        i = find(blocks, key)
        text = norm(blocks[i].text) if i is not None else ''
        at = text.find(norm(phrase))
        if at < 0:
            print(f'--- {key} [{phrase}]: NOT FOUND here, found on {where(blocks, phrase) or "no block"}')
        else:
            print(f'--- {key} [{phrase}]:', text[max(0, at - SPAN):at + len(phrase) + SPAN])


if __name__ == '__main__':
    main(sys.argv[1:])
