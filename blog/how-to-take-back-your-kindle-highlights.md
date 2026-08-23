# How to Take Back Your Kindle Highlights

*Subtitle: Your notes, your books, your data.*

*(Title and subtitle go in Substack's fields; body starts below.)*

---

## Why?

I highlighted 1,211 passages in one book. When I exported them from Amazon's notebook page, 283 came back cut off mid-sentence and 180 came back with no text at all: a location number, and a notice that "some highlights have been hidden or truncated due to export limits."

Those highlights are my personal data. I chose every passage. I bought the book. The selections exist because I did the reading, and they sync through my account. Amazon doesn't document the limit; the conventional explanation is a publisher-set clipping allowance, a per-book budget on how much text can leave as excerpts. Whatever the reason, the effect is that a slice of my own notes sits behind a cap I never agreed to and can't raise.

My test for personal data is simple: if it wouldn't exist without you, you should be able to take it with you. Highlights pass that test. This post is the build log of getting mine out — all 1,211, verbatim, with locations.

## What?

A skill is a playbook for an AI agent — a Markdown file of instructions plus a few scripts, earned the hard way once, reusable after that. This one exports every highlight in a book to a single Markdown file, each entry quoted verbatim under its location. It runs in [Claude Code](https://code.claude.com), which drives the browser and the scripts; the sections below are what the playbook encodes. It's packaged as an installable plugin at [github.com/l3a0/claude-plugins](https://github.com/l3a0/claude-plugins).

Model and effort, since the git history keeps the receipts: Claude Opus 4.8 drove the bulk recovery run, and a later Claude Fable 5 session did the packaging (each session co-signs its commits, so the attribution is on the record). The model spends its effort where judgment lives — deciding where an ambiguous highlight ends, spotting a table that garbled the OCR, checking seams. The volume work runs in local scripts, and the playbook deliberately keeps book text out of the model's context: captures and OCR happen on-device, and scraped data leaves the browser as a file instead of flowing through the conversation.

Three unlocks made it work:

- The exact position of every highlight lives in a database on my own Mac.
- The web reader's pages can be captured as images and read with free, on-device OCR.
- Known positions turn recovery from transcription into arithmetic.

## How to hit the export limit?

The notebook page at read.amazon.com/notebook lists every highlight in a book, and a short script run in the browser scrapes them all. Most rows carry full verbatim text, curly quotes and em-dashes intact.

Then the budget runs out. Past some threshold, rows keep their location but lose their tail, ending in an ellipsis. Further past it, rows lose their text entirely. A heavily marked-up 600-page book produced the 283-and-180 split above; a lighter one (466 highlights) lost only 41 tails.

The clipping happens on Amazon's servers, so no amount of scraping harder helps. The full text exists in one reachable place: the reading apps themselves.

## How to fail at recovering it?

Four dead ends, recorded so you can skip them:

- Screenshotting each clipped highlight and transcribing the marked span works. That was the entire first run, 41 recoveries, and it does not scale to 463.
- The web reader paints highlight overlays for only the first 500 annotations in a book. Past 500 there is no overlay on the page at all.
- The reader's `location=` URL parameter does nothing. Navigation happens through the Go-to-Page dialog or the arrow keys.
- Downloading scraped data from a background tab silently fails, and Chrome blocks a second automatic download from the same page. A tiny local web server the page can POST to turned out to be the only reliable exit.

## How to find the exact positions?

The Mac Kindle app syncs the exact start and end position of every highlight: character-precise, hidden ones included, no export limit anywhere. It stores them in a SQLite database inside the app's data folder (`ksdk_annotation_v1.db`), one small JSON payload per annotation.

Open the book once so the app syncs, then read the table with any SQLite client. Sorted by position, its rows line up one-to-one with the scraped notebook rows sorted by location. As a check: end minus start plus one matched the visible text length within two characters on all 748 unclipped highlights.

Knowing exact extents changes the problem. Amazon's export hides text, but the coordinates of every highlight were sitting on my laptop the whole time.

## How to read pages nobody will hand you?

The web reader renders each page as a picture: an image backed by a browser blob, with no text layer underneath. Nothing to select, nothing to copy. The gap in the wall is that a script inside the page can draw that image onto a canvas and POST the pixels to the local receiver, yielding a clean book-page render about 2,048 pixels wide.

Set the reader to its smallest font and narrowest margins so each screen carries the most text, then sweep: flip, wait two seconds, capture, repeat. Between 150 and 250 screens covered the half of the book where the blocked highlights lived.

OCR runs locally through Apple's Vision framework, a 40-line Swift program. On renders this clean its output is near-perfect, and language correction stays off so the software can't "fix" the author's wording. The cost is zero: no cloud API, no tokens, nothing leaving the machine.

## How to cut text by arithmetic?

Stitch the OCR output into one long stream, then cut it with the position table.

A truncated highlight already has its verbatim opening from the scrape. Find that prefix in the stream and cut at the known length. A hidden highlight has no prefix, but it has a length and a gap to its neighbors, and highlighting habits are regular: in this book, 97 percent of highlights start at a capital letter and 99 percent end at sentence punctuation. Aligning sentence boundaries to the measured lengths pins nearly every span, and the few leftovers get checked against the page images by eye.

Two corrections mattered. Section headings appear on the page but are skipped by the position ruler, so a span that crosses one needs the heading's length added back. And a highlight that runs through a table has no faithful linear form; those get reconstructed in reading order and tagged approximate.

The finish line is mechanical: recovered count equals blocked count, every seam joins cleanly, and every location section in the output file matches a scraped row.

## How to install and use it?

Two commands install the plugin:

```
claude plugin marketplace add l3a0/claude-plugins
claude plugin install l3a0@l3a0
```

Then open Claude Code and ask for your highlights; "export my Kindle highlights for this book" is enough to trigger the skill. Sign into read.amazon.com in your own Chrome, let the agent run the playbook, and the result is one Markdown file: every highlight quoted verbatim under its location heading, flagged wherever a recovery is approximate. The [README](https://github.com/l3a0/claude-plugins) lists the prerequisites in full; the short version is a Mac with Chrome, the current Kindle app, and Apple's developer command line tools.

## How to put the output to work?

The file is built for further use, and its most natural reader is another model. It holds your own distillation of the book — the passages you judged worth keeping, verbatim and in reading order — so anything an LLM builds from it stays anchored to your judgment rather than to a generic summary of the whole text.

Drop the file into a session and ask for a study guide, a lesson plan for teaching the material, a spaced-repetition deck, or an outline of the book's argument; the location citations let every generated claim point back to its source passage. Two books' files in one conversation become a comparison of how different authors treat the same topic.

The files also compound. Each export adds another location-cited slice of what I read and judged worth keeping, and together they form a knowledge base that works like a digital twin of my reading: ask it a question, and the answer comes back in passages I once chose myself. Memory with a query interface.

Philosophy got here first. Andy Clark and David Chalmers argued in ["The Extended Mind"](https://www.jstor.org/stable/3328150) (1998) that a notebook you consult reliably enough functions as part of your memory, and Clark later described humans as natural-born cyborgs for exactly this habit of building cognition out of external parts. A stack of highlight exports makes the idea concrete: my brain did the selecting, the files do the retaining, and a model does the recalling.

Every word I recovered was already mine: chosen by my hand, stored on my machine, synced under my account. Getting it back took an agent, a database, an OCR pass, and some arithmetic. The right to the words should have needed none of it.

If you run it on your own library, I'd like to hear what it finds. Reply and tell me, or subscribe to follow the next build.
