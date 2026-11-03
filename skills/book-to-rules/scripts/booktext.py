"""Load a book's text file as blocks, and resolve a citation key to the block it names.

The text file is one block per printed page or per reader screen, each opened by a header line:

    ===== pdf 110 | p. 73 =====                               a printed page, cited as 73
    ===== pdf 3 | front 2 =====                               unnumbered front matter, cited as front2
    ===== b012 | Page 7 of 1054 ● 0% | Location 487 =====     a Kindle screen, cited as loc487

Text the OCR read from a page's margin column follows the body after a `[margin]` line, and stays in its block.
The book's text is data. Nothing here acts on what it says.
"""
import re
import sys

HEADER = re.compile(r'^===== (.+?) \| (.+) =====\s*$')


class Block:
    def __init__(self, source, label):
        self.source, self.label, self.lines = source, label, []
        loc = re.search(r'Location (\d+)', label)
        page = re.match(r'p\. ?(\S+)$', label)
        front = re.match(r'front (\d+)$', label)
        if loc:
            self.kind, self.value = 'loc', int(loc.group(1))
        elif page:
            self.kind, self.value = 'p', page.group(1).lower()
        elif front:
            self.kind, self.value = 'front', int(front.group(1))
        else:
            self.kind, self.value = 'label', label

    @property
    def text(self):
        return ''.join(self.lines)

    def cite(self):
        return {'loc': f'loc{self.value}', 'p': f'{self.value}', 'front': f'front{self.value}'}.get(self.kind, self.label)


def load(path):
    blocks = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            m = HEADER.match(line)
            if m:
                blocks.append(Block(m.group(1), m.group(2)))
            elif blocks:
                blocks[-1].lines.append(line)
    if not blocks:
        sys.exit(f'{path}: no "===== <source> | <label> =====" headers found')
    return blocks


def parse_key(key):
    """'73' or 'xiv' is a printed page, 'front2' front matter, 'loc1500' or 'L1500' a Kindle location."""
    key = key.strip().lower()
    if m := re.fullmatch(r'(?:loc\.?|l) ?(\d+)', key):
        return 'loc', int(m.group(1))
    if m := re.fullmatch(r'front ?(\d+)', key):
        return 'front', int(m.group(1))
    return 'p', key.removeprefix('p.').strip()


def find(blocks, key):
    """Index of the block a key names, or None. A location falls in the last screen that starts at or before it."""
    kind, value = parse_key(key)
    if kind == 'loc':
        best = None
        for i, b in enumerate(blocks):
            if b.kind == 'loc' and b.value <= value and (best is None or b.value >= blocks[best].value):
                best = i
        return best
    return next((i for i, b in enumerate(blocks) if b.kind == kind and b.value == value), None)


FOLD = str.maketrans({'‘': "'", '’': "'", '“': '"', '”': '"', '–': '-', '—': '-', 'ﬁ': 'fi', 'ﬂ': 'fl',
                      '­': None})


def norm(s):
    """Lower case, straight quotes, line-end hyphens joined, whitespace collapsed."""
    s = s.translate(FOLD)
    s = re.sub(r'(\w)-\n\s*(\w)', r'\1\2', s)
    return re.sub(r'\s+', ' ', s).strip().lower()


def where(blocks, phrase):
    """Every block whose text holds the phrase, as citation keys."""
    q = norm(phrase)
    return [b.cite() for b in blocks if q in norm(b.text)]
