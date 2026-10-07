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

Proven on five real books: **2,733 highlights extracted, 1,038 of them export-blocked (537
truncated + 501 fully hidden) — every one recovered**, with recovered text landing within a
couple of characters of the Kindle app's own position ruler (median residual 0–1). Every
gotcha in the skill was earned by real debugging across those runs. The fifth run turned the recovery
into scripts. They read each highlight's known character length from the Kindle app, sweep the reader,
match recognized words to the reader's own highlight overlays, and check every recovered span against
that length.
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
4. **Xcode Command Line Tools** (`xcode-select --install`) — the recovery path compiles two small
   Swift helpers with `swiftc` on first use: an Apple Vision text pass and a CoreGraphics band crop.
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

### ask-board

One model answering a strategic question blends every concern into one voice, so the places where the concerns disagree never surface. This skill gives a sole operator a board of directors instead. Each director is a separate agent with its own objective, and none of them sees the others' first answers. The disagreement reaches the CEO as a split with the metric that decides it.

Ask a question such as "I want to start a quant trading shop with my own money. Should a working strategy come first?" The main thread chairs a sitting in seven steps.

1. **Intake.** It sets aside the CEO's own hypothesis in a file only the chair reads, and rewrites the question as an open choice among labelled options, at least two of them not the hypothesis. It loads the company brief, the recent minutes and every past decision, so a rejected plan does not come back without new evidence. It asks for any of four brief fields still blank.
2. **Seating.** It picks four to six seats the decision needs. The independent director sits every time. When the skill started on its own, it asks once before convening.
3. **Blind round.** The seated directors write memos in parallel without knowing which option the CEO favors, so none of them anchors on it. Each memo carries a pre-mortem, a base rate, and every factual claim tagged VERIFIED with a source or ASSUMED.
4. **Cross-examination or a rival plan.** When the memos disagree on which option comes first, seats from each side and the independent director learn which option the CEO favors, then rebut. A seat may change its verdict only by naming a new fact or a flaw in its own memo. When the memos all agree, the independent director builds the strongest rival plan instead.
5. **Fact check.** The chair spends about ten lookups, base rates first, then the assumed rules, thresholds and costs the advice rests on. Anything unchecked stays ASSUMED.
6. **Blind draft.** A secretary agent with no tools, which never learns the CEO's preference, drafts the synthesis and weighs each split by its arguments rather than by headcount.
7. **Minutes.** The chair adds the verdict count, a table of each seat's blind and final verdicts that flags any change made without a reason, and the decision with its status: adopted, rejected or deferred.

The board has nine seats. All of them run on the same model, so each charter names what the seat optimizes, what it will sacrifice, and the question it always asks.

1. **Chief Financial Officer** (`board-cfo`) asks whether the plan beats an index fund after costs and the CEO's time.
2. **Chief Risk Officer** (`board-risk`) asks what the maximum loss is and what stops trading when it hits.
3. **Chief Scientist** (`board-scientist`) asks what out-of-sample evidence exists and how many variants were tried.
4. **Chief Technology Officer** (`board-cto`) asks whether the live path reproduces the backtest number.
5. **Chief Operating Officer** (`board-coo`) asks what happens when the CEO is sick for a week or the broker API is down.
6. **Chief Information Security Officer** (`board-ciso`) asks where the broker keys live and who can withdraw.
7. **General Counsel and Tax** (`board-counsel`) asks which rules a choice touches and which of them has a deadline.
8. **Strategist** (`board-strategist`) asks who is on the other side of the trade and why they lose.
9. **Independent Director** (`board-independent`) asks what would have to be true for the opposite plan to win.

A tenth agent, the secretary (`board-secretary`), holds no seat and drafts the synthesis. Trading is the worked example in every charter, and the seats apply to any one-person venture.

No agent can write a file or run a shell command. The seats can read and search files, and only the finance, science, counsel and strategy seats can search the web. Read access still reaches any file the user can open, so keeping a seat to the brief and the minutes is an instruction in its charter, not a tool limit.

**The directors remember past sittings through the chair.** The chair keeps one record per seat at `~/.config/board/memory/<seat>.md`, pastes it into that seat's prompt, and alone appends to it after each sitting. A record lists the seat's positions, its predictions with a date to check them, and what the CEO decided. It holds no hypothesis, account numbers, credentials or balances. Read or prune any record by editing that file.

Invoke it as `/l3a0:ask-board`, or ask "what would my board say about this". A sitting costs six to ten agent runs on the session's model.

**Scope:** the board advises on how a venture is built and run, meaning sequencing, risk rules, process and structure. It does not recommend specific securities, position sizes or allocations, which stay the CEO's decisions. The counsel seat is not legal or tax advice and says when a licensed professional is needed. The brief, the minutes, the seat records and the chair's hypothesis files hold personal finances, so they live in `~/.config/board/` and never in a repository.

## License

[MIT](LICENSE)
