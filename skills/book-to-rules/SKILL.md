---
name: book-to-rules
description: Turn a book into rules for an engineering team and design principles for repositories, with every cited page checked against the book's text. Gets the full text, splits it into reading parts, briefs one reader agent per part, merges the notes into rules, writes them into a project repository, this plugin's role checks and board seats, and l3a0/repo-template as one pull request each, runs a review round whose verifiers refute by executing, and prices the loop. Use when asked to "adopt a book", "turn this book into rules", "read this book into the repos", or to add a book's principles to a design doc, a team charter or the plugin's agents.
---

# Book to rules

Four books went through this pipeline in two days, ending on 2026-11-03: *The Art of Scalability*, *Designing Data-Intensive Applications*, *Code Complete* and *Rapid Development*. Each run worked out the same steps again, at about 16 to 32 US dollars a book. This skill holds those steps, the scripts that check citations, the brief templates, and the checks the four review rounds taught. A later run fills in the templates and runs the checks instead of rediscovering them.

The worked examples are the four rounds of pull requests.

| Book | l3a0/ithildin-runtime | l3a0/claude-plugins | l3a0/repo-template |
| --- | --- | --- | --- |
| *The Art of Scalability* | [PR #24](https://github.com/l3a0/ithildin-runtime/pull/24) | [PR #42](https://github.com/l3a0/claude-plugins/pull/42) | none |
| *Designing Data-Intensive Applications* | [PR #25](https://github.com/l3a0/ithildin-runtime/pull/25) | [PR #46](https://github.com/l3a0/claude-plugins/pull/46) | [PR #74](https://github.com/l3a0/repo-template/pull/74) |
| *Code Complete* | [PR #26](https://github.com/l3a0/ithildin-runtime/pull/26) | [PR #47](https://github.com/l3a0/claude-plugins/pull/47) | [PR #75](https://github.com/l3a0/repo-template/pull/75) |
| *Rapid Development* | [PR #27](https://github.com/l3a0/ithildin-runtime/pull/27) | [PR #48](https://github.com/l3a0/claude-plugins/pull/48) | [PR #76](https://github.com/l3a0/repo-template/pull/76) |

Read the `## Review` comment on the *Code Complete* project pull request first. Its round is the one this skill's comment template copies.

## The book never enters a repository

All three target repositories are public, and the book is copyrighted. So the full text, the OCR output, the part files, the reader notes, the filled briefs and anything `ctx.py` prints stay in the run directory, and no tracked file or GitHub comment carries more than a short phrase of the book.

The run directory is `~/Documents/Claude/kindle/<book>/`, the same folder the `kindle-highlights` skill writes to. It sits outside every git repository, where one `git add -A` cannot stage it. A finished run holds these files.

- `book_pages.txt` (from a PDF) or `book.txt` (from the Cloud Reader), the whole text.
- `<ASIN>_highlights.json`, the owner's highlights, and `highlights_pages.json`, the same highlights with the page each was found on.
- `parts/`, one text file per reader.
- `notes/BRIEF.md`, the filled reader brief, and `notes/part<N>.md`, one reader's notes each.
- `review-brief.md`, the filled review brief.

A rule in a repository paraphrases the book and cites it. It quotes at most the book's own short phrase. Before a pull request opens, check its diff against the highlights for long shared runs of words, the way [PR #46](https://github.com/l3a0/claude-plugins/pull/46) searched for six or more words in a row shared with any highlight and found none.

## The text format the scripts read

The scripts in `scripts/` read one text file per book, cut into blocks. Each block opens with a header line, `===== <source> | <label> =====`, and the label gives the citation key.

1. **A printed page.** `===== pdf 110 | p. 73 =====` is cited as `73`. A PDF's OCR text uses this form.
2. **Front matter.** `===== pdf 3 | front 2 =====` is cited as `front2`.
3. **A Kindle location.** `===== b012 | Location 487 of 13134 ● 4% =====` is cited as `loc487` or `L487`. The `kindle-highlights` full-book path writes this form. A location falls in the last screen that starts at or before it.

Text the OCR read from a page's margin column follows the body after a `[margin]` line and stays in that page's block. A margin quote is often a highlight, so the scripts search it too.

`booktext.py` holds the loader and the matching, shared by the four scripts.

1. **`pg.py`** says whether each cited phrase is on its page. It answers OK, NEAR when the phrase is on a neighbouring page only, MISS, or NOKEY when the text has no such page. Every verdict but OK names where the phrase actually is, and the exit status is 1 when any citation is not OK. `--file cites.txt` reads one `KEY:PHRASE` per line.
2. **`ctx.py`** prints the 260 characters either side of the phrase, which is what a reviewer reads to judge whether a rule claims more than its page says.
3. **`split_parts.py`** cuts the text into one file per reader at chapter starts and prints each part's word count.
4. **`hlmap.py`** finds the page of each of the owner's highlights.

Matching folds case, curly quotes, dashes and ligatures, and joins a word hyphenated across a line end. A phrase that runs from the cited page onto the next counts as OK. Run the scripts with `python3 -I`, which keeps Python from loading a module out of the run directory. `tests/test_book_to_rules.py` runs them on a synthetic book in CI.

## The pipeline, in seven steps

1. Get the full text.
2. Split it into parts and map the highlights.
3. Brief one reader per part.
4. Merge the notes into rules, checking every citation.
5. Write the rules into the three repositories.
6. Run the review round.
7. Price the loop.

Set `SKILL` to this skill's folder first, such as `SKILL=<plugin>/skills/book-to-rules`, and `RUN` to the run directory.

### 1. Get the full text

The text comes from one of two places.

1. **A PDF the owner supplies.** The `book-text` skill in this plugin turns it into `book_pages.txt`, one block per printed page, with margin text after `[margin]`.
2. **The Kindle book alone.** The `kindle-highlights` skill extracts the owner's highlights into `<ASIN>_highlights.json`, and its full-book path sweeps the Cloud Reader into `book.txt`, one block per screen.

Get the highlights either way. They are how the owner says which points matter, and a reader marks a highlighted point `[H]`. Printed pages are the better citation where a PDF exists, because a reader of the repository can find them in a paper copy and an OCR location is good only to about one screen. When a run has only locations, write a location the text could not pin to one screen as `L\~5989`, the form [PR #25](https://github.com/l3a0/ithildin-runtime/pull/25) used.

### 2. Split the text into parts and map the highlights

Pick part boundaries at chapter starts, from the table of contents, so no reader starts mid-argument. The four runs used five to seven parts of 20,000 to 69,000 words each.

```bash
python3 -I "$SKILL/scripts/split_parts.py" "$RUN/book_pages.txt" "$RUN/parts" \
  1-part1-ch01-03=1 2-part1-ch04-05=73 3-part2-ch06-09=109
python3 -I "$SKILL/scripts/hlmap.py" "$RUN/book_pages.txt" "$RUN/<ASIN>_highlights.json" "$RUN/highlights_pages.json"
```

`split_parts.py` refuses starts out of book order and reports the front-matter blocks it left out, so give the preface a start of its own when it carries the book's argument. Read the word counts it prints, and split a part much larger than the rest. `hlmap.py` reports how many highlights it placed. On *Rapid Development* it placed 184 of 187, and a reader can still find a missed one by its text. It searches margin text too, which placed four highlights the run's first mapper missed and moved a margin quote from p. 169 to p. 126.

### 3. Brief one reader per part

Copy `templates/reader-brief.md` to `$RUN/notes/BRIEF.md` and fill it. Its hardest field is the summary of the project repository, which a reader reads every page against. Write it from that repository's `CLAUDE.md`, `docs/design.md` and `docs/team-charter.md` at `main`, and name the books its design already carries and any open pull request adding another. Then check that nothing is left unfilled.

```bash
rg -n '\{\{|<!--' "$RUN/notes/BRIEF.md"   # must print nothing
```

Launch the readers in one message, one Agent call per part, in the background. A general-purpose agent on Sonnet is enough for reading and noting. Each prompt names three things.

1. The brief, `$RUN/notes/BRIEF.md`, to read first and follow.
2. Its part file, `$RUN/parts/<part>.txt`.
3. Its notes path, `$RUN/notes/part<N>.md`.

The readers write only inside the run directory. Wait for every notice rather than polling, then read each summary and skim each notes file's caveats. The *Rapid Development* part 3 reader, for one, found that the OCR had scrambled four tables and that one highlight's page tag pointed at the wrong page.

### 4. Merge the notes into rules, checking every citation

The main thread merges. It reads every notes file, groups the candidate rules by what they protect, and keeps a rule only when it matters for the project and says something the repository's rules do not already say. Read the target repository's open issues and the owner's dated rulings on them before drafting, because a rule that contradicts a ruling is the most expensive finding a review makes.

Check every citation before it goes into a draft, not after. Write each one as `KEY:PHRASE` into a file in the run directory, and run it through `pg.py`.

```bash
python3 -I "$SKILL/scripts/pg.py" "$RUN/book_pages.txt" --file "$RUN/cites.txt"
python3 -I "$SKILL/scripts/ctx.py" "$RUN/book_pages.txt" "606:tuning"
```

Cite with a phrase of three to six words that the OCR read cleanly. A longer one can fail on OCR damage alone. On *Rapid Development* p. 126, a margin quote passed as "rare exceptions" and failed as a longer run of the same sentence, because the margin column's OCR had broken the words differently. So shorten a phrase that gets MISS before concluding the page is wrong. Fix every line that is not OK before writing the rule. Then read each rule's passage with `ctx.py` and cut any word the page does not support. The *Code Complete* review found five wrong pages after drafting, such as p. 605 for a procedure on p. 606, and two rules that claimed more than their page said. `pg.py` names the right page for the first kind, and only reading the passage catches the second.

### 5. Write the rules into the three repositories

Each repository gets its own branch and its own pull request, and each pull request body links the other two.

1. **The project repository**, such as l3a0/ithildin-runtime. Its `docs/design.md` gets a citation paragraph naming the book and how it is cited, then the rules. Its `docs/team-charter.md` gets each role's new duties and vetoes. A rule that changes a role's veto line is the owner's call, so the pull request puts it to the owner rather than making it.
2. **This plugin**, l3a0/claude-plugins. Role checks go into `scripts/gen_team.py` and board-seat failures into `scripts/gen_seats.py`, never into `agents/*.md` by hand. Regenerate with `python3 scripts/gen_team.py && python3 scripts/gen_seats.py`, and confirm with both scripts' `--check`. Bump the patch version in `.claude-plugin/plugin.json` to the next number above every open pull request's, since other sessions claim versions too. The title takes the form `feat(ask-team, ask-board): add <topic> checks from <Book> (v0.6.N)`.
3. **The template**, l3a0/repo-template. Its `docs/design.md` gets the rules that hold for any new repository, worded without the project's names.

A plugin check must hold in any repository, so word it for the property it protects and give the project's case as one example. [PR #46](https://github.com/l3a0/claude-plugins/pull/46) scoped five checks that would otherwise have fired in repositories with no such property, such as an `fsync` check against a GitHub comment.

### 6. Run the review round

Review all three pull requests in one round, under the owner's rules for reviewing a pull request. The `/l3a0:ask-team` skill describes the round, and this step adds what is particular to a book.

1. **The brief.** Fill `templates/review-brief.md` once, with all three pull requests' heads, bases and checkouts, and save it as `$RUN/review-brief.md`. Every lens and verifier gets it, so each one can check a citation with `pg.py` and `ctx.py`.
2. **The lenses.** Completeness and over-reach, plus the roles the rules touch, seated through `/l3a0:ask-team` in lens mode. Each runs blind to the others. Seven lenses ran on the *Code Complete* and *Rapid Development* rounds.
3. **The verifiers.** One per veto or group of must-fixes. Each tries to refute its finding by executing, with scripts written outside the repository. That can mean a model of the rules as written, an attack on a claimed type guard, or a copy of the repository with a limit inverted. A finding no verifier could execute is checked by the main thread running the commands. A verifier may downgrade a finding and says why.
4. **The fixes.** Apply what survived to every pull request it touches. A companion pull request that misses a fix carries the stale rule into a second repository, as [PR #74](https://github.com/l3a0/repo-template/pull/74) did with a fencing claim the other two had already withdrawn.
5. **The comment.** Post one `## Review` comment per pull request, in the form `templates/review-comment.md` gives. The project pull request carries the full review and the cost. Each companion carries the short form, which points to it.

A question that turns on the owner's judgement goes under `### For the owner`. Record the owner's answer as a dated line, first on the issue or pull request it settles, then in the document it changes. [PR #24](https://github.com/l3a0/ithildin-runtime/pull/24) recorded "2026-11-02: only the owner releases a loss stop or the kill switch once it has fired" and named the three places it went.

### 7. Price the loop

Run the `loop-cost` skill on the transcripts of every agent the run launched: the readers, the lenses and the verifiers. Report one line per loop under `### Cost` in the project pull request's review. The companions say the cost is posted there. Where the work tracks an issue, post the same lines as a `## Cost` comment on it. The *Rapid Development* round cost at least 24.34 US dollars: 9.32 for seven readers, 10.30 for seven lenses and 4.72 for three verifiers.

## Checks to run before opening the pull requests

Each check below is a finding a review made on one of the four rounds, after the pull requests were open. Run them on the drafts, and a review round has less to find.

### Citations

1. **Every cited page holds its phrase.** Run every citation through `pg.py`, and fix every line that is not OK. The *Code Complete* round found five wrong pages and *The Art of Scalability* three wrong locations, all after drafting.
2. **No rule claims more than its page.** Read each rule's passage with `ctx.py`. Reviews caught a rule that turned the book's "not so easy" into "needs a rewrite", an unsupported "most often skipped", and a rule that said "two different methods" where the page says any two ([PR #24](https://github.com/l3a0/ithildin-runtime/pull/24), [PR #26](https://github.com/l3a0/ithildin-runtime/pull/26)).
3. **A rule that goes past the book says so.** When the repository's rule is stricter than the page, or applies the book to agents where the book wrote about people, the citation paragraph says which part is the book's and which is the repository's.
4. **A figure names its source and stays in its scope.** *Rapid Development*'s survey of 300 projects supports recalibrating an estimate and nothing wider, and nobody has tested whether it fits agent loops ([PR #27](https://github.com/l3a0/ithildin-runtime/pull/27)).
5. **A claim about the book's silence is checked.** "The book never names fsync" was false, and a grep of the text would have shown it ([PR #25](https://github.com/l3a0/ithildin-runtime/pull/25)).

### Conflicts with what is already there

6. **No rule contradicts an earlier book's rule.** Read the design doc and charter whole. The *Code Complete* round found four pairs that fought, such as data stored as received against a type barrier at each adapter, and bad input failing the order path against a kill switch that lives on that path. That second pair was the round's one veto ([PR #26](https://github.com/l3a0/ithildin-runtime/pull/26)).
7. **No rule contradicts the owner's rulings or an open issue.** A first draft of [PR #25](https://github.com/l3a0/ithildin-runtime/pull/25) carried a lock design that the owner's rulings of 2026-11-01 and 2026-11-02 had already rejected. A draft of [PR #26](https://github.com/l3a0/ithildin-runtime/pull/26) carried an import rule that contradicted an open issue. Where the book and the repository disagree, the repository wins and the rule says so.
8. **A book default that the repository rejected stays out.** *Code Complete* compiles assertions out of production, which contradicts a repository that runs one build everywhere. The rule names the rejection as the repository's, not the book's.
9. **A design rule does not read as build-it-now.** The repository's 1x rule decides what is built first. The first draft of [PR #24](https://github.com/l3a0/ithildin-runtime/pull/24) read as an order to build every part at once.

### Scope

10. **A never-skip or never-drop list names each item.** A list that points to "the hard limits" misses the kill switch and the gate's limits. Name the alarms, guards, gate limits, kill switch, rollbacks, reviews and tests one by one ([PR #27](https://github.com/l3a0/ithildin-runtime/pull/27), [PR #76](https://github.com/l3a0/repo-template/pull/76)).
11. **A halt or a check covers each place it applies, and no more.** *Code Complete*'s bad-input rule first covered too little, missing reconciliation, restart and the clock, and too much, reaching data capture, which the design keeps outside every halt. Name each place the rule applies.
12. **A plugin check would not fire in an unrelated repository.** Ask of each new check whether it would flag a repository without the property. [PR #42](https://github.com/l3a0/claude-plugins/pull/42)'s off-switch check fired on every feature, and [PR #48](https://github.com/l3a0/claude-plugins/pull/48)'s spike check on every prototype.
13. **The data a rule needs exists.** A rule that asks for an estimate from past loops needs past loops with estimates. [PR #27](https://github.com/l3a0/ithildin-runtime/pull/27) found 37 `## Cost` comments and no estimate in any, so its rule starts from a labelled guess.

### Claims that only executing shows

14. **A claim that a type or a structure enforces a rule is attacked.** In Python, any module could build the acknowledgement a send was meant to require. A verifier sent four of six attacks with no journal entry, through `dataclasses.replace`, `copy.copy` and `object.__new__` among them ([PR #26](https://github.com/l3a0/ithildin-runtime/pull/26)). Write the attack before writing the claim.
15. **A claim about a system call is run.** A POSIX record lock is released when the process closes any descriptor for the file, and `flock` is not. A script showed it ([PR #46](https://github.com/l3a0/claude-plugins/pull/46)).
16. **A "done" or "releasable" rule names a check that can fail.** An inverted limit with no test passed the linter, the format check and all 75 tests in a copy of the repository ([PR #27](https://github.com/l3a0/ithildin-runtime/pull/27)).

### Every surface

17. **Generated files are regenerated.** `python3 scripts/gen_team.py --check`, `python3 scripts/gen_seats.py --check` and `sh tests/test_board_guard.sh` pass in the plugin. Counts the body states, such as "adds ten role checks", match the diff.
18. **The version is the next free one.** `gh pr list -R l3a0/claude-plugins --state open` shows what the open pull requests claim. A patch bump changes `plugin.json` alone.
19. **The template's tests still read the plugin.** l3a0/repo-template pins a plugin commit and tests each `jq` filter the plugin's skills carry. A plugin change that adds a filter needs the filter's expected output there before the pin moves ([PR #48](https://github.com/l3a0/claude-plugins/pull/48)).
20. **The markdown holds.** A tilde before a location is escaped as `L\~`, and a renumbered list keeps markdownlint's numbering rule.
