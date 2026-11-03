#!/usr/bin/env python3
"""OCR every image in a folder with Apple Vision, several images at a time. macOS only.

    python3 ocr_pages.py IMAGE_DIR OUT_DIR [--glob 'p-*.png'] [--jobs 8] [--ocr BIN]

Writes OUT_DIR/<image stem>.ocr.tsv for each image, one recognized line per row as `y<TAB>x<TAB>text`. y and x are
the line's top and left edges as fractions of the page, sorted top to bottom. An image whose .tsv exists and is
newer than the image is skipped, so a stopped run resumes and a remade image is read again. A .tsv appears only
once its OCR has finished, and an image whose OCR fails gets none. A .tsv whose image is no longer in IMAGE_DIR is
removed, so stitch.py cannot read OCR of a crop that prep.py stopped writing. Without --ocr, the script compiles the Vision
program the kindle-highlights skill ships, skills/kindle-highlights/scripts/ocr.swift, into OUT_DIR/../bin/ocr on
first use. OUT_DIR must sit outside every git repository.
"""
import argparse, concurrent.futures, os, pathlib, subprocess, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import booktext  # noqa: E402

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
        out.unlink(missing_ok=True)  # so an older .tsv cannot stand in for the image that failed
        return f'{image.name}: {r.stderr.strip()}'
    part = out.with_name(out.name + '.part')
    part.write_text(r.stdout, encoding='utf-8')
    os.replace(part, out)
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('image_dir')
    ap.add_argument('out_dir')
    ap.add_argument('--glob', default='p-*.png')
    ap.add_argument('--jobs', type=int, default=8)
    ap.add_argument('--ocr', help='a compiled OCR program that takes one image path and prints y, x, text rows')
    a = ap.parse_args(argv)

    out_dir = booktext.run_dir(a.out_dir)
    binary = ocr_binary(out_dir, a.ocr)
    images = sorted(pathlib.Path(a.image_dir).glob(a.glob))
    stems = {img.stem for img in pathlib.Path(a.image_dir).iterdir()}
    orphans = [t for t in out_dir.glob('*.ocr.tsv') if t.name[:-len('.ocr.tsv')] not in stems]
    for t in orphans:
        t.unlink()  # its image is gone, such as a margin crop prep.py no longer writes
    if orphans:
        print(f'removed {len(orphans)} .tsv files whose image is gone')
    todo = [(img, out_dir / f'{img.stem}.ocr.tsv') for img in images]
    todo = [(img, out) for img, out in todo if not out.exists() or out.stat().st_mtime < img.stat().st_mtime]
    with concurrent.futures.ThreadPoolExecutor(a.jobs) as pool:
        errors = [e for e in pool.map(lambda t: run_one(binary, *t), todo) if e]
    print(f'OCRed {len(todo) - len(errors)} images into {out_dir}')
    for e in errors:
        print('failed', e, file=sys.stderr)
    sys.exit(1 if errors else 0)


if __name__ == '__main__':
    main()
