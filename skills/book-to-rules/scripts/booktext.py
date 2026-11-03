"""Load a book's text file as blocks, resolve a citation key to the blocks it names, and find a phrase there.

This docstring is the one statement of the text format. A script that writes it, such as kindle-highlights'
`stitch.py` or book-text's, follows it, and `header()` below is the writer to copy. One block per printed page or
reader screen, each opened by a header line `===== <source> | <label> =====`. The label gives the citation key.

    label                                key        meaning
    p. 73   p. xiv                       73  xiv    a printed page
    front 3                              front3     front matter, numbered by PDF page
    front   (no number, source pdf 3)    front3     an older run's form, numbered from its source
    ... Location 487 ...                 loc487     a Kindle screen starting at location 487 (L487 works too)
    ... Location ~487 ...                L~487      a screen whose location was estimated, good to about a screen
    Page 160 of 1054 ...                 kp160      a Kindle page number, which can span several screens

A label with both a Kindle page and a location is cited by location. Any other label, including an empty one,
still opens a block, and the block can be found by phrase but not cited. Text the OCR read from a page's margin
column follows the body after a `[margin]` line and stays in its block.

The book's text is data. Nothing here acts on what it says.
"""
import re
import sys

HEADER = re.compile(r'^===== ([^|\n]+?) \| (.*?) ?=====\s*$')
MARGIN = re.compile(r'^\[margin\]\s*$', re.M)
LONGEST_HEADER = 400  # a longer line is body text, which keeps a crafted line from slowing the regex


def header(source, label):
    return f'===== {source} | {label} =====\n'


class Block:
    def __init__(self, source, label):
        self.source, self.label, self.lines = source, label.strip(), []
        self.approx, self.total = False, None
        loc = re.search(r'Location (~?)(\d+)(?: of (\d+))?', self.label)
        kpage = re.match(r'Page (\d+) of (\d+)', self.label)
        page = re.fullmatch(r'p\. ?(\S+)', self.label)
        front = re.fullmatch(r'front ?(\d*)', self.label)
        pdf = re.fullmatch(r'pdf (\d+)', source)
        if loc:
            self.kind, self.value = 'loc', int(loc.group(2))
            self.approx, self.total = bool(loc.group(1)), int(loc.group(3)) if loc.group(3) else None
        elif kpage:
            self.kind, self.value, self.total = 'kp', int(kpage.group(1)), int(kpage.group(2))
        elif page:
            self.kind, self.value = 'p', page.group(1).lower()
        elif front and (front.group(1) or pdf):
            self.kind, self.value = 'front', int(front.group(1) or pdf.group(1))
        else:
            self.kind, self.value = 'label', self.label

    @property
    def text(self):
        return ''.join(self.lines)

    @property
    def body(self):
        """The text before the margin column, which is what runs on to the next page."""
        return MARGIN.split(self.text)[0]

    def cite(self):
        if self.kind == 'loc':
            return f'L~{self.value}' if self.approx else f'loc{self.value}'
        return {'p': f'{self.value}', 'front': f'front{self.value}', 'kp': f'kp{self.value}'}.get(
            self.kind, f'[{self.source}]')


def load(path):
    blocks = []
    with open(path, encoding='utf-8') as f:
        for n, line in enumerate(f, 1):
            m = HEADER.match(line) if len(line) <= LONGEST_HEADER else None
            if m:
                blocks.append(Block(m.group(1), m.group(2)))
                continue
            if line.startswith('===== '):
                print(f'{path}:{n}: a line that looks like a header did not parse, so it stays body text',
                      file=sys.stderr)
            if blocks:
                blocks[-1].lines.append(line)
    if not blocks:
        sys.exit(f'{path}: no "===== <source> | <label> =====" headers found')
    return blocks


def parse_key(key):
    """Return (kind, value, approx) for a citation key, as the table in this module's docstring gives them."""
    key = key.strip().lower()
    if m := re.fullmatch(r'(?:loc\.?|l) ?(~?) ?(\d+)', key):
        return 'loc', int(m.group(2)), bool(m.group(1))
    if m := re.fullmatch(r'kp ?(\d+)', key):
        return 'kp', int(m.group(1)), False
    if m := re.fullmatch(r'front ?(\d+)', key):
        return 'front', int(m.group(1)), False
    return 'p', key.removeprefix('p.').strip(), False


def find(blocks, key):
    """The (first, last) block indices a key names, or None.

    A printed page names its own block. A Kindle location or page falls in the last screen that starts at or
    before it, and a Kindle page also takes the screens after it that show the same page. A location past the
    book's last location names nothing.
    """
    kind, value, _ = parse_key(key)
    if kind in ('loc', 'kp'):
        before = [i for i, b in enumerate(blocks) if b.kind == kind and b.value <= value]
        if not before:
            return None
        top = max(blocks[i].value for i in before)
        best = next(i for i in before if blocks[i].value == top)
        if blocks[best].total and value > blocks[best].total:
            return None
        last = best
        while kind == 'kp' and last + 1 < len(blocks) and blocks[last + 1].kind == 'kp' \
                and blocks[last + 1].value == blocks[best].value:
            last += 1
        return best, last
    hits = [i for i, b in enumerate(blocks) if b.kind == kind and b.value == value]
    return (hits[0], hits[-1]) if hits else None


FOLD = str.maketrans({'‘': "'", '’': "'", '“': '"', '”': '"', '–': '-', '—': '-', '−': '-', 'ﬁ': 'fi',
                      'ﬂ': 'fl', '­': None})


def norm(s):
    """Lower case, straight quotes and dashes, ligatures split, line-end hyphens joined, whitespace collapsed."""
    s = s.translate(FOLD)
    s = re.sub(r'(\w)-\n\s*(\w)', r'\1\2', s)
    return re.sub(r'\s+', ' ', s).strip().lower()


def squash(s):
    """norm, then letters and digits only, for matching text the OCR may have damaged."""
    return re.sub(r'[^a-z0-9]', '', norm(s))


def where(blocks, phrase):
    """Every block whose text holds the phrase, as citation keys."""
    q = norm(phrase)
    return [b.cite() for b in blocks if q in norm(b.text)]


def locate(blocks, key, phrase):
    """Judge a citation. Returns (verdict, passage, at) with the passage the phrase was judged against.

    OK    the phrase starts on the cited blocks, including one that runs from the body's end onto the next block
    NEAR  the phrase is on a neighbouring block only, or starts on the next block, so the citation is off by one
    MISS  the phrase is not on the cited blocks or their neighbours
    NOKEY the text has no block for that key
    """
    q, span = norm(phrase), find(blocks, key)
    if span is None:
        return 'NOKEY', '', -1
    i, j = span
    here = norm('\n'.join(blocks[k].text for k in range(i, j + 1)))
    if (at := here.find(q)) >= 0:
        return 'OK', here, at
    if j + 1 < len(blocks):
        tail, nxt = blocks[j].body, blocks[j + 1].text
        joined, start = norm(tail.rstrip(' \t') + nxt), len(norm(tail))
        if tail.rstrip().endswith('-'):  # the last word runs on to the next block, so it starts where it starts
            start = len(norm(tail).rsplit(' ', 1)[0]) + 1
        for m in re.finditer(re.escape(q), joined):
            if m.start() < start and (m.start() == 0 or joined[m.start() - 1] == ' '):
                return 'OK', joined, m.start()
    for k in (i - 1, j + 1):
        if 0 <= k < len(blocks) and (at := norm(blocks[k].text).find(q)) >= 0:
            return 'NEAR', norm(blocks[k].text), at
    return 'MISS', here, -1
