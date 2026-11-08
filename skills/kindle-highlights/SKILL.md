---
name: kindle-highlights
description: Extract a book's highlights from the Kindle notebook (read.amazon.com/notebook) into one verbatim, location-cited Markdown file, and recover highlights that Amazon's export limit truncated or hid — using the Mac Kindle app's synced annotation positions plus the Cloud Reader's rendered pages. Use when the user wants to export, extract, copy, or save Kindle book notes/highlights.
---

# Kindle highlights → Markdown

Extract every highlight for a book from `read.amazon.com/notebook` into one combined,
**verbatim, location-cited** Markdown file. Most highlights come straight from the page
DOM; the rest are truncated or entirely hidden by Amazon's clipping/export limit ("Some
highlights have been hidden or truncated due to export limits") and must be recovered.

Derived from five real runs: *Trade Your Way to Financial Freedom* (466 highlights, 41
truncated — recovered one-by-one from screenshots), *Trading and Exchanges* (1,211
highlights, 283 truncated + **180 fully hidden** — recovered in bulk via the Mac app's
position database + page OCR), *Inside the Black Box* (520 highlights, 73 truncated +
181 hidden — recovered via the overlay-geometry variant, median residual 0–1 char),
*Quantitative Trading* (235 highlights, 57 truncated + 0 hidden — recovered via
cluster-jumps + prefix-anchored cuts, 44/57 at residual 0, rest ±2), and *Algorithmic
Trading* (301 highlights, 83 truncated + 140 hidden, recovered with the scripted
**word-rect matching path** below, all 223 within 5 characters of the app's extents and 209 within 2). Trust
the gotchas below — each one cost real debugging.

The fifth run turned the recovery into scripts. The path in one line: `align_extents.py`
(Step 4) → `reader_capture.js` sweep (Step 5) → `assemble.py` → `finalize.py` → `qa_words.py`
(Step 6). Every script runs from a **run directory**: a working folder that holds `pages/` (the captures) and
`aligned.json`. The scripts themselves stay in the skill's `scripts/` folder. So `scripts/…` in every command
below means that folder, given as an absolute path from the run directory. Set `SKILL` to the skill's directory
once and the commands read as written. `tests/test_scripts.py` checks `hlmap.py`, `locmap.py`,
`notebook_pages.js`, `extract_highlights.js` and `cjs.sh`'s in-page guard on made-up inputs, with no book text:
`python3 "$SKILL/tests/test_scripts.py"`.

A sixth run, *The Art of Scalability* (382 highlights, 24 truncated, 0 hidden), recovered none of its
truncated highlights. Its goal moved from the highlights to the book's full text, which it captured with the
full-book path under Step 5. Its figures stay out of the recovery counts above, and its gotchas sit in the
steps below.

Three more runs exported every highlight in full, so they had nothing to recover and their figures stay out of
the recovery counts too.

1. *Designing Data-Intensive Applications* (580 highlights, 0 truncated, 0 hidden) captured the full text the
   same way. Its reader footer showed page numbers instead of locations, which `locmap.py` repairs (step 8 of
   the full-book path).
2. *Code Complete* (113 highlights, 1 note, 0 truncated, 0 hidden) paged its notebook with
   `notebook_pages.js` and drove Chrome through `cjs.sh`.
3. *Rapid Development* (187 highlights, 15 notes, 0 truncated, 0 hidden) did the same.

Neither of the last two would open in the web reader, so their full text came from the owner's own copies,
and `hlmap.py` gave each highlight its printed page (see "Matching highlights to printed pages").

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
- The same error stopped the extension's `javascript_tool` and `screenshot` on the sixth run, right after a
  1Password autofill. AppleScript from the shell still worked, because it is the route Control Chrome takes and
  needs only the Apple Events setting above. [scripts/cjs.sh](scripts/cjs.sh) is that route as a runner. Use it
  when the extension fails with that error and Control Chrome is not installed. The 2026-11-03 runs of *Code
  Complete* and *Rapid Development* drove Chrome through it. A permission the owner refused, or a policy that
  blocks the browser tool, is a different case. It is the owner's to lift, and `cjs.sh` is no way around it,
  the same rule that holds for the Kindle app under Step 5.

  ```
  "$SKILL/scripts/cjs.sh" --list                                # window id, tab id, URL of each read.amazon.com tab
  "$SKILL/scripts/cjs.sh" W T "$SKILL/scripts/notebook_pages.js"   # run a file in tab T of window W
  "$SKILL/scripts/cjs.sh" W T -e 'JSON.stringify(window.__pg)'   # run one expression, such as a poll
  ```

  Its limits come from AppleScript.

  1. It needs Chrome's Allow JavaScript from Apple Events, and the macOS Automation grant for the terminal to
     control Chrome.
  2. It addresses a tab by window id and tab id, never by "the active tab", so another session's tabs cannot
     redirect it. `--list` prints the ids, and they hold for the tab's life.
  3. `execute` returns only a synchronous value, and AppleScript mangles anything but a string. So an async
     script stores its result on `window` and returns at once, and a second call polls for it with
     `JSON.stringify`.
  4. A download started from it can be blocked or can raise a native Save dialog (Step 2). So set
     `window.__khNoDownload = true` before `extract_highlights.js` and post the payload to the receiver
     instead.

  This route has a cost. Any process that holds macOS's Automation grant to control Chrome, which Step 5's
  `osascript` window steps need too, can then run JavaScript in any tab on any site, including pages 1Password
  has just filled. Chrome has no per-site switch for it short of an enterprise DevTools policy. So `cjs.sh`
  reads the tab's URL first and refuses unless it starts with `https://read.amazon.com/`. The script it sends
  also starts with a line that throws unless the page running it is on that origin, so a navigation between
  the check and the run cannot redirect it. `--list` shows only tabs on that site, so other sites' URLs stay out
  of the transcript, and `cjs.sh` never launches Chrome. Undo the setting and the grant after the run (Step 6).
- Screen-control of the browser may be read-only tier and the **Kindle desktop app** screen may be
  blocked entirely — but neither matters much anymore: captures come from the page's own canvas
  (below), and the desktop app is used only via its **files on disk**, which needs no screen access.
  Where the desktop app is blocked, do not get around the block with scripted keystrokes or window captures
  (see "Opening a book in the reader" under Step 5).
- **Shared Chrome hazard:** if another session is driving the same Chrome, open your own tab —
  and for the reader (which only renders while visible), your own **window** (see Step 5).
  One run had another session open ten `127.0.0.1:91xx` tabs into the reader window mid-sweep. Address tabs by id, never by "the active tab".

## Step 1 — open the book's notebook

Navigate the tab to `https://read.amazon.com/notebook`. The `?asin=` parameter is ignored and
the page may restore the last-viewed book — select the book by clicking its entry in the
library sidebar (`#kp-notebook-library .kp-notebook-library-each-book`, id = ASIN) and confirm
the annotations-pane title. Header shows `N Highlights | M Notes` — **the count has thousands
commas** (`1,211`), so match `[\d,]+` when parsing it. The count can also be a LIE on a
paginated notebook: one run showed "97 Highlights" for a 520-highlight book (the server
rendered only the first page's count). Treat the Step-4 DB as the count authority, or just
page until a page adds no new row (`notebook_pages.js`, Step 2) and count rows.

## Step 2 — scrape all highlights to a JSON file

Run [scripts/extract_highlights.js](scripts/extract_highlights.js) via
`Control_Chrome.execute_javascript` (pass the notebook tab's `tab_id`), or through `cjs.sh`. It scrapes every
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
  the returned HTML fragment for rows + refreshed inputs, and loop until a page adds no new row
  (~50–100 rows/page). The token can also be **circular**: one run had all 235 rows already in
  the DOM yet a non-empty token, and the fetched pages re-served 139 exact duplicates — always
  dedupe fetched rows against what you have on `(loc, text)` before believing a bigger count.
  The sixth run confirmed it on a second book. All 382 rows were in the DOM, and the token served 303 more over
  5 pages, every one an exact copy.
- **Page with [scripts/notebook_pages.js](scripts/notebook_pages.js).** It fetches the pages through that
  endpoint, appends each new row to `#kp-notebook-annotations`, and stops at the first page that adds no new
  row, which also ends a circular token. A row is new when its location, text, note and header have not been
  seen. Rows with no text also carry their order among the text-less rows at that location, so two hidden
  highlights that start at one location stay two rows. The script runs async and returns `started`, so poll
  `JSON.stringify(window.__pg)` until `done` is true. Three fields need reading.

  1. `capped: true` means its 60-page limit stopped it with pages left. Run it again on the same page load and
     it resumes from where it stopped.
  2. `err` names a page that failed or held no rows at all, such as a sign-in page served with HTTP 200.
  3. `header` is the page's own `N Highlights | M Notes` text. It can undercount, so Step 4's count check is
     the one that proves no row is missing.

  It reads the ASIN from the book's `/dp/` link on the page, since the notebook ignores `?asin=` in its own
  URL. `window.__khAsin`, set by hand, is used only when the page has no `/dp/` link, and both scripts stop
  when it disagrees with the page's link, since a value left over from an earlier book would mislabel the
  next one. On 2026-11-03 it loaded *Code Complete*'s 113 highlights and 1 note and
  *Rapid Development*'s 187 highlights and 15 notes. Neither book had a truncated or hidden row. The full
  sequence through `cjs.sh`, with the receiver running from the run directory:

  ```
  "$SKILL/scripts/cjs.sh" W T "$SKILL/scripts/notebook_pages.js"
  "$SKILL/scripts/cjs.sh" W T -e 'JSON.stringify(window.__pg)'      # repeat until done is true
  "$SKILL/scripts/cjs.sh" W T -e 'window.__khNoDownload = true'
  "$SKILL/scripts/cjs.sh" W T "$SKILL/scripts/extract_highlights.js"
  "$SKILL/scripts/cjs.sh" W T -e "fetch('http://127.0.0.1:8931/json?name=<ASIN>_highlights', {method: 'POST', body: window.__khl}); 'posted'"
  ```

  The receiver saves `pages/<ASIN>_highlights.json`, where Step 4 looks for it.
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
  CORS/private-network preflight). The receiver refuses with 403 any request whose `Origin` is not
  `https://read.amazon.com`, so another page open in the browser cannot write into `pages/`. A manual
  `curl` against it needs `-H "Origin: https://read.amazon.com"`. A refused `fetch` shows in the page only as
  `TypeError: Failed to fetch`, and the receiver prints the refused origin to its stderr. Regional Kindle sites such
  as `read.amazon.co.uk` are refused too, because no run has used one. Add the site's origin to `ALLOWED_ORIGINS` in
  `receiver.py` to run there.
- Each row yields `{loc, color, text, note, truncated, hidden}`. `truncated: true` with text
  means the text is only the opening and ends with `…`.

## Step 3 — build the combined Markdown

```
python3 "$SKILL/scripts/build_notes.py" ~/Downloads/<asin>_highlights.json <out>.md [completions.json] [--edition "2nd ed." --publisher Wiley --year 2013]
```
When the receiver saved the scrape instead of a download, the input is `pages/<asin>_highlights.json`.
Emits: a citation header. Title, author and ASIN come from the scrape. Edition, publisher and year come
from the flags or the constants at the top of the script, since the notebook page does not carry them. Then
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

Scripted: copy the Step-2 download into the run directory's `pages/` (or pass `--highlights` to point at it
where it landed), then

```
python3 "$SKILL/scripts/align_extents.py" <ASIN>
```

copies the database aside, runs items 2 and 3 of the list above, and writes `aligned.json`. Each highlight
there carries `start`, `end` and `extent`. An **extent** is the highlight's length in characters, `end − start + 1`.
The script then prints the checks. The **residual** is the extent minus the length of the text you have, so a
residual of 0 means the two agree exactly. Expect 0 and −1 to dominate on the fully exported rows. It also prints
the truncated and hidden counts, where the hidden run starts, and the blocked highlights clustered by position gap
with the sweep span each cluster needs. A count mismatch means the app has not synced yet or the scrape missed a page.
Delete the `db/` copy when the run is done. It holds every book's highlights for the account, not just this one.

## Step 5 — recover blocked highlights from the Cloud Reader

**Key fact:** the blocked text is NOT on the notebook page (Amazon truncates server-side) and the
in-reader annotations panel is no help either (server-clamped ~100-char previews, capped at 500
items). Only the rendered pages have the text, as **rasterized images** (`<img src="blob:…">` in
`.kg-full-page-img`).

Reader mechanics (hard-won):

- **Opening a book in the reader.** On 2026-11-03 `https://read.amazon.com/?asin=<ASIN>` landed on
  `/kindle-library`, not in the book, and the library page carried the book as
  `#library-item-option-<ASIN>`, which is where to open it. Earlier runs reached the reader through `?asin=`
  directly, so check which page loaded. Some books never open in the web reader at all. That day the Microsoft
  Press DV-Professional editions of *Code Complete* and *Rapid Development* would not. The Mac Kindle app
  (`com.amazon.Lassen`) was no way around it, because policy blocked the app for computer use that day. Do not
  get around such a block with scripted keystrokes, such as System Events `keystroke`, or with window
  captures, such as `screencapture -l`. Reading the app's files on disk in Step 4 is still fine, since it needs
  no screen. For such a book the route to its text is the owner's own copy, a PDF or a scan, through the
  `book-text` skill (`/l3a0:book-text`), which [PR #51](https://github.com/l3a0/claude-plugins/pull/51) adds.
  Then "Matching highlights to printed pages" below gives each highlight its page.
- **The reader can sit behind `read.amazon.com/checkpoint/continue`**, a page that reads "Website
  Temporarily Unavailable". On the sixth run it showed no challenge to solve, and loading the reader again once
  a minute got past it within a few minutes. A page that does show a challenge is the user's to clear.
- **The reader renders only while its tab is visible.** Boot stalls and page-flips freeze in a
  hidden tab. Give it its own Chrome **window** (`osascript`: `make new window`) so other tabs
  and sessions don't freeze it; the window may sit behind others but must not be minimized.
  A locked screen (or full occlusion) flips `document.visibilityState` to `hidden`: renders
  freeze AND in-page `setTimeout` chains throttle to ~1/min, so a batched sweep crawls instead of erroring. The sweep stops when it sees the tab hidden, with
  `__kh.sweepEnd.why` set to `hidden`, but a visible tab that is merely throttled still crawls. When a batch stalls, probe visibility first; resume when
  `visible`, or drive each cycle externally (one JS call per flip survives throttling).
- **macOS full-screen Spaces are the usual reason the tab is hidden.** If the user's Chrome
  window is in macOS full-screen, `make new window` inherits full-screen on its own Space. The
  tab goes `hidden` the moment the user switches Space, and it stays hidden however you raise
  it. `open -na "Google Chrome" --args --new-window <url>` does the same. Check before sweeping:
  every Chrome window's `bounds` equal to the display size is the tell (Chrome's `mode` still
  says `normal`). Escaping takes four steps, because System Events, the macOS scripting bridge to
  windows, sees only the Space that is currently in front:

    1. Pull the reader's Space in front. A `window.open(url, 'x', 'popup=1,width=…')` from the
       reader tab does it.
    2. Run `set value of attribute "AXFullScreen" of window 1 to false` on the Chrome process.
    3. Wait about 3 seconds.
    4. Run `set bounds of window id N to {…}` onto a display nobody is using. The laptop panel
       at device pixel ratio 2 is ideal.

  `set index` and `activate` alone do nothing.
  On the sixth run `set bounds` would not move a new window onto the laptop panel, and the run went ahead at
  ratio 1 (see "Two columns, not one" below).
- **Use [scripts/reader_capture.js](scripts/reader_capture.js)** for the in-page side: install
  it once per page load (`__kh`), then `__kh.applySettings(4, 2)` (it reloads, so re-install after),
  `__kh.jump(<startPos>)`, `__kh.sweep(from, n, prefix)` and `__kh.restoreSettings()`. Its
  capture pads the render with a 64 px white border and stores every word rect normalized to
  the padded PNG, which is what the cutter consumes. The usage block at the top of the file is
  the reference.
- **Highlight overlays render for one 500-row page of `getAnnotations` at minimum** (the API
  needs an `X-ADP-Session-Token` you can't reach). Books modestly over 500 may render ALL
  overlays (verified: 520/520 painted); big books stop at ~500. Probe empirically — where
  overlays exist they beat Step-4 arithmetic (see the word-rect matching path below); where
  they don't, extents must come from Step 4. Overlays can also paint a beat AFTER the page
  img — collect rects at capture time, not immediately post-flip, and expect the occasional
  missing/partial overlay (a per-highlight glitch, not a cap).
- Navigation: the `&location=N` URL parameter does nothing. Use the **Go-to-Page modal**
  (Reader menu → Go to Page): set the native `<input>` via the value-property setter + an
  `input` event, then click Go. Landing can be off by a page (screens ≠ print pages; one screen
  can span 2–3 print pages, and a print page can span multiple screens).
- **The table of contents jumps to a chapter by name.** Its panel is a virtual list, which lays out only the
  rows near its scroll position, so scroll `button.toc-item-button[aria-label="<chapter>"]` into view with
  `scrollIntoView()` before dispatching `mousedown`, `mouseup` and `click` on it. Then close the panel with
  `[aria-label=Close]` before sweeping, because an open panel swallows the page flips (next item).
- Page-flip: dispatch keydown **and keyup** for ArrowRight on several targets — `window`,
  `document`, `document.body`, `.kg-client-root`, `ion-app` — one target alone is unreliable,
  and the chevron `.click()` does nothing. **A leftover modal/panel silently swallows the keys**
  (a stuck Go-to-Page modal is the classic wedge; the OPEN annotations panel does it too — after
  every panel-jump, close the panel before flipping, or the flips change nothing, and after three of them the sweep stops with `why: 'end'` as if the book had
  ended; when flips die and no overlay is open, reload
  the tab and reinstall your helpers). Keyboard-independent fallback (works after Aa-panel
  interactions kill the arrows): dispatch `mousedown` + `mouseup` MouseEvents at the center of
  `[aria-label="Next page"]` / `"Previous page"` — exactly one viewport per pair. Do NOT add
  the full pointer/mouse/click 5-event sequence: it double-fires.
- **Capture without screenshots:** `fetch(blobUrl)` fails (CSP), but `drawImage` of the loaded
  `<img>` into a canvas is untainted → `canvas.toBlob` → POST to the localhost receiver. This
  yields the full-resolution page render (≈2048 px wide) regardless of OS screenshot policy.
- Density setup still applies. Snapshot `KWR_Display_Settings` first (snippet 7 in
  [scripts/reader_helpers.js](scripts/reader_helpers.js)) and restore it afterward. Apply the new
  settings with `__kh.applySettings`, not with snippet 8's Aa-panel path, which reverted on one run.
  `applySettings` sets the font index and the column count and leaves `sideMarginsSize` as it found it,
  so check that field in the first capture's JSON. Narrow is the verified layout. Settings live in
  origin-wide localStorage, so never run two extraction sessions concurrently. **Pick the font size by pixels-per-char,
  not by fewest flips**: the render width = CSS viewport width × devicePixelRatio, capped at
  2048, so px-per-char ≈ font CSS px × dpr. Vision OCR is near-perfect at ≥~17 px/char
  (fontSizeIndex 4 at dpr 1, or smallest font on a Retina/dpr-2 window) and garbles at 11
  (fontSizeIndex 0 at dpr 1). The smallest font is only correct on a dpr-2 window. A window
  WIDER than 2048 CSS px downscales the render (2560 → 2048 = 0.8×; an unresizable fullscreen
  window can force this) — bump the font to compensate: fontSizeIndex 6 (~21 px → ~17 effective)
  was verified near-perfect.
- **Two columns, not one.** In single-column mode on a 2048 px render a body line runs ~300
  characters, and Vision drops the LAST character of every full-width line (a padded canvas
  does not help). Two columns (`maxNumberColumns: 2`) give ~115-character lines and clean
  reads. The cutter orders words by column first, so columns cost nothing downstream.
  The column setting is only a maximum. On the sixth run a viewport 1344 CSS pixels wide, at font size index 4
  and device pixel ratio 1, rendered one column under `maxNumberColumns: 2`, in a page image 1076 pixels wide.
  That run tried one width at one font size, so whether width alone decides the column count is untested. Its
  lines ran to about 120 characters. Read back in one column, 347 of the notebook's 358 fully exported
  highlights matched on letters and digits, and most of the 11 misses had figure or footer text inside the span.
  So check what rendered rather than trusting the setting. A two-column page has many long lines starting past
  the middle. A one-column page can still have short lines there, such as figure labels and right-aligned
  epigraphs. `cutter.py` still splits columns by each line's centre, which can misorder a one-column page
  ([#43](https://github.com/l3a0/claude-plugins/issues/43)), so the word-rect path below still needs two columns.
- **Set the display settings through localStorage, then reload.** On one run the Aa-panel
  slider path reported the new index and then reverted when the panel closed. Writing
  `KWR_Display_Settings` directly and calling `location.reload()` is deterministic
  (`__kh.applySettings`). Record the original JSON string before touching it. Restore it the same way at
  the end. A helper re-installed after a reload does not carry the snapshot over, so keep the
  string in your own notes and pass it back explicitly. One run wrote the literal string
  `undefined` into the setting for exactly that reason.

### Word-rect matching path (preferred whenever overlays render, for any mix of truncated and hidden)

The reader's `.kg-client-highlight` rects are **word-level** (about two per OCR word). So the
cut needs no geometry arithmetic at all: OCR each capture with per-word boxes, assign every word
to the rect that contains its center, and read off the words of each token in reading order. A **token**
here is one highlight's `<start>/<end>` class on its `.kg-client-highlight` rects. It is not the notebook's
pagination token from Step 2.
The fifth run recovered 223 blocked highlights this way. Every one landed within 5 characters of its
extent and 209 of the 223 within 2. The control is the 78 highlights the notebook exported in full: reading
those back the same way agrees with Amazon's own text within 2 characters on 74 of them, which is what makes
the method trustworthy on the blocked ones. Reproduce both numbers from the app database and the finished
file, without the captures.

1. **Sweep once, continuously.** Jump to the first blocked highlight (`__kh.jump(startPos)`),
   then `__kh.sweep(1, 25)` in batches, numbering each batch's `from` past the last, polling `__kh.sweepLog` for progress
   and `__kh.sweepEnd` for each batch's end, as the full-book path's step 4 says, until the last blocked token
   has appeared and then left the screen. Budget ~5,500 characters per two-column screen at
   font index 4 (`align_extents.py` prints the estimate). One continuous sweep of ~100 screens
   beats per-cluster jumps once the blocked span covers most of the book. If the sweep has to
   resume in a new window (see the full-screen gotcha), give the new series a new prefix
   letter (`s000…` then `t000…`). The assembler merges the overlap between series fuzzily.
2. **Cut and assemble.** From the run directory:

   ```
   python3 "$SKILL/scripts/validate.py" s000 s001   # calibrate on the fully exported highlights first
   python3 "$SKILL/scripts/assemble.py"             # residual report for every blocked highlight
   python3 "$SKILL/scripts/assemble.py" --write     # completions.json
   ```

   `cutter.py` compiles `ocr_words.swift` and `crop.swift` on first use into the run directory's `bin/`,
   caches each capture's OCR, and orders words left column first. The compile needs `swiftc` from the Xcode
   Command Line Tools (`xcode-select --install`). `assemble.py` joins each token's lines across its
   captures, generates the join variants the notebook stream demands (below), and keeps the
   variant whose length is closest to the DB extent. Two OCR sources compete per highlight. One is the
   page-scale OCR. The other is a **2× re-OCR of the highlight's own band**, the horizontal strip of
   page the highlight covers (`recut`). The re-OCR earns its place because Vision silently drops whole
   body-text lines at page scale. One paragraph lost three of its lines with no error at all. Vision also
   reads the shaded Example boxes badly. The band crop must carry a **≥40 px margin**, or the first glyph
   of every line is clipped ("ortfolio", "opefully"). Ties within ±2 go to the
   text with fewer non-dictionary words. Truncated highlights are aligned on the **tail** of the
   notebook prefix, so a garbled drop cap costs nothing, and only the completion is kept. A **drop cap** is the oversized
   first letter of a chapter opener, which the page renders as its own glyph.
   The cutter repairs one more OCR failure. When the reader never painted an overlay rect for a
   line, that line stays unassigned. The gap-fill takes an unassigned body-height line that sits
   between two assigned lines of the same token. Code boxes fail its height and left-edge test.
   The extent decides whether the line stays.
3. **Read the report, then look.** `assemble.py` lists every highlight outside ±2.
   `python3 "$SKILL/scripts/inspect_highlight.py" <loc>` prints the assembled text and writes a crop of
   the highlight's page region per column to `pages/crop_<loc>_*.png`. Read the crop. The
   residuals cluster into a few causes, each with a rule the assembler already tries as a
   variant: a display-equation body inside the span, a boxed-sidebar code listing, list
   markers, a dropped or duplicated line. What the variants cannot fix goes into one of three files:

   - `fixes.json` holds a systematic slip such as `Eigure` → `Figure`, verified on a crop.
   - `loc_fixes.json` holds regex fixes that apply to one location.
   - `overrides.json` holds a hand-transcribed full text.

   Tag spans that cross a table, a figure or a display equation in `approx.json`.
   A `WARN` line from `finalize.py` means one of those patterns no longer matches. Treat it as a stop, not
   as noise: on the fifth run 16 stale patterns scrolled past and the garbled text they targeted shipped.
   `--strict` turns those warnings into a non-zero exit.
4. **Finalize and QA.**

   ```
   python3 "$SKILL/scripts/finalize.py" <out>.md --publisher Wiley --year 2013 --strict
   python3 "$SKILL/scripts/qa_words.py"
   ```

   `finalize.py` applies the per-location fixes, runs `build_notes.py`, adds the `≈ approximate`
   tags and prints the seam checks. `qa_words.py` is the sweep for the errors the extent cannot
   see: same-length substitutions (`5.Z` for `5.7`, `Ty` for `T1`), joined words from a
   dropped line-end hyphen, first-letter loss, and hidden highlights that start lowercase
   (a chapter opener's drop cap). Expect the residual table to look like the fifth run's. Most rows sit at 0 or ±1. A handful sit at
   ±3 to ±5, where the notebook's own spacing quirks ("mean( f )") make the extent disagree with the
   visible text by a few characters. Anything beyond that is a span crossing a table, a figure or a
   display equation, and those carry the `≈ approximate` tag.

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
2. **OCR locally** with the line-level [scripts/ocr.swift](scripts/ocr.swift), which emits the text
   stream the stitch step below consumes. [scripts/ocr_words.swift](scripts/ocr_words.swift) is the
   per-word-box variant the word-rect path uses, and `cutter.py` needs painted overlays, so it has
   nothing to match past the cap. Both wrap Apple Vision's `VNRecognizeTextRequest`, which is near-perfect
   on these clean renders and costs zero tokens. Keep `usesLanguageCorrection = false` for fidelity.
3. **Stitch** screens into one text stream (dedupe identical screens by md5 — missed flips
   produce duplicates; label jumps ≥4 pages signal a missed capture).
   `scripts/stitch.py` from the full-book path below does the column order and the md5 dedupe, on
   `ocr_words.swift` output rather than `ocr.swift`'s.
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

**Overlay-geometry variant. Superseded by the word-rect matching path above, kept for the
record.** Instead of sentence-boundary DP, collect per-screen overlay geometry during the sweep: for each
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

### Full-book path (the whole text, for reading the book rather than its highlights)

When the goal is the book's full text, such as to read it with an agent and draw notes from it, sweep the
book end to end and skip the cutting, which leaves Step 4's extents unused. The sixth run captured *The Art of
Scalability* this way.

1. **Set up as for any sweep.** Start the receiver, install `reader_capture.js`, and snapshot and apply the
   display settings as above.
2. **Jump to the first page of the body through the table of contents** (the gotcha above). The sixth run
   jumped to the Foreword.
3. **Sweep in one call.** `__kh.sweep(from, n, 'b')` names its captures `b<from>` on, with the number padded
   to three digits (`b003`). Never reuse a name. The receiver replaces an existing file without a word
   ([#45](https://github.com/l3a0/claude-plugins/issues/45)), so set `from` to one more than the highest
   number already in `pages/`, and capture any screen by hand under the same `b000` form. Set `n` above the
   book's screen count. The sixth run captured its first three screens, then ran `__kh.sweep(3, 700, 'b')`.
   The 493 captures, from location 487 to 13,121 of 13,134, took about 16 minutes, 12 of them on the book's
   own screens and the rest flipping past its end.
4. **Wait for the sweep to stop itself, then read why.** Past the last screen each flip leaves the image
   unchanged, so the loop stops after `__kh.END_AFTER` flips in a row that change nothing, three by default. It
   also stops when the tab goes hidden, after `__kh.stopSweep()`, or after `n` screens. Whichever it is, it posts
   `__kh.sweepLog` to the receiver as `pages/<prefix>-sweeplog.json` before it returns, and only once that post has settled sets
   `__kh.sweepEnd` to `{why, last, label}`, with `why` one of `end`, `hidden`, `stopped` or `count`. So poll
   `JSON.stringify(__kh.sweepEnd)` until it is not null, and read `why`. Anything but `end` on a full-book sweep
   means the book is not finished: `hidden` asks for the tab to be made visible and the sweep resumed under a
   new prefix, and `count` asks for a larger `n`. Check `end` too, by comparing `__kh.sweepEnd.label` with the
   book's last location or page, because three flips swallowed by an open panel or a stuck reader look the same
   as the end. A reader slower than the six-second wait for each render can do the same, and raising
   `__kh.END_AFTER` before the sweep gives it more flips. The log is cumulative within a page load, so each
   post replaces the last with a longer copy, and a new page load starts a new log under a new prefix. A log entry with an `err`, or with `changed: false` before the
   last three, marks a capture to check. Until this check existed the loop never noticed the end, and only a
   reload stopped it. The 2026-11-08 run of *The Evaluation and Optimization of Trading Strategies* reached its
   186th and last screen and kept flipping, with nothing to tell the session it had finished.
5. **Stitch.** From the run directory, with `swiftc` installed as for Step 5's other paths:

   ```
   python3 "$SKILL/scripts/stitch.py"
   ```

   It OCRs each capture once and writes one `text/<name>.txt` per screen and `book.txt`, the distinct screens
   in capture order, each headed by its footer label. It reads a screen top to bottom, and left column first
   only when at least three long lines start past the middle and make up a quarter of its long lines. On the
   sixth run's one-column render, splitting every screen at the middle instead moved short figure labels and
   epigraph lines below the body on 102 of 464 screens, and 21 fewer fully exported highlights matched. A
   line-end hyphen joins a lowercase next line. The price is that a real compound hyphen at a line end is lost.
6. **Read the stitch report for gaps.** `stitch.py` names every PNG it skipped, every missing capture number,
   and every repeated screen. It drops repeats by md5 and counts the final unbroken run of them as the flips
   past the end. The sixth run's 493 captures gave 464 distinct screens, and all 29 repeats were those flips.
   A repeat in mid-book is flagged, because a flip that landed late repeats a screen and the next flip then
   skips one. The location steps are a weaker check. On the sixth run the median step was 31 locations and the
   largest 36, but 80 steps were under 20, so one skipped screen between two short ones would still sum to a
   normal step. Capture a skipped screen under a new series letter (`c000`) rather than over an old name,
   since `cutter.py` reuses the cached OCR of a name it has already read. `stitch.py` places the new series
   after the first, so move its text into place by its footer label.
7. **Keep the text private.** `book.txt` is the whole book's copyrighted text, so it stays in the run
   directory with the captures, like extracted highlights. Keep the run directory outside any git repository,
   where one `git add -A` would stage it. Step 6's cleanup applies: restore the display settings, stop the
   receiver and close the tabs.
8. **Put locations back when the footer shows pages.** Some books' reader footer reads "Page 7 of 1054"
   instead of a location, while the highlights and every citation use locations. The gap check in step 6
   above then reads page steps instead of location steps. Each highlight is a known passage at a known location, so
   `locmap.py` finds the opening 45 letters and digits of every highlight in each screen's text, pins that
   screen to the smallest location found on it, and interpolates the screens between two pins by their order.
   A phrase the book repeats can pin an earlier screen than its own and break location order. So the script
   keeps the longest run of pins whose locations rise with their screens, prints each pin it drops, and lists
   each highlight it did not find. From the run directory:

   ```
   python3 "$SKILL/scripts/locmap.py"     # reads book.txt and pages/<ASIN>_highlights.json, writes book_loc.txt
   ```

   Each header in `book_loc.txt` gains `| Location N` on a pinned screen and `| Location ~N` on an
   interpolated one. The seventh run, *Designing Data-Intensive Applications*, showed pages. Its 588 captures
   gave 572 distinct screens. The script found 578 of the 580 highlights, pinned 231 screens and interpolated
   the other 341. Interpolation assumes the locations per screen stay even between two pins, so a citation
   from a `~` screen is approximate.

### Matching highlights to printed pages (when the full text exists)

The notebook cites by Kindle location, which a reader of the printed book cannot use. When the book's full
text exists with one header per printed page, such as `===== pdf 110 | p. 73 =====` from the owner's own
copy, [scripts/hlmap.py](scripts/hlmap.py) gives each highlight its page:

```
python3 "$SKILL/scripts/hlmap.py" book_pages.txt <ASIN>_highlights.json   # writes highlights_pages.json
```

It matches on letters and digits alone, by windows of 50, 35 and then 22 characters taken from the start, a
third of the way in and halfway in, so OCR slips and a garbled opening cost little. It leaves margin text,
the part of a page after a `[margin]` marker, out of the first pass and looks there only for a highlight the
body lacks. On 2026-11-03 the run's own matchers placed 111 of *Code Complete*'s 113 highlights and 180 of
*Rapid Development*'s 187. The misses and the wrong pages fell into three classes, and the script now handles
each one.

1. **Repeated text.** A reference recurs in a chapter's reading list and in the book's closing bibliography. A
   heading or a figure caption recurs in the table of contents or the list of figures. The run's lookup took
   the earliest copy, which put 16 of *Code Complete*'s highlights on a page their locations rule out. Sorted
   by location, the highlights must fall on pages in book order. So among a highlight's candidate pages the
   script keeps only the candidates that lie between the pages of its nearest neighbours that matched only
   once. That settled 19 on *Code Complete* and 3 on *Rapid Development*. Two on each keep several candidates
   in range. They take the first and list the rest under `also`, so the section heading "Sandwich Integration"
   reads p. 698, also p. 699.
2. **Margin text.** *Rapid Development* sets its chapter epigraphs in the margin column, which the body pass
   leaves out. The margin pass finds 4 of its 7 unmatched highlights there and marks them `"margin": true`.
   The other 3 stay unmatched.
3. **Text the print words differently.** The Kindle text of one bibliography entry carries `http://` where the
   print has none. The window from halfway in skips past it.

On the same text the script now maps all 113 *Code Complete* highlights and 184 of the 187 from *Rapid
Development*, with two ambiguous on each. A highlight hidden by the export limit has no text, so it stays
unmatched. Check every `ambiguous` and `unmatched` line it prints against the page before citing it. Each row
of `highlights_pages.json` also carries the scrape's `truncated` and `hidden` flags. The script refuses to
write over an input, and over an existing `highlights_pages.json` unless `--force` is given, because a run's
notes may cite the pages the earlier file gave.

## Step 6 — QA before declaring done

- `recovered == truncated + hidden`, `pending == 0` (build prints these).
- Seam check: for each recovered truncation, prefix + completion joins with no double space, no
  doubled word, no leftover `…` (mid-text `…` may be genuine book punctuation — check before
  "fixing"). Join with no space when the completion starts with punctuation.
- Junk sweep: no stray `«` (OCR's misread of the sidebar-close glyph), no sidebar-title fragments
  glued to span starts/ends, no mid-word cut endings.
- `### Location` section count == highlight count; file ends with exactly one newline.
- `python3 scripts/qa_words.py` clean, or every hit checked against its crop: non-dictionary
  words (inflections accepted, tickers skipped), joined words, first-letter loss, hidden
  highlights that start lowercase. The book's own typos stay. "untill", "Annoucement" and
  "p.m.. ET" were all in the printed page, so a repeated non-word is not proof of an OCR slip.
- If the run used the `osascript` fallback or `cjs.sh`, turn off Chrome's View → Developer → Allow JavaScript from Apple
  Events, and remove the terminal's Chrome entry under System Settings → Privacy & Security → Automation if it
  was granted for this run.
- Delete the run directory's `db/` copy. It holds every book's highlights for the account, not just
  this one.
- Display settings restored from the snapshot; localhost receiver stopped; your reader and
  notebook tabs closed; note that the run moves the book's furthest-read position (the user
  can decline the sync prompt on next open).

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
- **Bullet markers ("•", "■") are neither rendered in notebook text nor counted by the position
  ruler** — strip them from recovered text (extent-fit verified both ways). Numbered markers
  ("1.") are inconsistent: one run kept them in a list of short items and dropped them in a
  list of paragraph-length items, both by extent. The assembler tries both. Let the extent
  decide per highlight. Footnote digits glued after punctuation are usually absent from
  notebook text too (inconsistently) — strip for consistency.
- **What else the notebook stream omits and keeps.** Five rules, each confirmed on the fifth run by
  notebook truth or an exact residual:

  - A display equation's body is out. Its label `(3.6)` stays.
  - The equation's parenthesized annotation, such as `("State transition")`, is out. OCR may print that
    line before the label.
  - Greek rendered as an image is out. ϵ vanished from "and ϵ is a Gaussian noise". Inline Greek
    (α β γ λ μ) stays.
  - Code listings inside boxed sidebars (Example and BOX boxes) are out. Code snippets in the running
    text are in.
  - `FIGURE n.n` and `TABLE n.n` captions and `Example n.n:` titles are in.

  When a residual matches the length of a code listing or an equation line exactly, that is the rule at work.
- **Match the notebook's symbol conventions:** minus signs are `−` (never a hyphen), year ranges
  and negative test statistics use `–` or `−`, multiplication is `×`, and subscripts and
  superscripts flatten (`L1`, `T1`, `Fi`, `iQ`, `s2`). OCR reads `−` and `–` as `-`, `×` as `x`, `L1` as
  `Lz` and `T1` as `Ty`, and it turns a subscript into a comma, so `Fi` arrives as `F,`.
- **Drop caps are separate glyphs the OCR skips.** A chapter opener comes back as "ven though".
  A section opener comes back as "here are four main causes". Sweep hidden highlights that start
  lowercase and restore the letter from the crop.
- OCR clips trailing digits in dollar amounts and small caption text: sweep recovered text with
  `\$\d+\.(?=\s|$)` and re-read hits from the page image; an arithmetic cross-check often pins the
  digits (2,340 of 23.4M milliseconds ⇒ "0.01 percent"). Also watch em-dashes read as hyphens.
- **Display equations (standalone math blocks) are NOT in notebook text and NOT counted by the
  position ruler** — same class as headings and bullet markers (verified: the notebook prefix of a
  formula-spanning highlight skipped the equations entirely). OCR inserts them mid-highlight as
  garbage ("fᵢ*=mᵢ/sᵢ²" read as "2 m/s") — delete them from recovered text and let the freed
  chars extend the end cut; check the result against the page image. The label is the
  exception: a numbered equation's `(1.1)` stays in the stream (fifth run's notebook truth:
  "(using in-sample data!): (1.1) where f (i) is the ith factor"). This is the rule the "what else"
  list above points at, and a missing label is a real defect: the fifth run dropped `(8.1)` and the
  residual caught it.
- OCR flattens Greek letters (θ → "O"/"0", μ → "u") and reads zero as letter O in prose
  ("greater than O") — restore from context, using the notebook prefix's glyphs as the guide
  when the same symbol appears there.
- **Dictionary-sweep URL slugs specifically**: "your"→"vour" inside a printed URL survived every
  other QA check (word sweeps skip slug fragments); URLs are also cheap to verify externally.
