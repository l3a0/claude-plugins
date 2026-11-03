"""Shared helpers for the book-text scripts: the page offset, the page-block format and the reading parts.

A page block is one PDF page of text under a header line:

    ===== pdf N | p. M =====

N is the 1-based PDF page number and M the printed page number, so M = N - offset. A page before printed page 1
is labelled `front N` instead, with its PDF page number, so each front matter page keeps a label of its own.
Every script in this folder writes or reads that one format.
"""
import collections, pathlib, re

HEADER = re.compile(r'^===== pdf (\d+) \| (p\. (\d+)|front \d+) =====$', re.M)
PAGE_NUMBER = re.compile(r'\d{1,4}')


def find_offset(pages, edge=3):
    """Find the printed page offset from the page numbers printed in headers and footers.

    `pages` is a list of line lists, one per PDF page, in reading order, with pages[0] being PDF page 1. Any line
    among the first or last `edge` non-empty lines of a page that is a bare number is a page number candidate, and
    it votes for the offset (PDF page number - printed number). Returns (offset, pages_that_agree, votes), where
    votes is a Counter of every offset seen. The offset is None when no page carries a number.
    """
    votes = collections.Counter()
    per_page = []
    for i, lines in enumerate(pages):
        lines = [s.strip() for s in lines if s.strip()]
        seen = {i + 1 - int(s) for s in lines[:edge] + lines[-edge:] if PAGE_NUMBER.fullmatch(s)}
        per_page.append(seen)
        votes.update(seen)
    if not votes:
        return None, 0, votes
    offset = votes.most_common(1)[0][0]
    return offset, sum(offset in s for s in per_page), votes


def label(pdf_no, offset):
    printed = pdf_no - offset
    return f'p. {printed}' if printed >= 1 else f'front {pdf_no}'


def block(pdf_no, offset, text):
    return f'===== pdf {pdf_no} | {label(pdf_no, offset)} =====\n{text}\n'


def printed_page(blk):
    m = HEADER.match(blk)
    return int(m.group(3)) if m and m.group(3) else None


def parse_part(spec):
    """Parse a part given as NAME:FIRST-LAST, a printed page range, into (name, first, last)."""
    m = re.fullmatch(r'([\w.-]+):(\d+)-(\d+)', spec)
    if not m or int(m.group(2)) > int(m.group(3)):
        raise ValueError(f'part {spec!r} is not NAME:FIRST-LAST with FIRST <= LAST')
    return m.group(1), int(m.group(2)), int(m.group(3))


def write_book(out_dir, blocks, parts):
    """Write book_pages.txt and one parts/NAME.txt per part, and print each part's size."""
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / 'book_pages.txt').write_text('\n'.join(blocks), encoding='utf-8')
    if parts:
        (out_dir / 'parts').mkdir(exist_ok=True)
    for name, first, last in parts:
        seg = [b for b in blocks if (p := printed_page(b)) is not None and first <= p <= last]
        (out_dir / 'parts' / f'{name}.txt').write_text('\n'.join(seg), encoding='utf-8')
        print(f'{name}: {len(seg)} pages, {sum(map(len, seg))} chars')


def read_book(path):
    """Read book_pages.txt into {printed page: text}. Front matter pages are left out."""
    text = pathlib.Path(path).read_text(encoding='utf-8')
    heads = list(HEADER.finditer(text))
    pages = {}
    for h, nxt in zip(heads, heads[1:] + [None]):
        if h.group(3):
            pages[int(h.group(3))] = text[h.end() + 1:nxt.start() if nxt else len(text)]
    return pages
