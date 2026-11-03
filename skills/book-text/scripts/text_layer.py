#!/usr/bin/env python3
"""Turn a PDF that has a text layer into page-numbered text and reading parts.

    python3 text_layer.py BOOK.pdf RUN_DIR [--offset N] [--drop REGEX ...] [--part NAME:FIRST-LAST ...]

Runs `pdftotext -enc UTF-8` into RUN_DIR/book.txt and splits it into pages at the form feeds pdftotext writes
after every page. Without --offset, the offset comes from the page numbers in each page's first and last lines.
Each --drop removes every line that matches it, such as a watermark repeated across pages, and the script prints
each distinct line it dropped with the pages it came from. Writes RUN_DIR/book_pages.txt and RUN_DIR/parts/NAME.txt.
It also prints every line that is left on two or more pages and carries a web address, because a download site's
watermark usually names the site. RUN_DIR must sit outside every git repository.
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

    run = booktext.run_dir(a.run_dir)
    pdf = pathlib.Path(a.pdf).resolve()  # an absolute path cannot be read as a pdftotext option
    subprocess.run(['pdftotext', '-enc', 'UTF-8', str(pdf), str(run / 'book.txt')], check=True)
    pages = split_pages((run / 'book.txt').read_text(encoding='utf-8'))

    drops = [re.compile(d) for d in a.drop]
    dropped = collections.defaultdict(list)
    kept = []
    for n, page in enumerate(pages, 1):
        keep = []
        for ln in page.split('\n'):
            if any(d.search(ln) for d in drops):
                dropped[ln.strip()].append(n)
            else:
                keep.append(ln)
        kept.append(keep)
    for line, on in sorted(dropped.items(), key=lambda kv: -len(kv[1])):
        print(f'dropped {line!r} from {len(on)} lines on PDF pages {sorted(set(on))}')

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
    print(f'dropped {sum(map(len, dropped.values()))} lines')

    blocks = [booktext.block(i + 1, offset, '\n'.join(lines)) for i, lines in enumerate(kept)]
    booktext.write_book(run, blocks, a.part)


if __name__ == '__main__':
    main()
