#!/usr/bin/env python3
"""Find every run of six or more words a draft shares with the book's full text, before the draft goes public.

    git diff main... > /tmp/x.diff
    python3 -I overlap.py book_pages.txt /tmp/x.diff pr-body.md review-comment.md

A draft is any text bound for a repository or GitHub: a diff, a pull request body, a review comment. Words are
compared after booktext.norm, letters and digits only, so curly quotes and line breaks do not hide a copy. Each
hit prints its file, its line and the shared words, which are book text, so read them and do not paste them
anywhere. The exit status is 1 when any run is found. A common phrase can match by chance, so judge each hit:
the rule is that a draft quotes at most the book's own short phrase.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from booktext import load, norm  # noqa: E402

RUN = 6


def words(s):
    return re.findall(r'[a-z0-9]+', norm(s))


def main(argv):
    if len(argv) < 2:
        sys.exit(__doc__)
    book = words('\n'.join(b.text for b in load(argv[0])))
    grams = {tuple(book[k:k + RUN]) for k in range(len(book) - RUN + 1)}
    hits = 0
    for path in argv[1:]:
        with open(path, encoding='utf-8') as f:
            for n, line in enumerate(f, 1):
                w = words(line.removeprefix('+').removeprefix('-'))
                k = 0
                while k + RUN <= len(w):
                    if tuple(w[k:k + RUN]) in grams:
                        end = k + RUN
                        while end < len(w) and tuple(w[end - RUN + 1:end + 1]) in grams:
                            end += 1
                        print(f'{path}:{n}: {end - k} words shared with the book: {" ".join(w[k:end])}')
                        hits, k = hits + 1, end
                    else:
                        k += 1
    print(f'{hits} runs of {RUN} or more words shared with the book')
    return 1 if hits else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
