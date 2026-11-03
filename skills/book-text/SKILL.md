---
name: book-text
description: Turn a book PDF the user owns into page-numbered plain text and reading parts, kept outside every repository. Covers a PDF with a text layer, read with pdftotext, and a scanned PDF of page images, read with Apple Vision OCR after whitening gray shading and splitting the margin column from the body. Also checks a quote against its cited printed page. Use when the user supplies a book as a PDF, when the Kindle Cloud Reader will not open a book, or when citations need checking against a book's printed page numbers.
---

# Book PDF to page-numbered text

A reading or citation pipeline needs a book's text with its printed page numbers attached, so that a quote can be checked against the page it cites. The `kindle-highlights` skill gets text from the Kindle Cloud Reader, but on 2026-11-03 the Cloud Reader would not open two books, *Code Complete* and *Rapid Development*, both Microsoft Press editions. The owner supplied PDFs of their own copies instead, and this skill holds the two routes worked out on those PDFs.

Every route ends in the same files in one run directory:

1. `book_pages.txt`, the whole book as page blocks.
2. `parts/NAME.txt`, one file per reading part, each a printed page range of the same blocks.

A page block is one PDF page of text under a header line:

```text
===== pdf 101 | p. 64 =====
```

The first number is the 1-based PDF page and the second is the printed page. The difference between them is the book's **offset**, 37 in this example, and it is one number for the whole book. A page before printed page 1 gets `front N` instead of `p. M`, where N is again the PDF page number. A scanned page's margin column follows its body on one line that starts `[margin] `.

**Keep the run directory outside every repository.** It holds a copyrighted book's full text. Use `~/Documents/Claude/kindle/<book-slug>/`, the folder `kindle-highlights` already uses, so a book's highlights and its text sit together. No book page, crop or OCR output may enter a tracked file, a test fixture or a pull request.

## Prerequisites

1. **poppler**, for `pdfinfo`, `pdffonts`, `pdftotext` and `pdfimages`. Install it with `brew install poppler`.
2. **python3**, which runs every script here.
3. **Pillow**, for the scan route's `prep.py` only. It need not be installed globally, because `uv run -q --with pillow python <script>` fetches it for one run.
4. **macOS with Xcode Command Line Tools**, for the scan route's OCR only. `ocr_pages.py` compiles Apple Vision's text recognizer with `swiftc` on first use.

The scripts sit in `scripts/` next to this file. The commands below write `$SKILL` for that folder and `$RUN` for the run directory.

## Step 1: pick the route

A PDF either carries a text layer, which is the book's characters stored as text, or only pictures of its pages. `pdffonts` tells them apart, because a text layer needs fonts:

```bash
pdfinfo BOOK.pdf     # page count, and the program that made the file
pdffonts BOOK.pdf    # a list of fonts means a text layer; a header with no rows means images only
```

*Code Complete* listed its fonts and was made by FrameMaker, so it took route A. *Rapid Development* listed no fonts and was made by Chrome's print to PDF, so it took route B.

## Route A: a PDF with a text layer

```bash
python3 $SKILL/text_layer.py BOOK.pdf $RUN --part 1-intro:1-50 --part 2-design:51-120
```

The script works in four steps.

1. It runs `pdftotext -enc UTF-8` into `$RUN/book.txt`. pdftotext writes a form feed after every page, so splitting at form feeds gives one piece of text per PDF page.
2. It finds the offset by counting the page numbers printed in headers and footers. A line among the first or last three lines of a page that holds only a number votes for PDF page minus that number. The most common vote wins, and the script prints how many pages agree. `--offset N` overrides the vote.
3. It removes every line matching a `--drop` regular expression. A download site's watermark is the usual target, so the script prints every line on two or more pages that carries a web address. Rerun with `--drop` naming it.
4. It writes `book_pages.txt` and one part per `--part NAME:FIRST-LAST`, where FIRST and LAST are printed pages.

**Measured on *Code Complete* (952 PDF pages).** The vote gave offset 37, with 814 pages agreeing. Stray numbers cast 3 votes for two other offsets. A watermark line sat on 7 pages, and the web-address report named it first. The script's output matched the hand run on every printed page except the blank lines left where the watermark was dropped, on five pages.

**Limits of route A.**

- **pdftotext reads a margin column inline.** *Code Complete*'s margin notes, such as cross-references, come out as lines between body paragraphs rather than on a `[margin]` line.
- **The offset is one number.** A book with unnumbered plates inserted mid-book changes its offset partway. The vote then shows two large counts rather than one, and the book needs a run per stretch.
- **A watermark without a web address goes unreported.** Read a few pages of `book.txt` before trusting the report.

## Route B: a scanned PDF of page images

Route B runs OCR twice. The first pass reads whole pages, and the second reads cleaned crops of each page. The first pass alone lost text on *Rapid Development* in two ways.

1. **Words on gray boxes.** The book prints its case studies on gray shading, and Vision dropped words there.
2. **Words at line ends.** The page has a margin column of notes left of the body. A margin note and a body line on the same baseline read as one line across both columns, and Vision dropped words where they met.

The first pass is still needed, because it locates the body column that the second pass splits at.

### B1. Extract one image per page

```bash
pdfimages -list BOOK.pdf | head    # one image per page is what the rest assumes
mkdir -p $RUN/pages && pdfimages -png BOOK.pdf $RUN/pages/p
```

pdfimages names the images `p-000.png`, `p-001.png` and so on, so `p-000.png` is PDF page 1. Check that the image count equals the page count from `pdfinfo`, because a page with two images shifts every later page by one. `stitch.py` stops when a number is missing, but it cannot see an extra image. *Rapid Development* gave 672 images for 672 pages, each about 1104 by 1387 pixels at 210 pixels per inch.

### B2. First pass on whole pages

```bash
python3 $SKILL/ocr_pages.py $RUN/pages $RUN/text --jobs 8
```

`ocr_pages.py` runs Vision on each image, several at a time, and writes `<stem>.ocr.tsv`, one recognized line per row as `y`, `x` and the text, where `y` and `x` are the line's top and left edges as fractions of the page. It compiles the Vision program that `kindle-highlights` ships, `skills/kindle-highlights/scripts/ocr.swift`, into `$RUN/bin/ocr` on first use. The script points at that file rather than copying it, so the two skills share one recognizer. A rerun skips any image whose `.tsv` already exists, so a stopped run resumes.

### B3. Whiten the shading and split the columns

```bash
uv run -q --with pillow python $SKILL/prep.py $RUN/pages $RUN/text $RUN/clean
```

`prep.py` changes each page in three ways.

1. **Whitening.** Every pixel at or above gray level 185 turns white, and darker pixels stretch to fill the range, so the shading vanishes while the text stays dark. `--threshold` sets the level. Text printed in a gray lighter than the threshold vanishes with the shading, so lower the threshold if that happens.
2. **Splitting.** The page splits into a body crop and a margin crop, 3% of the page width left of the body column (`--gap`). The body column's left edge is the median x of the first pass's lines longer than 45 characters (`--min-chars`), since only body text runs that long. A page with no such line keeps one whole-page body crop. `--split FRACTION` cuts every page at one fixed fraction instead.
3. **Padding and scaling.** Each crop gets a 64-pixel white border and is scaled up 2 times (`--border`, `--scale`). The border keeps text off the crop's edge, where the cut runs, and the scaling enlarges small type such as the margin notes.

### B4. Second pass on the crops

```bash
python3 $SKILL/ocr_pages.py $RUN/clean $RUN/text2 --glob '*.png' --jobs 8
```

### B5. Stitch the pages and parts

```bash
python3 $SKILL/stitch.py $RUN/pages $RUN/text2 $RUN --first-pass $RUN/text --part 1-intro:1-50
```

Each page block holds the body lines in reading order, then one `[margin]` line carrying the margin column. A hyphen at a line end joins to the next line when that line starts in lowercase, which mends a word split across lines. The offset comes from the first pass's header and footer numbers, the same vote route A takes, or from `--offset N`. The script lists every page with no text by its PDF page number.

**Measured on *Rapid Development* (672 PDF pages).**

- **Offset.** The vote gave offset 22, with 615 of 672 pages agreeing by this script's count. The hand count on the day gave 616. Stray numbers cast 3 votes for two other offsets, and the remaining pages print no number at their top or foot.
- **Blank pages.** Six pages came back with no text, PDF pages 3, 12, 20, 22, 646 and 671.
- **Speed.** The whole book OCRed in a few minutes with 8 jobs at once. A later timing of 56 second-pass crops took 6.3 seconds, which puts the 1,304 crops of the second pass at about two and a half minutes.
- **Agreement with the hand run.** `prep.py`'s crops were byte-identical to the hand run's, the second pass's `.tsv` files matched, and all 650 printed pages of `book_pages.txt` matched.

**Limits of route B.**

- **Tables come out scrambled.** The recognizer returns each table cell as its own line and sorts lines top to bottom, so cells whose tops sit at slightly different heights interleave across columns, and a table's text comes out in the wrong order. Check a table against the page image before quoting it.
- **A hyphenated compound loses its hyphen** when it breaks at a line end, such as "self-" before "contained". The join cannot tell a split word from a compound.
- **The margin column must sit left of the body.** `prep.py` cuts one vertical line per page. A book with its margin on the right, or on alternating sides, needs `--split` per side or a change to `crops()`.
- **One image per page.** See B1.
- **The OCR is macOS only.** Vision is Apple's framework. `prep.py` and `stitch.py` run anywhere.

## Step 2: check citations

```bash
python3 $SKILL/ctx.py $RUN/book_pages.txt '64:the quoted words' '212:another quote'
python3 $SKILL/ctx.py $RUN/book_pages.txt --check '64:the quoted words' '212:another quote'
```

Without `--check`, `ctx.py` prints 260 characters either side of each quote on its cited page, or NOT FOUND. With `--check`, it prints one verdict per citation.

1. **OK** means the quote is on the cited page.
2. **NEAR** means it is only on the page before or after, which usually means a quote that starts at the foot of one page.
3. **MISS** means it is on neither.

Matching ignores case, line breaks and a hyphen that splits a word across lines. The script exits 1 on any MISS or NOT FOUND, so a pipeline can stop on a bad citation. A quote from a scanned book can miss on an OCR error rather than a wrong page, so read the context before calling the citation wrong.

## Tests

`tests/test_book_text.py` checks every script on inputs it makes itself: a PDF written byte by byte, page images drawn with Pillow that carry a gray box and a margin note, and hand-written OCR rows. On macOS it also runs Vision end to end on a drawn page and checks that the shaded text survives and the margin note lands on the `[margin]` line. CI runs it on Linux, where that OCR check skips.

```bash
uv run -q --with pillow python tests/test_book_text.py
```
