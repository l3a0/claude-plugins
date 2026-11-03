#!/usr/bin/env python3
"""Split a book's text into reading parts at chapter starts, one file per reader.

    python3 split_parts.py book_pages.txt parts 1-part1-ch01-03=1 2-part1-ch04-05=73 3-part2-ch06-09=109

Each NAME=KEY starts a part at the block KEY names (a printed page, front2 or loc487), and the part runs to the
next start. The last part runs to the end of the text. Blocks before the first start are left out and counted, so
front matter a reader should see needs a start of its own. Each part keeps its block headers, so a reader cites
from them. The word count per part is printed to balance the readers' loads.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from booktext import find, load  # noqa: E402


def main(argv):
    if len(argv) < 3:
        sys.exit(__doc__)
    blocks, out, specs = load(argv[0]), argv[1], argv[2:]
    starts = []
    for spec in specs:
        name, sep, key = spec.rpartition('=')
        i = find(blocks, key) if sep else None
        if i is None:
            sys.exit(f'{spec}: no block for key {key!r}')
        starts.append((i, name))
    if [i for i, _ in starts] != sorted(i for i, _ in starts) or len({i for i, _ in starts}) < len(starts):
        sys.exit('part starts must be in book order with no repeats')
    os.makedirs(out, exist_ok=True)
    if starts[0][0]:
        print(f'left out {starts[0][0]} blocks before {starts[0][1]}')
    for n, (i, name) in enumerate(starts):
        end = starts[n + 1][0] if n + 1 < len(starts) else len(blocks)
        part = blocks[i:end]
        with open(os.path.join(out, f'{name}.txt'), 'w', encoding='utf-8') as f:
            for b in part:
                f.write(f'===== {b.source} | {b.label} =====\n{b.text}')
        words = sum(len(b.text.split()) for b in part)
        print(f'{name}: {part[0].cite()} to {part[-1].cite()}, {len(part)} blocks, {words} words')


if __name__ == '__main__':
    main(sys.argv[1:])
