#!/usr/bin/env python3
"""Assemble a scanned book's column-split OCR into page-numbered text and reading parts.

    python3 stitch.py PAGE_DIR OCR_DIR RUN_DIR [--offset N] [--first-pass DIR] [--part NAME:FIRST-LAST ...]

PAGE_DIR holds one image per PDF page, named the way `pdfimages -png` names them: p-000.png is PDF page 1.
OCR_DIR holds <stem>_body.ocr.tsv and <stem>_margin.ocr.tsv for each page. Each page block holds the body lines in
reading order, with a hyphen at a line end joined to a lowercase continuation, then one `[margin]` line carrying
the margin column. Without --offset, the offset comes from the page numbers in the first-pass OCR of whole pages,
which --first-pass names. Writes RUN_DIR/book_pages.txt and RUN_DIR/parts/NAME.txt, and lists the blank pages.
"""
import argparse, pathlib, re, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import booktext  # noqa: E402


def tsv_lines(path):
    if not path.exists():
        return []
    return [row.split('\t', 2)[2] for row in path.read_text(encoding='utf-8').splitlines() if row.count('\t') >= 2]


def page_text(body, margin):
    text = re.sub(r'-\n(?=[a-z])', '', '\n'.join(body))
    if margin:
        text += '\n[margin] ' + ' '.join(margin)
    return text


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('page_dir')
    ap.add_argument('ocr_dir')
    ap.add_argument('run_dir')
    ap.add_argument('--glob', default='p-*.png')
    ap.add_argument('--offset', type=int, help='PDF page number minus printed page number')
    ap.add_argument('--first-pass', help='folder of whole-page OCR, used to find the offset')
    ap.add_argument('--part', action='append', default=[], type=booktext.parse_part, metavar='NAME:FIRST-LAST')
    a = ap.parse_args(argv)

    stems = [p.stem for p in sorted(pathlib.Path(a.page_dir).glob(a.glob))]
    numbers = [int(re.search(r'(\d+)$', s).group(1)) + 1 for s in stems]
    if numbers != list(range(1, len(stems) + 1)):
        sys.exit(f'{a.page_dir} must hold one image per PDF page numbered from 0 with no gaps')

    offset = a.offset
    if offset is None:
        if not a.first_pass:
            sys.exit('pass --offset, or --first-pass so the offset can be found from page numbers')
        fp = pathlib.Path(a.first_pass)
        offset, agree, votes = booktext.find_offset([tsv_lines(fp / f'{s}.ocr.tsv') for s in stems])
        if offset is None:
            sys.exit('no page carries a header or footer number, so pass --offset')
        print(f'offset {offset} agrees with {agree} of {len(stems)} pages, votes {votes.most_common(3)}')

    ocr = pathlib.Path(a.ocr_dir)
    blocks, blank = [], []
    for n, s in zip(numbers, stems):
        body, margin = tsv_lines(ocr / f'{s}_body.ocr.tsv'), tsv_lines(ocr / f'{s}_margin.ocr.tsv')
        if not body and not margin:
            blank.append(n)
        blocks.append(booktext.block(n, offset, page_text(body, margin)))
    print(f'{len(blocks)} pages, {len(blank)} with no text: PDF pages {blank}')
    booktext.write_book(a.run_dir, blocks, a.part)


if __name__ == '__main__':
    main()
