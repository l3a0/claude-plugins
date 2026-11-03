"""Shared helpers for the book-text scripts: the page offset, the page-block format and the reading parts.

A page block is one PDF page of text under a header line:

    ===== pdf N | p. M =====

N is the 1-based PDF page number and M the printed page number, so M = N - offset. A page before printed page 1
is labelled `front N` instead, with its PDF page number, so each front matter page keeps a label of its own.
Every script in this folder writes or reads that one format.
"""
import collections, pathlib, re, subprocess, sys

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


def run_dir(path):
    """Create an output folder and return it, refusing one inside a git repository.

    Every output holds a copyrighted book's text or page images, and a folder inside a repository is one
    `git add -A` away from publishing it.
    """
    path = pathlib.Path(path).resolve()
    probe = path
    while not probe.exists():
        probe = probe.parent
    try:
        inside = subprocess.run(['git', '-C', str(probe), 'rev-parse', '--show-toplevel'],
                                capture_output=True, text=True).returncode == 0
    except FileNotFoundError:  # no git, so no repository to leak into
        inside = False
    if inside:
        sys.exit(f'{path} is inside a git repository, so its book text could be committed. Use a folder outside it.')
    path.mkdir(parents=True, exist_ok=True)
    return path


def image_pages(stems):
    """Map each PDF page number to its page image's stem, from the names `pdfimages -png` gives.

    `pdfimages -p -png` names an image p-PPP-NNN, with PPP its 1-based page, so a page with no image or two images
    shows. Plain `pdfimages -png` names it p-NNN, numbering images from 0, which is the page only when every page
    holds exactly one image. Stops on a page with two images, a gap, or a mix of the two names.
    """
    with_page = [re.fullmatch(r'.*-(\d+)-(\d+)', s) for s in stems]
    if all(with_page):
        pages = collections.defaultdict(list)
        for s, m in zip(stems, with_page):
            pages[int(m.group(1))].append(s)
        doubled = [n for n, ss in pages.items() if len(ss) > 1]
        if doubled:
            sys.exit(f'PDF pages {sorted(doubled)} hold more than one image')
        numbered = {n: ss[0] for n, ss in pages.items()}
    else:
        plain = [re.fullmatch(r'.*-(\d+)', s) for s in stems]
        if any(with_page) or not all(plain):
            sys.exit('page image names must all end in -NNN (pdfimages -png) or all in -PPP-NNN (pdfimages -p -png)')
        numbered = {int(m.group(1)) + 1: s for s, m in zip(stems, plain)}
    missing = sorted(set(range(1, max(numbered, default=0) + 1)) - set(numbered))
    if missing:
        sys.exit(f'no page image for PDF pages {missing}')
    return dict(sorted(numbered.items()))


def write_book(out_dir, blocks, parts):
    """Write book_pages.txt and one parts/NAME.txt per part, and print each part's size.

    Part files from an earlier run are removed first, so none is left holding old labels or text.
    """
    out_dir = run_dir(out_dir)
    (out_dir / 'book_pages.txt').write_text('\n'.join(blocks), encoding='utf-8')
    for old in (out_dir / 'parts').glob('*.txt'):
        old.unlink()
    if parts:
        (out_dir / 'parts').mkdir(exist_ok=True)
    for name, first, last in parts:
        seg = [b for b in blocks if (p := printed_page(b)) is not None and first <= p <= last]
        (out_dir / 'parts' / f'{name}.txt').write_text('\n'.join(seg), encoding='utf-8')
        short = f', short of the {last - first + 1} in its range' if len(seg) != last - first + 1 else ''
        print(f'{name}: {len(seg)} pages{short}, {sum(map(len, seg))} chars')


def read_book(path):
    """Read book_pages.txt into {printed page: text}. Front matter pages are left out."""
    text = pathlib.Path(path).read_text(encoding='utf-8')
    heads = list(HEADER.finditer(text))
    pages = {}
    for h, nxt in zip(heads, heads[1:] + [None]):
        if h.group(3):
            pages[int(h.group(3))] = text[h.end() + 1:nxt.start() if nxt else len(text)]
    return pages
