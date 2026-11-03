#!/usr/bin/env python3
"""Prepare scanned page images for a second OCR pass: whiten gray shading, then split the body column from the
margin column. Needs Pillow, so run it as `uv run -q --with 'pillow>=10' python prep.py ...`.

    prep.py PAGE_DIR FIRST_PASS_DIR OUT_DIR [--threshold 185] [--split FRACTION] [--glob 'p-*.png']

A whole-page OCR pass drops words printed on gray boxes, and it drops words at the ends of lines when the body and
a margin column share baselines, because it reads each baseline across both columns. This script fixes both.

1. Every pixel at or above --threshold turns white, and darker pixels stretch to fill the range, so gray shading
   vanishes while text stays dark.
2. The page splits into a body crop and a margin crop, --gap of the page width left of the body column. The body
   column's left edge is the --percentile of the x of the first pass's long lines, read from
   FIRST_PASS_DIR/<stem>.ocr.tsv. A low percentile holds the edge when a list or a quotation indents many lines,
   and a gap narrower than the gutter keeps the cut out of the margin notes. --split skips that and cuts every page
   at one fixed fraction of its width.
3. Each crop gets a --border of white pixels and is scaled up --scale times.

Writes OUT_DIR/<stem>_body.png and, where the margin is wider than --min-margin pixels, OUT_DIR/<stem>_margin.png.
A margin crop left from an earlier run is removed when this run writes none for that page. Prints the pages that
had no first-pass .tsv and the pages that had no long line, since both keep one whole-page body crop. OUT_DIR must
sit outside every git repository.
"""
import argparse, pathlib, sys
from PIL import Image, ImageOps

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import booktext  # noqa: E402


def whiten(im, threshold):
    return im.convert('L').point(lambda v: 255 if v >= threshold else int(v * 255 / threshold))


def body_left(tsv_text, min_chars, percentile=10):
    """The left edge of the body column: the given percentile, by lower rank, of the x of the long lines in a
    first-pass OCR .tsv. None when the page has no long line."""
    xs = []
    for row in tsv_text.splitlines():
        p = row.split('\t', 2)
        if len(p) == 3 and len(p[2]) > min_chars:
            xs.append(float(p[1]))
    xs.sort()
    return xs[int(percentile / 100 * (len(xs) - 1))] if xs else None


def crops(im, cut, border, scale, min_margin):
    w, h = im.size
    boxes = [('body', (cut, 0, w, h))] + ([('margin', (0, 0, cut, h))] if cut > min_margin else [])
    for name, box in boxes:
        c = ImageOps.expand(im.crop(box), border=border, fill=255)
        yield name, c.resize((c.width * scale, c.height * scale), Image.LANCZOS)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('page_dir')
    ap.add_argument('first_pass_dir')
    ap.add_argument('out_dir')
    ap.add_argument('--glob', default='p-*.png')
    ap.add_argument('--threshold', type=int, default=185, help='gray level at and above which a pixel turns white')
    ap.add_argument('--split', type=float, help='cut every page at this fraction of its width instead')
    ap.add_argument('--gap', type=float, default=0.02, help='how far left of the body column to cut')
    ap.add_argument('--percentile', type=float, default=10, help='which long line marks the body column edge')
    ap.add_argument('--min-chars', type=int, default=45, help='a first-pass line longer than this is body text')
    ap.add_argument('--min-margin', type=int, default=40, help='narrowest margin crop worth writing, in pixels')
    ap.add_argument('--border', type=int, default=64)
    ap.add_argument('--scale', type=int, default=2)
    a = ap.parse_args(argv)

    out = booktext.run_dir(a.out_dir)
    written, no_tsv, no_long = 0, [], []
    for page in sorted(pathlib.Path(a.page_dir).glob(a.glob)):
        split = a.split
        if split is None:
            tsv = pathlib.Path(a.first_pass_dir) / f'{page.stem}.ocr.tsv'
            left = body_left(tsv.read_text(encoding='utf-8'), a.min_chars, a.percentile) if tsv.exists() else None
            if left is None:
                (no_long if tsv.exists() else no_tsv).append(page.stem)
            split = max(0.0, left - a.gap) if left is not None else 0.0
        im = whiten(Image.open(page), a.threshold)
        names = set()
        for name, c in crops(im, int(im.width * split), a.border, a.scale, a.min_margin):
            c.save(out / f'{page.stem}_{name}.png')
            names.add(name)
            written += 1
        if 'margin' not in names:
            (out / f'{page.stem}_margin.png').unlink(missing_ok=True)
    print(f'prepared {written} crops in {out}')
    print(f'{len(no_tsv)} pages had no first-pass .tsv: {no_tsv}')
    print(f'{len(no_long)} pages had no line over {a.min_chars} characters: {no_long}')


if __name__ == '__main__':
    main()
