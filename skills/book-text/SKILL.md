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

**Keep the run directory outside every repository.** It holds a copyrighted book's full text. Every script refuses an output folder inside a git repository, since one `git add -A` there would stage the book. The 2026-11-03 runs used `~/Documents/Claude/kindle/<book-slug>/`, beside the book's Kindle highlights. No book page, crop or OCR output may enter a tracked file, a test fixture or a pull request.

## Prerequisites

1. **poppler**, for `pdfinfo`, `pdffonts`, `pdftotext` and `pdfimages`. Install it with `brew install poppler`.
2. **python3**, which runs every script here.
3. **Pillow**, for the scan route's `prep.py` only. Either install it for python3, or use **uv**, whose `uv run -q --with 'pillow>=10' python <script>` fetches it for one run.
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
3. It removes every line matching a `--drop` regular expression. A download site's watermark is the usual target, so the script prints every line on two or more pages that carries a web address. Rerun with `--drop` naming it. The script prints each distinct line it dropped and the PDF pages it came from, so a pattern that also catches the book's own lines shows at once.
4. It writes `book_pages.txt` and one part per `--part NAME:FIRST-LAST`, where FIRST and LAST are printed pages. Part files from an earlier run are removed first, and a part whose range runs past the book says how many pages it fell short.

### Measured on *Code Complete*

These figures come from one run on 2026-11-03, on the owner's 952-page PDF, which stays outside the repository.

- **Offset.** The vote gave offset 37, with 814 pages agreeing. Stray numbers cast 3 votes for two other offsets.
- **Watermark.** A watermark line sat on 7 pages, and the web-address report named it first.
- **Agreement with the hand run.** The non-blank lines of every page matched the hand run. Blank lines differ where the watermark was dropped, and the hand run's empty block after the last page is gone.

### Limits of route A

- **pdftotext reads a margin column inline.** *Code Complete*'s margin notes, such as cross-references, come out as lines between body paragraphs rather than on a `[margin]` line.
- **The offset is one number.** A book with unnumbered plates inserted mid-book changes its offset partway. The vote then shows two large counts rather than one. The scripts take one offset for the whole book, so such a book needs them extended first.
- **A watermark without a web address goes unreported.** Read a few pages of `book.txt` before trusting the report.

## Route B: a scanned PDF of page images

Route B runs OCR twice. The first pass reads whole pages, and the second reads cleaned crops of each page. The first pass alone lost text on *Rapid Development* in two ways.

1. **Words on gray boxes.** The book prints its case studies on gray shading, and Vision dropped words there.
2. **Words at line ends.** The page has a margin column of notes left of the body. A margin note and a body line on the same baseline read as one line across both columns, and Vision dropped words where they met.

The first pass is still needed, because it locates the body column that the second pass splits at.

### B1. Extract one image per page

```bash
pdfimages -list BOOK.pdf | head    # one image per page is what the rest assumes
mkdir -p $RUN/pages && pdfimages -p -png BOOK.pdf $RUN/pages/p
```

`-p` puts the page number in each name, so `p-001-000.png` is the first image on PDF page 1. `stitch.py` reads that number, and it stops on a page with two images or a page with no image. A missing last page shows only against the page count, so pass `--pages` from `pdfinfo` to `stitch.py`. Without `-p`, pdfimages numbers images from `p-000.png`, which matches pages only when every page holds exactly one image. The 2026-11-03 run used that plain form, and *Rapid Development* gave 672 images for 672 pages, each about 1104 by 1387 pixels at 210 pixels per inch.

### B2. First pass on whole pages

```bash
python3 $SKILL/ocr_pages.py $RUN/pages $RUN/text --jobs 8
```

`ocr_pages.py` runs Vision on each image, several at a time, and writes `<stem>.ocr.tsv`, one recognized line per row as `y`, `x` and the text, where `y` and `x` are the line's top and left edges as fractions of the page. It compiles the Vision program that `kindle-highlights` ships, `skills/kindle-highlights/scripts/ocr.swift`, into `$RUN/bin/ocr` on first use. The script points at that file rather than copying it, so the two skills share one recognizer, and it relies on that program's output staying `y`, `x`, text. A rerun skips an image whose `.tsv` is newer than the image, so a stopped run resumes and a remade crop is read again. A `.tsv` appears only once its OCR has finished. An image whose OCR fails gets no `.tsv`, and the script exits 1. A `.tsv` whose image has gone from the folder is removed.

### B3. Whiten the shading and split the columns

```bash
uv run -q --with 'pillow>=10' python $SKILL/prep.py $RUN/pages $RUN/text $RUN/clean
```

`prep.py` changes each page in three ways.

1. **Whitening.** Every pixel at or above gray level 185 turns white, and darker pixels stretch to fill the range, so the shading vanishes while the text stays dark. `--threshold` sets the level. Text printed in a gray lighter than the threshold vanishes with the shading, so lower the threshold if that happens.
2. **Splitting.** The page splits into a body crop and a margin crop, 2% of the page width left of the body column (`--gap`). The body column's left edge is the 10th percentile, by lower rank, of the x of the first pass's lines longer than 45 characters (`--percentile`, `--min-chars`), since only body text runs that long. A page with no such line keeps one whole-page body crop, and the script lists those pages. `--split FRACTION` cuts every page at one fixed fraction instead.
3. **Padding and scaling.** Each crop gets a 64-pixel white border and is scaled up 2 times (`--border`, `--scale`). The border keeps text off the crop's edge, where the cut runs, and the scaling enlarges small type such as the margin notes.

The hand run cut at the median x minus 3%, and a review of it on 2026-11-03 found two faults, measured on 590 pages with an ordinary layout. A page's body edge was found from its pixels and compared with each rule's cut.

1. **Lost first letters.** Where a list or a quotation indents most of a page's long lines, the median moves right and the cut lands inside the lines that are not indented. Their first letters went to the margin crop on 28 pages.
2. **Clipped margin notes.** The gutter between the margin notes and the body is about 3% of the page, so a 3% gap cut into the right edge of the notes on 294 pages, and slivers of them started body lines.

The 10th percentile minus 2% lost letters on none of the 590 pages and clipped notes on 1. A second OCR pass under the new rule agreed, with margin slivers in the body falling from 174 pages to 2.

### B4. Second pass on the crops

```bash
python3 $SKILL/ocr_pages.py $RUN/clean $RUN/text2 --glob '*.png' --jobs 8
```

### B5. Stitch the pages and parts

```bash
python3 $SKILL/stitch.py $RUN/pages $RUN/text2 $RUN --first-pass $RUN/text --pages 672 --part 1-intro:1-50
```

Each page block holds the body lines in reading order, then one `[margin]` line carrying the margin column. A hyphen at a line end joins to the next line when that line starts in lowercase, which mends a word split across lines. The offset comes from the first pass's header and footer numbers, the same vote route A takes, or from `--offset N`, which wins when both are given. The script stops when a page has no body `.tsv`, since that means its OCR failed. It lists the pages with no text, and separately the pages with margin text but an empty body.

### Measured on *Rapid Development*

These figures come from runs on 2026-11-03, on the owner's 672-page PDF, which stays outside the repository.

- **Offset.** The vote gave offset 22, with 615 of 672 pages agreeing by this script's count. The hand count on the day gave 616. Stray numbers cast 3 votes for two other offsets, and the remaining pages print no number at their top or foot.
- **Blank pages.** Six pages came back with no text, PDF pages 3, 12, 20, 22, 646 and 671.
- **Speed.** The whole book OCRed in a few minutes with 8 jobs at once. A later timing of 56 second-pass crops took 6.3 seconds, which puts the 1,304 crops of the second pass at about two and a half minutes.
- **Agreement with the hand run.** The first version of `prep.py`, which used the hand run's median rule, made crops byte-identical to the hand run's. The second pass's `.tsv` files matched, and all 650 printed pages of `book_pages.txt` matched. The default cut has since changed, as B3 says.

### Limits of route B

- **Tables come out scrambled.** The recognizer returns each table cell as its own line and sorts lines top to bottom, so cells whose tops sit at slightly different heights interleave across columns, and a table's text comes out in the wrong order. Check a table against the page image before quoting it.
- **A hyphenated compound loses its hyphen** when it breaks at a line end, such as "self-" before "contained". The join cannot tell a split word from a compound.
- **Some layouts defeat the column cut.** The cut assumes at least a tenth of a page's long lines start at the body edge. On *Rapid Development* it moved a table of contents' hanging chapter numbers whole onto the `[margin]` line, filed the left column of 4 two-column index pages under `[margin]`, and still cut into tables or figures that start near the left edge on 11 of 19 such pages. Read those pages against their images.
- **The margin column must sit left of the body.** `prep.py` cuts one vertical line per page. A book with its margin on the right, or on alternating sides, needs `--split` per side or a change to `crops()`.
- **One image per page.** See B1.
- **Front matter is outside the parts and the citation check.** Its pages carry no printed number, so `--part` ranges and `ctx.py` reach printed pages only. Front matter stays in `book_pages.txt`.
- **The OCR is macOS only.** Vision is Apple's framework. `prep.py` and `stitch.py` run anywhere.

## Step 2: check citations

```bash
python3 $SKILL/ctx.py $RUN/book_pages.txt '64:the quoted words' '212:another quote'
python3 $SKILL/ctx.py $RUN/book_pages.txt --check '64:the quoted words' '212:another quote'
```

Without `--check`, `ctx.py` prints 260 characters either side of each quote on its cited page, in the book's own case, or NOT FOUND. A quote that starts on the cited page and runs onto the next counts as on the cited page. With `--check`, it prints one verdict per citation.

1. **OK** means the quote is on the cited page, or starts there and runs onto the next.
2. **NEAR** means the whole quote is on the page before or after instead, so the cited page is probably off by one.
3. **MISS** means it is on none of them.

Matching ignores case, runs of whitespace, curly against straight quotes, and hyphens, so a word split across lines and a compound broken at its hyphen both match. The script exits 1 on any MISS or NOT FOUND, so a pipeline can stop on a bad citation. A quote from a scanned book can miss on an OCR error rather than a wrong page, so read the context before calling the citation wrong.

## Tests

`tests/test_book_text.py` checks every script on inputs it makes itself: a PDF written byte by byte, page images drawn with Pillow that carry a gray box and a margin note, hand-written OCR rows, and a stand-in OCR program for `ocr_pages.py`. On macOS it also runs Vision end to end on a drawn page and checks that the shaded text survives and the margin note lands on the `[margin]` line. CI runs it on Linux, where only that Vision check skips.

```bash
uv run -q --with 'pillow>=10' python tests/test_book_text.py
```
