---
name: kindle-highlights
description: Extract a book's highlights from the Kindle notebook (read.amazon.com/notebook) into one verbatim, location-cited Markdown file, and recover highlights that Amazon's export limit truncated or hid — using the Mac Kindle app's synced annotation positions plus the Cloud Reader's rendered pages. Use when the user wants to export, extract, copy, or save Kindle book notes/highlights.
---

# Kindle highlights → Markdown

Extract every highlight for a book from `read.amazon.com/notebook` into one combined,
**verbatim, location-cited** Markdown file. Most highlights come straight from the page
DOM; the rest are truncated or entirely hidden by Amazon's clipping/export limit ("Some
highlights have been hidden or truncated due to export limits") and must be recovered.

Derived from four real runs: *Trade Your Way to Financial Freedom* (466 highlights, 41
truncated — recovered one-by-one from screenshots), *Trading and Exchanges* (1,211
highlights, 283 truncated + **180 fully hidden** — recovered in bulk via the Mac app's
position database + page OCR), *Inside the Black Box* (520 highlights, 73 truncated +
181 hidden — recovered via the overlay-geometry variant, median residual 0–1 char), and
*Quantitative Trading* (235 highlights, 57 truncated + 0 hidden — recovered via
cluster-jumps + prefix-anchored cuts, 44/57 at residual 0, rest ±2). Trust
the gotchas below — each one cost real debugging.

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
commas** (`1,211`), so match `[\d,]+` when parsing it. The count can also be a LIE on a
paginated notebook: one run showed "97 Highlights" for a 520-highlight book (the server
rendered only the first page's count). Treat the Step-4 DB as the count authority, or just
page until the token empties and count rows.

## Step 2 — scrape all highlights to a JSON file

Run [scripts/extract_highlights.js](scripts/extract_highlights.js) via
`Control_Chrome.execute_javascript` (pass the notebook tab's `tab_id`). It scrapes every
`.kp-notebook-row-separator` and **triggers a Blob download** of `<asin>_highlights.json` to
`~/Downloads` — downloading avoids piping 200 KB+ of text through the model and preserves exact
typography (curly quotes, em-dashes, bullets). Then read that file with normal tools.

Gotchas:
- Small books load all rows at once, but **large sets lazy-load in batches** (~500/burst) —
  poll `.kp-notebook-row-separator` count until it equals the header count before scraping.
  Synthetic window-scroll events may never trigger the next batch. The reliable path is the
  pagination endpoint: GET `/notebook?asin=<ASIN>&contentLimitState=<state>&token=<tok>`
  (values from the hidden inputs `.kp-notebook-content-limit-state` and
  `.kp-notebook-annotations-next-page-start`; send `x-requested-with: XMLHttpRequest`), parse
  the returned HTML fragment for rows + refreshed inputs, loop until the token is empty
  (~50–100 rows/page). The token can also be **circular**: one run had all 235 rows already in
  the DOM yet a non-empty token, and the fetched pages re-served 139 exact duplicates — always
  dedupe fetched rows against what you have on `(loc, text)` before believing a bigger count.
- The export limit doesn't just truncate: past its budget it **hides highlights entirely** —
  the row has a location but NO text (only the banner). The scraper keeps these
  (`hidden: true, text: null`); never filter rows by text presence, filter by `loc`.
- A Blob download from a **background** tab is blocked — and Chrome blocks the **second**
  automatic download from the same origin even in a focused tab. With "ask where to save each
  file" enabled, every download instead raises a native Save-As dialog that page JS cannot
  dismiss (the payload bytes do land in `~/Downloads/.com.google.Chrome.*` temp files, readable
  directly). Fallback that always works:
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
  A locked screen (or full occlusion) flips `document.visibilityState` to `hidden`: renders
  freeze AND in-page `setTimeout` chains throttle to ~1/min, so a batched sweep silently
  crawls instead of erroring. When a batch stalls, probe visibility first; resume when
  `visible`, or drive each cycle externally (one JS call per flip survives throttling).
- **Highlight overlays render for one 500-row page of `getAnnotations` at minimum** (the API
  needs an `X-ADP-Session-Token` you can't reach). Books modestly over 500 may render ALL
  overlays (verified: 520/520 painted); big books stop at ~500. Probe empirically — where
  overlays exist they beat Step-4 arithmetic (see the overlay-geometry variant below); where
  they don't, extents must come from Step 4. Overlays can also paint a beat AFTER the page
  img — collect rects at capture time, not immediately post-flip, and expect the occasional
  missing/partial overlay (a per-highlight glitch, not a cap).
- Navigation: the `&location=N` URL parameter does nothing. Use the **Go-to-Page modal**
  (Reader menu → Go to Page): set the native `<input>` via the value-property setter + an
  `input` event, then click Go. Landing can be off by a page (screens ≠ print pages; one screen
  can span 2–3 print pages, and a print page can span multiple screens).
- Page-flip: dispatch keydown **and keyup** for ArrowRight on several targets — `window`,
  `document`, `document.body`, `.kg-client-root`, `ion-app` — one target alone is unreliable,
  and the chevron `.click()` does nothing. **A leftover modal/panel silently swallows the keys**
  (a stuck Go-to-Page modal is the classic wedge; the OPEN annotations panel does it too — after
  every panel-jump, close the panel before flipping, or the sweep re-captures the same screen
  forever; when flips die and no overlay is open, reload
  the tab and reinstall your helpers). Keyboard-independent fallback (works after Aa-panel
  interactions kill the arrows): dispatch `mousedown` + `mouseup` MouseEvents at the center of
  `[aria-label="Next page"]` / `"Previous page"` — exactly one viewport per pair. Do NOT add
  the full pointer/mouse/click 5-event sequence: it double-fires.
- **Capture without screenshots:** `fetch(blobUrl)` fails (CSP), but `drawImage` of the loaded
  `<img>` into a canvas is untainted → `canvas.toBlob` → POST to the localhost receiver. This
  yields the full-resolution page render (≈2048 px wide) regardless of OS screenshot policy.
- Density setup still applies (snippets 7/8 in
  [scripts/reader_helpers.js](scripts/reader_helpers.js)): snapshot `KWR_Display_Settings`,
  set narrow margins, restore afterward. Settings are origin-wide localStorage —
  never run two extraction sessions concurrently. **Pick the font size by pixels-per-char,
  not by fewest flips**: the render width = CSS viewport width × devicePixelRatio, capped at
  2048, so px-per-char ≈ font CSS px × dpr. Vision OCR is near-perfect at ≥~17 px/char
  (fontSizeIndex 4 at dpr 1, or smallest font on a Retina/dpr-2 window) and garbles at 11
  (fontSizeIndex 0 at dpr 1). The smallest font is only correct on a dpr-2 window. A window
  WIDER than 2048 CSS px downscales the render (2560 → 2048 = 0.8×; an unresizable fullscreen
  window can force this) — bump the font to compensate: fontSizeIndex 6 (~21 px → ~17 effective)
  was verified near-perfect.

### Small-scale path (a few dozen truncated, all within the first 500)

As in the original run: jump via the annotations panel (`#notebook-grouped-item-<pos>`, only the
first 500 exist), capture the screen with overlays painted from `.kg-client-highlight` rects
(class token `<startPos>/<endPos>` = exact extent), read the yellow span, transcribe the
completion into `completions.json`, batch by cluster.

### Truncated-only path (no hidden rows — every blocked highlight has a known prefix)

When nothing is fully hidden, skip both the full sweep and geometry x-cuts:

1. **Cluster** the truncated highlights by DB start-position gap (< ~3000 positions). One run's
   57 truncated highlights formed 14 clusters whose spans summed to ~15% of a full sweep —
   ~44 captures total instead of ~300.
2. **Per cluster:** open the annotations panel → jump to the cluster's first highlight
   (`#notebook-grouped-item-<startPos>`) → **close the panel** (see the key-swallowing gotcha)
   → capture → flip → capture … until the cluster's LAST token (`<start>/<end>` of its last
   truncated highlight) has appeared and then left the screen. ~3 screens per cluster.
3. **Cut by prefix anchor, not geometry.** Proportional-x boundary cuts assume monospace and
   overshoot by 3–4 words in the book's proportional font. Instead: take the OCR lines inside
   the token's vertical band (first-rect top → last-rect bottom, still filtering rects taller
   than ~45 CSS px), join them (a line ending in `-` joins the next without a space), then
   **find the known notebook prefix** in that text (normalize for matching only: en-dash →
   hyphen, curly → straight, collapse spaces), align the prefix END with difflib (tolerates
   OCR slips: dropped spaces like "I know"→"Iknow", AI→Al), and cut exactly
   `(end − start + 1) − len(prefix)` chars from there, snapping the end to the word edge that
   minimizes the residual. The value written to `completions.json` is that tail alone, so
   **OCR errors inside the prefix region cost nothing** — the build reconstructs
   `notebook prefix + completion`. Validate per highlight: prefix found + |residual| ≤ 3.
   Multi-screen highlights: join fragments by dropping the longest suffix-prefix overlap
   (≥ 20 chars) at each seam.

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
   Calibrate the non-word threshold on the KNOWN notebook texts first — /usr/share/dict flags
   5–11% of perfectly good finance prose, so flag outliers vs that baseline, not an absolute rate.

**Overlay-geometry variant — preferred whenever overlays render for the blocked range.** Instead
of sentence-boundary DP, collect per-screen overlay geometry during the sweep: for each
`.kg-client-highlight` class-token `<start>/<end>`, record the first and last word-rects
(sort rects by y then x), normalized against the page-img bounding rect. Then cut each blocked
highlight from its own screens: take OCR lines whose centers fall inside [first-box top,
last-box bottom] (spillover screens concatenate; each screen's token carries its own boxes),
cut the boundary lines at the proportional x of the box edge snapped to a word edge, and trim
boundary-word bleed against the Step-4 length. This turns recovery into local pixel cuts —
median length residual 0–1 char over 236 cuts, no heading arithmetic. Two gotchas: an
exhibit-spanning highlight wraps the figure image in one giant rect (height ≫ a word box's
25-ish px — filter rects taller than 40 CSS px before picking first/last, and drop small-font
figure-internal OCR lines while keeping `EXHIBIT`-prefixed caption lines); and word boxes are
the DOM's, so **validate the cutter on the in-range FULL highlights against their notebook
text first** — byte-exact + ≥99% rates tell you the true error classes before any blocked cut
is trusted.

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
  tag them approximate rather than pretending precision. Their captions ("EXHIBIT N.M …") ARE part
  of the notebook text; figure innards (axis labels, legends) are not.
- **Measure the notebook's typography per book and match it** — count glyphs in the exported rows.
  One book used curly double quotes (252:0) with STRAIGHT apostrophes (251:0); don't assume both curl.
- **List markers ("1.", "•", "■") are neither rendered in notebook text nor counted by the position
  ruler** — strip them from recovered text (extent-fit verified both ways). Footnote digits glued
  after punctuation are usually absent from notebook text too (inconsistently) — strip for consistency.
- OCR clips trailing digits in dollar amounts and small caption text: sweep recovered text with
  `\$\d+\.(?=\s|$)` and re-read hits from the page image; an arithmetic cross-check often pins the
  digits (2,340 of 23.4M milliseconds ⇒ "0.01 percent"). Also watch em-dashes read as hyphens.
- **Display equations (standalone math blocks) are NOT in notebook text and NOT counted by the
  position ruler** — same class as headings and list markers (verified: the notebook prefix of a
  formula-spanning highlight skipped the equations entirely). OCR inserts them mid-highlight as
  garbage ("fᵢ*=mᵢ/sᵢ²" read as "2 m/s") — delete them from recovered text and let the freed
  chars extend the end cut; check the result against the page image.
- OCR flattens Greek letters (θ → "O"/"0", μ → "u") and reads zero as letter O in prose
  ("greater than O") — restore from context, using the notebook prefix's glyphs as the guide
  when the same symbol appears there.
- **Dictionary-sweep URL slugs specifically**: "your"→"vour" inside a printed URL survived every
  other QA check (word sweeps skip slug fragments); URLs are also cheap to verify externally.
