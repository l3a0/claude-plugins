#!/usr/bin/env python3
"""Turn a PDF that has a text layer into page-numbered text and reading parts.

    python3 text_layer.py BOOK.pdf RUN_DIR [--offset N] [--drop REGEX ...] [--part NAME:FIRST-LAST ...]

Runs `pdftotext -enc UTF-8` into RUN_DIR/book.txt and splits it into pages at the form feeds pdftotext writes
after every page. Without --offset, the offset comes from the page numbers in each page's first and last lines.
Each --drop removes every line that matches it, such as a watermark repeated across pages. Writes
RUN_DIR/book_pages.txt and RUN_DIR/parts/NAME.txt. It also prints every line that is left on two or more pages and
carries a web address, because a download site's watermark usually names the site.
"""
import argparse, collections, pathlib, re, subprocess, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import booktext  # noqa: E402

WEB = re.compile(r'www\.|https?://|\.(com|org|net)\b', re.I)


def split_pages(text):
    pages = text.split('\f')
    if text.endswith('\f'):
        pages.pop()  # pdftotext ends the last page with a form feed too
    return pages


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('pdf')
    ap.add_argument('run_dir')
    ap.add_argument('--offset', type=int, help='PDF page number minus printed page number')
    ap.add_argument('--drop', action='append', default=[], help='regex for a line to remove from every page')
    ap.add_argument('--part', action='append', default=[], type=booktext.parse_part, metavar='NAME:FIRST-LAST')
    a = ap.parse_args(argv)

    run = pathlib.Path(a.run_dir)
    run.mkdir(parents=True, exist_ok=True)
    subprocess.run(['pdftotext', '-enc', 'UTF-8', a.pdf, str(run / 'book.txt')], check=True)
    pages = split_pages((run / 'book.txt').read_text(encoding='utf-8'))

    drops = [re.compile(d) for d in a.drop]
    dropped = 0
    kept = []
    for page in pages:
        lines = page.split('\n')
        keep = [ln for ln in lines if not any(d.search(ln) for d in drops)]
        dropped += len(lines) - len(keep)
        kept.append(keep)

    repeated = collections.Counter(s for lines in kept for s in {ln.strip() for ln in lines if WEB.search(ln)})
    print('repeated lines with a web address:', [(n, s) for s, n in repeated.most_common() if n > 1])

    offset, agree, votes = booktext.find_offset(kept)
    print(f'{len(pages)} pages, header and footer numbers vote {votes.most_common(3)}')
    if a.offset is None:
        if offset is None:
            sys.exit('no page carries a header or footer number, so pass --offset')
        print(f'offset {offset} agrees with {agree} pages')
    else:
        offset = a.offset
    print(f'dropped {dropped} lines')

    blocks = [booktext.block(i + 1, offset, '\n'.join(lines)) for i, lines in enumerate(kept)]
    booktext.write_book(run, blocks, a.part)


if __name__ == '__main__':
    main()
