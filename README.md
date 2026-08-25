# l3a0's Claude Code plugins

[![Plugin Security Scan](https://github.com/l3a0/claude-plugins/actions/workflows/plugin-security-scan.yml/badge.svg?branch=main)](https://github.com/l3a0/claude-plugins/actions/workflows/plugin-security-scan.yml)

A personal collection of [Claude Code](https://code.claude.com) skills, published as a single
plugin under the `l3a0` namespace. This repo is both the plugin and its own marketplace.

I write about how these tools get built — and about technology, business, and finance — at
[baowebdev.substack.com](https://baowebdev.substack.com).

## Install

```bash
claude plugin marketplace add l3a0/claude-plugins
claude plugin install l3a0@l3a0
```

Skills are invoked as `/l3a0:<skill-name>` (the bare `/<skill-name>` also works while no other
installed command claims the name), and Claude auto-invokes them when a request matches a
skill's description.

## Skills

### kindle-highlights

Export a heavily-highlighted book from Amazon's notebook page and some highlights come back
cut off mid-sentence, while others come back as a bare location number with no text at all,
under this notice:

> "Some highlights have been hidden or truncated due to export limits."

Those are your own notes, in your own account, capped by a budget Amazon doesn't document and
you can't raise. This skill gets them back: it extracts every highlight for a book from the
Kindle notebook (`read.amazon.com/notebook`) into one combined, **verbatim, location-cited**
Markdown file — including the highlights the export limit truncates or hides entirely, which
are recovered from the Mac Kindle app's synced annotation positions plus the Cloud Reader's
rendered pages.

Proven on four real books: **2,432 highlights extracted, 815 of them export-blocked (454
truncated + 361 fully hidden) — every one recovered**, with recovered text landing within a
couple of characters of the Kindle app's own position ruler (median residual 0–1). Every
gotcha in the skill was earned by real debugging across those runs.
The build story — why the export limit exists, the three unlocks that beat it, and what a
library of exports becomes — is written up in
[How to Take Back Your Kindle Highlights](blog/how-to-take-back-your-kindle-highlights.md),
also published on [Substack](https://baowebdev.substack.com/p/how-to-take-back-your-kindle-highlights).

**Scope:** this exports *your own* highlights from *your own* Amazon account, by driving your
own logged-in browser session and reading files the Kindle app stores on your Mac. The output
is for your personal notes — book text is copyrighted, so keep extracted notes private.

#### Prerequisites (macOS only)

The pipeline is macOS-only three times over: browser control runs over AppleScript, OCR uses
Apple's Vision framework, and highlight positions come from the Mac Kindle app's data files.

1. **Claude Desktop with the "Control Chrome" extension** — Anthropic's browser-control MCP,
   installed in one click from Claude Desktop → Settings → Extensions. It is the skill's
   verified path for executing JavaScript in your real Chrome (any browser MCP that can run JS
   in the tab can substitute). It requires a Chrome setting:
   Chrome menu bar → View → Developer → **Allow JavaScript from Apple Events** → check →
   quit and relaunch Chrome.
2. **Google Chrome**, signed in to your Amazon account (the skill drives
   `read.amazon.com`).
3. **The current Mac Kindle app** (App Store; bundle id `com.amazon.Lassen` — not the classic
   Kindle.app), signed in to the same Amazon account, with the book downloaded. Its synced
   annotation database provides exact highlight extents with no export limit.
4. **Xcode Command Line Tools** (`xcode-select --install`) — the bulk-recovery path compiles a
   small Swift OCR helper (`swiftc`) that uses Apple Vision.
5. **python3** — builds the final Markdown and runs a localhost receiver
   (`127.0.0.1:8931`) that the reader page POSTs captures to.

#### What it does, briefly

1. Scrapes all highlights from the notebook page DOM to JSON (verbatim typography preserved).
2. Reads exact character-precise highlight positions from the Kindle app's SQLite database —
   including highlights the web export hides completely.
3. For blocked text, captures the Cloud Reader's rendered pages via canvas (no OS screenshots
   needed), OCRs them locally with Apple Vision (zero tokens), and cuts the text to the known
   positions.
4. Emits one Markdown file with `### Location N` sections, blockquoted verbatim text, and
   flags for anything recovered or approximate, then runs a QA pass.

## License

[MIT](LICENSE)
