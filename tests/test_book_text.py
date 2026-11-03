#!/usr/bin/env python3
"""Tests for skills/book-text/scripts on synthetic inputs.

    uv run -q --with pillow python tests/test_book_text.py

Every fixture is made here: a PDF written byte by byte, page images drawn with Pillow, and hand-written OCR rows.
None holds book text. The text-layer test needs pdftotext and the image tests need Pillow, and each is skipped
when its tool is missing, except under CI, where a missing tool fails. The OCR test runs only on macOS with swiftc,
because Apple Vision does the OCR.
"""
import contextlib, io, os, pathlib, shutil, subprocess, sys, tempfile

HERE = pathlib.Path(__file__).resolve().parent
SCRIPTS = HERE.parent / 'skills' / 'book-text' / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import booktext, ctx, stitch, text_layer  # noqa: E402

failures = 0


def check(name, cond):
    global failures
    print(('ok   ' if cond else 'FAIL ') + name)
    failures += not cond


def skip(name, why):
    global failures
    if os.environ.get('CI'):
        print(f'FAIL {name}: {why}, and CI must run it')
        failures += 1
    else:
        print(f'skip {name}: {why}')


def run(main, argv):
    """Run a script's main() and return (exit code, stdout)."""
    out = io.StringIO()
    code = 0
    with contextlib.redirect_stdout(out):
        try:
            main(argv)
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else 1
    return code, out.getvalue()


# --- the offset finder ---------------------------------------------------------------------------------------------

# PDF pages 1-3 are front matter. Printed page N sits on PDF page N + 3, its number in the header on odd pages and in
# the footer on even ones. Page 7 carries a stray number in its body, and page 8 a chapter number in its header.
pages = [['Title'], ['Copyright 2001'], ['Contents']]
for printed in range(1, 9):
    body = ['Some prose.', 'More prose.', 'Middle.', '17', 'And more.', 'Still more.', 'The end of the page.']
    pages.append([str(printed)] + body if printed % 2 else body + [str(printed)])
pages[6 + 3 - 1][3] = '412'
pages[8 + 3 - 1] = ['Chapter', '9'] + pages[8 + 3 - 1]
offset, agree, votes = booktext.find_offset(pages)
check('the offset is the most common header and footer vote', offset == 3)
check('every numbered page agrees with it', agree == 8)
check('a number deep in the body casts no vote, and a chapter number in a header casts one', set(votes) == {3, 2})
check('a page with no number gives no offset', booktext.find_offset([['a'], ['b']])[0] is None)
check('a page before printed page 1 is front matter', booktext.label(3, 3) == 'front 3' and booktext.label(4, 3) == 'p. 1')
check('a block header carries both page numbers', booktext.block(40, 37, 'x') == '===== pdf 40 | p. 3 =====\nx\n')
check('a part is NAME:FIRST-LAST', booktext.parse_part('1-intro:1-50') == ('1-intro', 1, 50))
for bad in ('intro', 'intro:50-1', 'a b:1-2'):
    try:
        booktext.parse_part(bad)
        check(f'part {bad!r} is refused', False)
    except ValueError:
        check(f'part {bad!r} is refused', True)


# --- the text-layer route ------------------------------------------------------------------------------------------

check('split_pages drops only the empty piece after the final form feed',
      text_layer.split_pages('a\fb\f') == ['a', 'b'] and text_layer.split_pages('a\f\f') == ['a', ''])


def write_pdf(path, pages):
    """Write a PDF with one Helvetica text line per entry in each page's list, top to bottom."""
    objs = [None, '<< /Type /Catalog /Pages 2 0 R >>', None, '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>']
    kids = []
    for lines in pages:
        esc = [ln.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)') for ln in lines]
        stream = 'BT /F1 12 Tf 14 TL 72 720 Td ' + ' '.join(f'({ln}) Tj T*' for ln in esc) + ' ET'
        objs.append(f'<< /Length {len(stream)} >>\nstream\n{stream}\nendstream')
        objs.append(f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {len(objs) - 1} 0 R '
                    '/Resources << /Font << /F1 3 0 R >> >> >>')
        kids.append(f'{len(objs) - 1} 0 R')
    objs[2] = f'<< /Type /Pages /Kids [{" ".join(kids)}] /Count {len(kids)} >>'
    out, offsets = b'%PDF-1.4\n', []
    for n, body in enumerate(objs[1:], 1):
        offsets.append(len(out))
        out += f'{n} 0 obj\n{body}\nendobj\n'.encode('latin-1')
    xref = len(out)
    out += f'xref\n0 {len(objs)}\n0000000000 65535 f \n'.encode()
    out += b''.join(f'{o:010d} 00000 n \n'.encode() for o in offsets)
    out += f'trailer\n<< /Size {len(objs)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode()
    pathlib.Path(path).write_bytes(out)


MARK = 'Shared from www.example.com'
with tempfile.TemporaryDirectory() as tmp:
    tmp = pathlib.Path(tmp)
    if not shutil.which('pdftotext'):
        skip('text-layer route', 'pdftotext is not installed')
    else:
        book = [['A Made-Up Book'], ['Contents']]
        for printed in range(1, 6):
            book.append([str(printed), f'Chapter text on printed page {printed}.', 'A plain closing line.'])
        book[3].append(MARK)
        book[5].append(MARK)
        write_pdf(tmp / 'book.pdf', book)
        code, out = run(text_layer.main, [str(tmp / 'book.pdf'), str(tmp / 'run'), '--drop', '^Shared from ',
                                          '--part', 'first:1-2', '--part', 'rest:3-5'])
        check('text_layer finishes', code == 0)
        check('text_layer finds the offset from the header numbers', 'offset 2 agrees with 5 pages' in out)
        check('text_layer reports the lines it dropped', 'dropped 2 lines' in out)
        code, out = run(text_layer.main, [str(tmp / 'book.pdf'), str(tmp / 'look')])
        check('text_layer names a watermark that carries a web address', f"(2, '{MARK}')" in out)
        text = (tmp / 'run' / 'book_pages.txt').read_text(encoding='utf-8')
        check('every PDF page gets one block', text.count('===== pdf ') == 7)
        check('front matter is labelled front', '===== pdf 2 | front 2 =====\nContents' in text)
        check('a page is labelled with its printed number', '===== pdf 5 | p. 3 =====\n3\n' in text)
        check('the watermark is gone', MARK not in text)
        got = booktext.read_book(tmp / 'run' / 'book_pages.txt')
        check('read_book keys pages by printed number', sorted(got) == [1, 2, 3, 4, 5])
        check('read_book keeps the page text', 'printed page 4.' in got[4] and 'printed page 5' not in got[4])
        first = (tmp / 'run' / 'parts' / 'first.txt').read_text(encoding='utf-8')
        check('a part holds exactly its printed range', first.count('=====\n') == 2 and '| p. 3 ' not in first)
        code, out = run(text_layer.main, [str(tmp / 'book.pdf'), str(tmp / 'run2'), '--offset', '1'])
        check('--offset overrides the vote', '===== pdf 2 | p. 1 =====' in (tmp / 'run2' / 'book_pages.txt').read_text())

        write_pdf(tmp / 'bare.pdf', [['no numbers'], ['anywhere here']])
        code, _ = run(text_layer.main, [str(tmp / 'bare.pdf'), str(tmp / 'run3')])
        check('text_layer stops when no page carries a number', code not in (0, None))


# --- the citation checker ------------------------------------------------------------------------------------------

with tempfile.TemporaryDirectory() as tmp:
    bp = pathlib.Path(tmp) / 'book_pages.txt'
    bp.write_text('\n'.join([booktext.block(1, 1, 'Front words.'),
                             booktext.block(2, 1, 'The first page talks about\ncoupling and cohe-\nsion at length.'),
                             booktext.block(3, 1, 'The second page is about schedules.\n[margin] A side note.'),
                             booktext.block(4, 1, 'The third page.')]), encoding='utf-8')
    code, out = run(ctx.main, [str(bp), '1:Coupling and cohesion', '2:a side note'])
    check('ctx finds a quote across a line break and a split word', 'NOT FOUND' not in out and code == 0)
    code, out = run(ctx.main, [str(bp), '3:coupling'])
    check('ctx says NOT FOUND for a quote on another page, and exits 1', 'NOT FOUND' in out and code == 1)
    code, out = run(ctx.main, [str(bp), '--check', '1:cohesion at length', '3:about schedules', '1:no such words'])
    check('--check says OK on the cited page', out.startswith('OK   1 [1]'))
    check('--check says NEAR one page off', 'NEAR 3 [2]' in out)
    check('--check says MISS and exits 1 otherwise', 'MISS 1 []' in out and code == 1)
    check('front matter is not a citable page', 'Front' not in ''.join(booktext.read_book(bp).values()))


# --- the scan route: stitch ----------------------------------------------------------------------------------------

def tsv(path, rows):
    path.write_text(''.join(f'{y}\t{x}\t{t}\n' for y, x, t in rows), encoding='utf-8')


with tempfile.TemporaryDirectory() as tmp:
    tmp = pathlib.Path(tmp)
    for d in ('pages', 'text', 'text2'):
        (tmp / d).mkdir()
    for i in range(6):
        (tmp / 'pages' / f'p-{i:03d}.png').write_bytes(b'')  # stitch reads only the names
    # Printed page N is on PDF page N + 2, so image p-00(N+1). Image p-004 is blank.
    for i in (2, 3, 5):
        tsv(tmp / 'text' / f'p-{i:03d}.ocr.tsv', [(0.05, 0.5, str(i - 1)), (0.1, 0.3, 'body')])
    tsv(tmp / 'text2' / 'p-000_body.ocr.tsv', [(0.4, 0.4, 'A Title')])
    tsv(tmp / 'text2' / 'p-002_body.ocr.tsv', [(0.1, 0.3, 'A line that ends in a broken compu-'),
                                                 (0.2, 0.3, 'tation and a kept dash -'), (0.3, 0.3, 'Next line')])
    tsv(tmp / 'text2' / 'p-002_margin.ocr.tsv', [(0.1, 0.1, 'See also'), (0.12, 0.1, 'Chapter 9.')])
    tsv(tmp / 'text2' / 'p-003_body.ocr.tsv', [(0.1, 0.3, 'Page two text.')])
    tsv(tmp / 'text2' / 'p-005_body.ocr.tsv', [(0.1, 0.3, 'Page four text.')])
    args = [str(tmp / 'pages'), str(tmp / 'text2'), str(tmp / 'run'), '--first-pass', str(tmp / 'text'),
            '--part', 'one:1-2', '--part', 'two:3-4']
    code, out = run(stitch.main, args)
    check('stitch finds the offset from the first pass', 'offset 2 agrees with 3 of 6 pages' in out)
    check('stitch lists the blank pages by PDF page number', 'PDF pages [2, 5]' in out)
    text = (tmp / 'run' / 'book_pages.txt').read_text(encoding='utf-8')
    check('stitch labels front matter', text.startswith('===== pdf 1 | front 1 =====\nA Title\n'))
    check('stitch joins a word split at a line end', 'broken computation and' in text)
    check('stitch keeps a dash before a capital', 'kept dash -\nNext line' in text)
    check('stitch puts the margin after the body on one line', 'Next line\n[margin] See also Chapter 9.\n' in text)
    check('a blank page still gets its block', '===== pdf 5 | p. 3 =====\n\n' in text)
    two = (tmp / 'run' / 'parts' / 'two.txt').read_text(encoding='utf-8')
    check('a part holds its printed range', '| p. 3 =' in two and '| p. 4 =' in two and '| p. 2 =' not in two)
    code, _ = run(stitch.main, [str(tmp / 'pages'), str(tmp / 'text2'), str(tmp / 'run2')])
    check('stitch stops when it has neither an offset nor a first pass', code not in (0, None))
    (tmp / 'pages' / 'p-003.png').unlink()
    code, _ = run(stitch.main, args[:3] + ['--offset', '2'])
    check('stitch stops when a page image is missing', code not in (0, None))


# --- the scan route: prep and OCR ----------------------------------------------------------------------------------

try:
    from PIL import Image, ImageDraw, ImageFont
    import prep
except ImportError:
    Image = None
    skip('image tests', 'Pillow is not installed')

if Image:
    W, H, GRAY, INK, SOFT = 800, 600, 200, 0, 100
    page = Image.new('L', (W, H), 255)
    d = ImageDraw.Draw(page)
    d.rectangle((300, 100, 760, 300), fill=GRAY)       # a shaded box in the body column
    d.rectangle((320, 150, 700, 170), fill=INK)        # a text line inside it
    d.rectangle((320, 400, 700, 420), fill=SOFT)       # a lighter line below it
    d.rectangle((40, 150, 200, 170), fill=INK)         # a margin note left of the body column
    white = prep.whiten(page, 185)
    check('whiten turns the gray box white', white.getpixel((750, 110)) == 255)
    check('whiten keeps black text black', white.getpixel((400, 160)) == 0)
    check('whiten stretches a darker gray', white.getpixel((400, 410)) == int(SOFT * 255 / 185))
    check('the threshold is a setting', prep.whiten(page, 201).getpixel((750, 110)) < 255)

    first_pass = '0.25\t0.40\tshort\n0.30\t0.38\t' + 'x' * 50 + '\n0.40\t0.40\t' + 'y' * 50 + '\n0.5\t0.42\t' + 'z' * 46
    check('the body column starts at the median x of long lines', prep.body_left(first_pass, 45) == 0.40)
    check('no long line gives no body column', prep.body_left('0.1\t0.4\tshort', 45) is None)

    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        for d_ in ('pages', 'text'):
            (tmp / d_).mkdir()
        page.save(tmp / 'pages' / 'p-000.png')
        page.save(tmp / 'pages' / 'p-001.png')
        (tmp / 'text' / 'p-000.ocr.tsv').write_text(first_pass)  # p-001 has no first pass
        code, out = run(prep.main, [str(tmp / 'pages'), str(tmp / 'text'), str(tmp / 'clean')])
        check('prep writes a body and a margin crop, and only a body crop with no first pass',
              sorted(p.name for p in (tmp / 'clean').iterdir()) == ['p-000_body.png', 'p-000_margin.png', 'p-001_body.png'])
        body = Image.open(tmp / 'clean' / 'p-000_body.png')
        margin = Image.open(tmp / 'clean' / 'p-000_margin.png')
        cut = int(W * (0.40 - 0.03))
        check('the body crop starts just left of the body column, padded and doubled',
              body.size == ((W - cut + 128) * 2, (H + 128) * 2))
        check('the margin crop is the rest, padded and doubled', margin.size == ((cut + 128) * 2, (H + 128) * 2))
        check('the margin note lands in the margin crop', margin.getpixel(((64 + 100) * 2, (64 + 160) * 2)) == 0)
        check('the body crop has no margin note', body.crop((0, 0, 64 * 2 + 10, body.height)).getextrema() == (255, 255))
        check('the gray box is white in the body crop', body.getpixel(((64 + 740 - cut) * 2, (64 + 110) * 2)) == 255)
        run(prep.main, [str(tmp / 'pages'), str(tmp / 'text'), str(tmp / 'fixed'), '--split', '0.5',
                        '--border', '10', '--scale', '1'])
        check('--split, --border and --scale override the defaults',
              Image.open(tmp / 'fixed' / 'p-001_body.png').size == (W // 2 + 20, H + 20))

    font = next((f for f in ('/System/Library/Fonts/Helvetica.ttc', '/System/Library/Fonts/Supplemental/Arial.ttf')
                 if os.path.exists(f)), None)
    if sys.platform != 'darwin' or not shutil.which('swiftc') or not font:
        print('skip Vision OCR test: it needs macOS, swiftc and a system font')
    else:
        import ocr_pages
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            for d_ in ('pages', 'text'):
                (tmp / d_).mkdir()
            big, small = ImageFont.truetype(font, 26), ImageFont.truetype(font, 20)
            im = Image.new('L', (1100, 1400), 255)
            d = ImageDraw.Draw(im)
            d.rectangle((330, 180, 1060, 420), fill=210)
            lines = ['Shaded boxes hold the case studies in this book', 'and their words must survive the second pass',
                     'even when the gray behind them is quite dark', 'so the threshold whitens the shading first']
            for k, s in enumerate(lines):
                d.text((350, 200 + 50 * k), s, font=big, fill=0)
            for k, s in enumerate(['Body text continues below the box with a', 'second line of ordinary prose here']):
                d.text((350, 520 + 50 * k), s, font=big, fill=0)
            d.text((40, 520), 'CROSS-REF', font=small, fill=0)
            d.text((40, 550), 'See chapter nine.', font=small, fill=0)
            im.save(tmp / 'pages' / 'p-000.png')
            code, _ = run(ocr_pages.main, [str(tmp / 'pages'), str(tmp / 'text'), '--jobs', '2'])
            check('ocr_pages OCRs a whole page', code == 0 and (tmp / 'text' / 'p-000.ocr.tsv').exists())
            run(prep.main, [str(tmp / 'pages'), str(tmp / 'text'), str(tmp / 'clean')])
            code, _ = run(ocr_pages.main, [str(tmp / 'clean'), str(tmp / 'text2'), '--glob', '*.png',
                                           '--ocr', str(tmp / 'bin' / 'ocr')])
            run(stitch.main, [str(tmp / 'pages'), str(tmp / 'text2'), str(tmp / 'run'), '--offset', '0'])
            text = (tmp / 'run' / 'book_pages.txt').read_text(encoding='utf-8')
            body_text, _, margin_text = text.partition('[margin]')
            check('the shaded box text survives the second pass', 'gray behind them is quite dark' in body_text)
            check('the margin note lands on the margin line', 'See chapter nine.' in margin_text)
            check('no margin word leaks into the body', 'CROSS-REF' not in body_text)

print('all passed' if not failures else f'{failures} failed')
sys.exit(1 if failures else 0)
