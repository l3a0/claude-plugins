#!/usr/bin/env python3
"""OCR every image in a folder with Apple Vision, several images at a time. macOS only.

    python3 ocr_pages.py IMAGE_DIR OUT_DIR [--glob 'p-*.png'] [--jobs 8] [--ocr BIN]

Writes OUT_DIR/<image stem>.ocr.tsv for each image, one recognized line per row as `y<TAB>x<TAB>text`. y and x are
the line's top and left edges as fractions of the page, sorted top to bottom. An image whose .tsv already exists
is skipped, so a stopped run resumes. Without --ocr, the script compiles the Vision program the kindle-highlights
skill ships, skills/kindle-highlights/scripts/ocr.swift, into OUT_DIR/../bin/ocr on first use.
"""
import argparse, concurrent.futures, pathlib, subprocess, sys

OCR_SWIFT = pathlib.Path(__file__).resolve().parents[2] / 'kindle-highlights' / 'scripts' / 'ocr.swift'


def ocr_binary(out_dir, given):
    if given:
        return pathlib.Path(given)
    binary = out_dir.parent / 'bin' / 'ocr'
    if not binary.exists():
        if not OCR_SWIFT.exists():
            sys.exit(f'{OCR_SWIFT} is missing, so pass --ocr with a compiled Vision OCR program')
        binary.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(['swiftc', '-O', str(OCR_SWIFT), '-o', str(binary)], check=True)
    return binary


def run_one(binary, image, out):
    r = subprocess.run([str(binary), str(image)], capture_output=True, text=True)
    if r.returncode:
        return f'{image.name}: {r.stderr.strip()}'
    out.write_text(r.stdout, encoding='utf-8')
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('image_dir')
    ap.add_argument('out_dir')
    ap.add_argument('--glob', default='p-*.png')
    ap.add_argument('--jobs', type=int, default=8)
    ap.add_argument('--ocr', help='a compiled OCR program that takes one image path and prints y, x, text rows')
    a = ap.parse_args(argv)

    out_dir = pathlib.Path(a.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    binary = ocr_binary(out_dir.resolve(), a.ocr)
    todo = [(img, out_dir / f'{img.stem}.ocr.tsv') for img in sorted(pathlib.Path(a.image_dir).glob(a.glob))]
    todo = [(img, out) for img, out in todo if not out.exists()]
    with concurrent.futures.ThreadPoolExecutor(a.jobs) as pool:
        errors = [e for e in pool.map(lambda t: run_one(binary, *t), todo) if e]
    print(f'OCRed {len(todo) - len(errors)} images into {out_dir}')
    for e in errors:
        print('failed', e, file=sys.stderr)
    sys.exit(1 if errors else 0)


if __name__ == '__main__':
    main()
