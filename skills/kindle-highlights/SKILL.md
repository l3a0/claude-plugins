---
name: kindle-highlights
description: Extract a book's highlights from the Kindle notebook (read.amazon.com/notebook) into one verbatim, location-cited Markdown file, and recover highlights that Amazon's export limit truncated or hid — using the Mac Kindle app's synced annotation positions plus the Cloud Reader's rendered pages. Use when the user wants to export, extract, copy, or save Kindle book notes/highlights.
---

# Kindle highlights → Markdown

Extract every highlight for a book from `read.amazon.com/notebook` into one combined,
**verbatim, location-cited** Markdown file. Most highlights come straight from the page
DOM; the rest are truncated or entirely hidden by Amazon's clipping/export limit ("Some
highlights have been hidden or truncated due to export limits") and must be recovered.

Derived from two real runs: *Trade Your Way to Financial Freedom* (466 highlights, 41
truncated — recovered one-by-one from screenshots) and *Trading and Exchanges* (1,211
highlights, 283 truncated + **180 fully hidden** — recovered in bulk via the Mac app's
position database + page OCR). Trust the gotchas below — each one cost real debugging.

## The one prerequisite that unblocks everything

Driving the page needs **JavaScript execution in the tab** — any browser-control MCP that can
run JS in the user's real, logged-in Chrome works. The verified reference is the
**Control Chrome MCP** (Anthropic's Claude Desktop extension: Settings → Extensions →
"Control Chrome"; tools appear as `Control_Chrome.*`), which runs JS via AppleScript and
requires Chrome's **"Allow JavaScript from Apple Events"** to be ON:

> Chrome menu bar → **View → Developer → Allow JavaScript from Apple Events** → check it →
> confirm the warning → **quit & relaunch Chrome**.

- Symptom when OFF: `Control_Chrome.execute_javascript` returns `"Google Chrome is not running"`.
- The Claude-in-Chrome extension's `javascript_tool`/`computer`(click/screenshot) may fail with
  `Cannot access a chrome-extension:// URL of different extension` when another browser-control
  extension contends for the debugger. Its `read_page`/`find`/`navigate` still work, but
  `read_page` **caps each text node at ~100 chars** — useless for full highlight text. Use the
  Control_Chrome JS scrape instead.
- Screen-control of the browser may be read-only tier and the **Kindle desktop app** screen may be
  blocked entirely — but neither matters much anymore: captures come from the page's own canvas
  (below), and the desktop app is used only via its **files on disk**, which needs no screen access.
- **Shared Chrome hazard:** if another session is driving the same Chrome, open your own tab —
  and for the reader (which only renders while visible), your own **window** (see Step 5).

## Step 1 — open the book's notebook

Navigate the tab to `https://read.amazon.com/notebook`. The `?asin=` parameter is ignored and
the page may restore the last-viewed book — select the book by clicking its entry in the
library sidebar (`#kp-notebook-library .kp-notebook-library-each-book`, id = ASIN) and confirm
the annotations-pane title. Header shows `N Highlights | M Notes` — **the count has thousands
commas** (`1,211`), so match `[\d,]+` when parsing it.

## Step 2 — scrape all highlights to a JSON file

Run [scripts/extract_highlights.js](scripts/extract_highlights.js) via
`Control_Chrome.execute_javascript` (pass the notebook tab's `tab_id`). It scrapes every
`.kp-notebook-row-separator` and **triggers a Blob download** of `<asin>_highlights.json` to
`~/Downloads` — downloading avoids piping 200 KB+ of text through the model and preserves exact
typography (curly quotes, em-dashes, bullets). Then read that file with normal tools.

Gotchas:
- Small books load all rows at once, but **large sets lazy-load in batches** (~500/burst) —
  poll `.kp-notebook-row-separator` count until it equals the header count before scraping.
- The export limit doesn't just truncate: past its budget it **hides highlights entirely** —
  the row has a location but NO text (only the banner). The scraper keeps these
  (`hidden: true, text: null`); never filter rows by text presence, filter by `loc`.
- A Blob download from a **background** tab is blocked — and Chrome blocks the **second**
  automatic download from the same origin even in a focused tab. Fallback that always works:
  stash the payload on `window.__x`, run [scripts/receiver.py](scripts/receiver.py) locally,
  and `fetch('http://127.0.0.1:8931/json?name=…', {method:'POST', body: window.__x})` — the
  notebook AND reader pages' CSP both allow localhost fetches (the receiver answers the
  CORS/private-network preflight).
- Each row yields `{loc, color, text, note, truncated, hidden}`. `truncated: true` with text
  means the text is only the opening and ends with `…`.

## Step 3 — build the combined Markdown

```
python3 scripts/build_notes.py ~/Downloads/<asin>_highlights.json <out>.md [completions.json]
```
Emits: a citation header (title/author/ASIN from the scrape; fill edition/publisher/year by hand),
then `### Location N · color` sections with verbatim `> ` blockquotes. Truncated highlights with no
recovered completion get a `⚠ truncated` flag; hidden ones get `⚠ hidden` placeholders. In
`completions.json`, a truncated loc's value is the **completion** (text after the `…`) and a hidden
loc's value is the **full text**. Recovered entries get a `↻ recovered` tag. Re-run any time — it's
deterministic.

## Step 4 — get exact extents from the Mac Kindle app (do this before any recovery)

**Game-changer:** the Kindle desktop app syncs **every** highlight's exact character-precise
start/end position, with no export limit — including the fully-hidden ones. No screen access
needed; it's a SQLite file:

1. `open -a "Amazon Kindle" "kindle://book?action=open&asin=<ASIN>"` — name the app explicitly:
   a bare `open kindle://…` may route to the **classic** Kindle.app, whose data lives elsewhere.
   The new app is bundle `com.amazon.Lassen`. Wait ~30 s for the annotation sync.
2. Read `~/Library/Containers/com.amazon.Lassen/Data/Library/KSDK/amzn1.account.*/ksdk_annotation_v1.db`
   (copy it + `-wal` aside first), table `server_view`, rows where `dataset_id LIKE '<ASIN>%'`.
   Each `serialized_payload` is JSON with `start_position.shortPosition` / `end_position.shortPosition`
   and `type: "HIGHLIGHT"`.
3. Sorted by position, the rows align **1:1** with the scraped highlights sorted by location.
   Verify: `end − start + 1 == len(notebook text)` within ±2 for the non-truncated ones (confirmed
   on 748 highlights). The panel item ids in the web reader (`notebook-grouped-item-<pos>`) use the
   same positions.

This turns recovery from transcription-with-guessed-boundaries into **cutting text to known
lengths**. (`AnnotationStorage` in the same container holds only a ~10-row `popular` stub until
the book is opened; the classic app's `My Clippings.txt` only has physical-device highlights.)

## Step 5 — recover blocked highlights from the Cloud Reader

**Key fact:** the blocked text is NOT on the notebook page (Amazon truncates server-side) and the
in-reader annotations panel is no help either (server-clamped ~100-char previews, capped at 500
items). Only the rendered pages have the text, as **rasterized images** (`<img src="blob:…">` in
`.kg-full-page-img`).

Reader mechanics (hard-won):

- **The reader renders only while its tab is visible.** Boot stalls and page-flips freeze in a
  hidden tab. Give it its own Chrome **window** (`osascript`: `make new window`) so other tabs
  and sessions don't freeze it; the window may sit behind others but must not be minimized.
- **Highlight overlays render only for the first ~500 annotations** of the book (the client
  fetches one 500-row page of `getAnnotations` and stops; the API needs an `X-ADP-Session-Token`
  you can't reach). Beyond 500 there is NO yellow on the page — extents must come from Step 4.
- Navigation: the `&location=N` URL parameter does nothing. Use the **Go-to-Page modal**
  (Reader menu → Go to Page): set the native `<input>` via the value-property setter + an
  `input` event, then click Go. Landing can be off by a page (screens ≠ print pages; one screen
  can span 2–3 print pages, and a print page can span multiple screens).
- Page-flip: dispatch keydown **and keyup** for ArrowRight on several targets — `window`,
  `document`, `document.body`, `.kg-client-root`, `ion-app` — one target alone is unreliable,
  and the chevron `.click()` does nothing. **A leftover modal/panel silently swallows the keys**
  (a stuck Go-to-Page modal is the classic wedge; when flips die and no overlay is open, reload
  the tab and reinstall your helpers).
- **Capture without screenshots:** `fetch(blobUrl)` fails (CSP), but `drawImage` of the loaded
  `<img>` into a canvas is untainted → `canvas.toBlob` → POST to the localhost receiver. This
  yields the full-resolution page render (≈2048 px wide) regardless of OS screenshot policy.
- Density setup still applies (snippets 7/8 in
  [scripts/reader_helpers.js](scripts/reader_helpers.js)): snapshot `KWR_Display_Settings`,
  set smallest font + narrow margins, restore afterward. Settings are origin-wide localStorage —
  never run two extraction sessions concurrently.

### Small-scale path (a few dozen truncated, all within the first 500)

As in the original run: jump via the annotations panel (`#notebook-grouped-item-<pos>`, only the
first 500 exist), capture the screen with overlays painted from `.kg-client-highlight` rects
(class token `<startPos>/<endPos>` = exact extent), read the yellow span, transcribe the
completion into `completions.json`, batch by cluster.

### Bulk path (hundreds blocked / anything past the 500-overlay cap)

Screenshot-per-highlight does not scale; do a **sweep + OCR + position-math** pipeline instead:

1. **Sweep** every screen from the first blocked highlight to the end: flip → wait ~2 s →
   canvas-capture → POST, in batches of ~10–12 per JS call (staggered `setTimeout`s), verifying
   the page label advances between batches. ~150–250 screens covers half a book.
2. **OCR locally** with [scripts/ocr.swift](scripts/ocr.swift) (`swiftc -O ocr.swift -o ocrbin`) —
   Apple Vision `VNRecognizeTextRequest`, near-perfect on these clean renders, zero tokens. Keep
   `usesLanguageCorrection = false` for fidelity.
3. **Stitch** screens into one text stream (dedupe identical screens by md5 — missed flips
   produce duplicates; label jumps ≥4 pages signal a missed capture).
4. **Cut by position math** from the Step-4 table: truncated highlights by fuzzy prefix-match +
   known length; hidden highlights by aligning **sentence boundaries** to the exact
   lengths/gaps (97% of highlights start at a capital letter, 99% end at sentence punctuation —
   dynamic programming over sentence boundaries with per-item length residuals works well).
5. **Corrections that matter:** section headings and sidebar titles are NOT counted by the
   position ruler — add their length back when a span crosses one. Tables/figures inside a span
   garble OCR order and lengths — reconstruct in reading order and tag the entry `≈ approximate`.
   Flag OCR-garbled regions by dictionary non-word rate (stem before checking) and re-read those
   from the page images by eye. Verify every low-confidence cut against its source image.

## Step 6 — QA before declaring done

- `recovered == truncated + hidden`, `pending == 0` (build prints these).
- Seam check: for each recovered truncation, prefix + completion joins with no double space, no
  doubled word, no leftover `…` (mid-text `…` may be genuine book punctuation — check before
  "fixing"). Join with no space when the completion starts with punctuation.
- Junk sweep: no stray `«` (OCR's misread of the sidebar-close glyph), no sidebar-title fragments
  glued to span starts/ends, no mid-word cut endings.
- `### Location` section count == highlight count; file ends with exactly one newline.
- Display settings restored from the snapshot; localhost receiver stopped; note that the run
  moves the book's furthest-read position (the user can decline the sync prompt on next open).

## Verbatim judgment calls

- Mid-line hyphens in justified text are usually soft (line-break) hyphens — render the dominant book
  form (e.g. "channel breakout", not "break-out"), cross-checking another occurrence.
- Italic *R* / *1R* / *2R* etc.: Amazon's scraped prefix renders them plain, so keep completions plain
  for consistency (or italicize everywhere — just be consistent).
- Keep the scraped prefix byte-exact (the build does this automatically); only transcribe completions.
- Table/figure-spanning highlights have no faithful linear form — transcribe in reading order and
  tag them approximate rather than pretending precision.
