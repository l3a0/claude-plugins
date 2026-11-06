#!/usr/bin/env python3
"""Print the passage around a phrase on the page or screen it is cited to, to judge what the page supports.

    python3 -I ctx.py book_pages.txt "199:make up the time" "loc1500:one writer per fact"
    python3 -I ctx.py --grep book_pages.txt "199:time|schedule" "L~1500:one writer"

pg.py says whether a phrase is on its page. This shows the 260 characters either side of it, in the same text
pg.py judged, which is what a reviewer reads to decide whether a rule claims more than the page says. When the
phrase is not there, it names every block where it is. What it prints is book text, so keep it out of every
repository, pull request body and comment.

With --grep the text after the colon is a regular expression rather than a phrase, for when a reader has the idea and
the page but not the book's words. It searches the cited block and the next one, across line breaks and ignoring case,
and prints the same span around the first match in each block that has one.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from booktext import find, load, locate, norm, where  # noqa: E402

SPAN = 260


def grep(blocks, key, pattern):
    """Return (block, passage) for the first match of pattern in each block the key names and the block after them."""
    span = find(blocks, key)
    if span is None:
        return None
    regex = re.compile(pattern, re.I)
    hits = []
    for block in blocks[span[0]:span[1] + 2]:
        text = ' '.join(block.text.split())
        match = regex.search(text)
        if match:
            hits.append((block, text[max(0, match.start() - SPAN):match.end() + SPAN]))
    return hits


def main(argv):
    use_grep = '--grep' in argv
    argv = [arg for arg in argv if arg != '--grep']
    if len(argv) < 2:
        sys.exit(__doc__)
    blocks = load(argv[0])
    if use_grep:
        for arg in argv[1:]:
            key, _, pattern = arg.partition(':')
            hits = grep(blocks, key, pattern)
            print(f'--- {key} [{pattern}] ' + ('NOKEY' if hits is None else f'{len(hits)} block(s)'))
            for block, passage in hits or []:
                print(f'[{block.label}] {passage}')
        return
    for arg in argv[1:]:
        key, _, phrase = arg.partition(':')
        verdict, text, at = locate(blocks, key, phrase)
        if at < 0:
            print(f'--- {key} [{phrase}] {verdict}: found on {where(blocks, phrase) or "no block"}')
        else:
            print(f'--- {key} [{phrase}] {verdict}:', text[max(0, at - SPAN):at + len(norm(phrase)) + SPAN])


if __name__ == '__main__':
    main(sys.argv[1:])
