---
name: update-build-board
description: Keep a repository's build board true by setting, on GitHub, the labels, links and lines it reads. Run it when a plan or decompose loop starts or exits, when a build session starts on a card or hands its pull request over, when a review is posted, when an issue is filed, gains or loses a sub-issue, or its priority, its ranking or what it waits on changes, and when the board's page, generator or pinned version changes. It covers the working:build and working:decompose labels, the band:N labels, the "Board verdict:" comment line, the "Board order:" and "Board after:" body lines, and the review heading the board reads. A GitHub Action rebuilds the board from GitHub on every change, so nothing here writes the board itself. Answering what to take next is a read of the board's board.json.
---

# Update the build board

The build board is a page answering what is in flight and what to take next. Each open issue appears on it as a card. A GitHub Action rebuilds the page's data from GitHub on every issue, comment and pull request change and on a schedule, and no Claude runs at any step.

So a session never writes the board. What a session does is set the judgement the board reads, on GitHub: a label, a native "blocked by" link, a line in an issue body, or a line in a comment. The facts GitHub already records, such as a pull request opening, its checks settling or an issue closing, reach the board with nothing set by anyone. A session that reaches one of the moments below and sets nothing leaves the board wrong, and nothing else notices.

This skill is the union of four copies that had drifted apart, each read at its repository's `main`, and [l3a0/claude-plugins#28](https://github.com/l3a0/claude-plugins/issues/28) carries the inventory that maps every capability of each copy to a section here.

1. `.claude/skills/update-build-board/SKILL.md` in l3a0/quantitative-trading at `0237abf`, the original, written for that repository's own generator.
2. The same file in l3a0/repo-template at `9c6d7e2`, generalised for the shared reusable workflow.
3. The same file in l3a0/ithildin-runtime at `3c2242c`, the template's copy at `4bb3f7f` with an `## In this repository` section.
4. `.claude/skills/board-markers/SKILL.md` in l3a0/marketlake at `16666cb`, which states the same markers and moments for that repository's own generator.

Three files beside this one hold what a session needs only some of the time.

- [page.md](page.md) says what the page is made of, how to change the page or a generator, and how to verify a change by running the page.
- [record.md](record.md) is the record of what has gone wrong on the page, and the offer of a task per idle card that was tried and withdrawn.
- The `sync-prune-next` skill in this plugin runs the status round that reads the board and reports what a session left unset.

## Which board this repository runs

Three setups exist, and they differ in where the generator lives, which labels and lines it reads, and what the page draws. Find the setup before setting anything, because a format one generator reads can mean nothing to another.

| Setup | Repositories | Generator | Page source |
| --- | --- | --- | --- |
| Shared reusable workflow | l3a0/repo-template, l3a0/ithildin-runtime, and any repository seeded from the template | `scripts/build_board.py` in l3a0/repo-template, at the ref the caller pins | `.claude/skills/update-build-board/board.html` in l3a0/repo-template |
| Own generator, `scripts/` | l3a0/quantitative-trading | `scripts/build_board.py` in the repository | `.claude/skills/update-build-board/board.html` in the repository |
| Own generator, beside the sync skill | l3a0/marketlake | `.claude/skills/sync-prune-next/build_board.py` in the repository | `.claude/skills/sync-prune-next/board.html` in the repository |

Run this from the repository root to find the setup. Each Bash tool call starts a new shell, so run these lines in the same call as any command below that uses `$REPO`, `$BOARD`, `$GEN` or `template`.

```bash
REPO="$(gh repo view --json nameWithOwner --jq .nameWithOwner)"
PIN="$(sed -nE 's#^ *uses: l3a0/repo-template/\.github/workflows/build-board\.yml@([^ ]+).*#\1#p' .github/workflows/board.yml)"
template() { gh api "repos/l3a0/repo-template/contents/$1?ref=$PIN" -H "Accept: application/vnd.github.raw"; }
if [ -n "$PIN" ]; then BOARD=shared
elif [ -f scripts/build_board.py ]; then BOARD=own GEN=scripts/build_board.py
elif [ -f .claude/skills/sync-prune-next/build_board.py ]; then BOARD=own GEN=.claude/skills/sync-prune-next/build_board.py
else BOARD=none
fi
echo "$REPO board=$BOARD pin=${PIN:-none} generator=${GEN:-template}"
```

Check that `$PIN` is not empty before trusting anything `template` returns, because an empty pin means the `uses:` line did not match. l3a0/quantitative-trading, l3a0/repo-template and l3a0/marketlake keep the page, the stub and the icon inside their skill folders, and marketlake keeps its generator there too. Each one's board workflow publishes the page and the icon from there, the shared workflow serving the template's page to every caller, and the template's icon unless the caller names its own, and each one's tests run the stub. So a repository that drops its own copy of this skill deletes only `SKILL.md` and keeps those files. `board=none` means the repository has no board this skill knows, so stop and report it. A repository that moves its page or its generator to a path this block does not test updates the block in a plugin release, per the next section.

## Generator compatibility

The skill and each generator share formats: the label names, the comment and body lines, the review heading, and the list of changes that start no run. A repository pins its generator to one commit, while this skill moves whenever the plugin updates. [l3a0/repo-template#24](https://github.com/l3a0/repo-template/issues/24) kept the skill as a per-repository file for exactly that reason, and the owner asked on 2026-10-29 UTC to move it into the plugin anyway. The price is that a plugin update and a generator change can land apart, so this table names what the formats here were checked against.

| Repository | Generator file | Formats match at | Repository `main` read at |
| --- | --- | --- | --- |
| l3a0/quantitative-trading | `scripts/build_board.py` | `d5876470cd7ecbefbc3b207f8e185543f6eea1ed` | `0237abf` |
| l3a0/repo-template | `scripts/build_board.py` | `4bb3f7f301300ed3f86a4992e6792fba3f7d3ed7`, unchanged at `9c6d7e2` | `9c6d7e2` |
| l3a0/ithildin-runtime | the template's, pinned at `4bb3f7f301300ed3f86a4992e6792fba3f7d3ed7` | the same commit | `3c2242c` |
| l3a0/marketlake | `.claude/skills/sync-prune-next/build_board.py` | `ea7a6a20afdd27bf125c51378b1b7e37e1dc7404` | `16666cb` |

The template's `icon` input on the reusable workflow arrived at `9c6d7e2`, after the generator's last change, so it needs a pin at or after `9c6d7e2` even though the generator formats did not move.

Three rules keep the two in step.

1. **A repository on a generator commit this table does not name follows its generator, not this skill.** The generator is what the board reads. So before setting a format, read the generator at the commit the repository runs: `template scripts/build_board.py` for the shared setup, or `git show HEAD:"$GEN"` for an own generator. Grep it for `re.compile` and `KIND_LABELS`. Where it disagrees with this skill, set what the generator reads, and report the disagreement, so the owner can move the pin or release the plugin.
2. **A format change to any generator ships with a plugin release in the same step.** The pull request that changes what a generator reads also opens a pull request on l3a0/claude-plugins that updates this skill and this table and bumps the plugin's version. Neither merges without the other, because a generator merged alone leaves every session following the old rules on the new board.
3. **Moving a pin is a format change when the generator moved between the two commits.** Compare the two commits with `git diff <old>..<new> -- scripts/build_board.py` in l3a0/repo-template before moving the pin, and treat any change to a regex, a label list or a query field as rule 2.

Two repositories have tests that read this skill's text from their own copy. They pin these strings, so the strings stay here verbatim for a test that is repointed at this file.

1. `test_the_skill_quotes_the_allowance_the_script_adds` in both repositories asserts the phrase "a 600-minute allowance".
2. l3a0/repo-template's tests assert the `PIN=` line above, the line `gh workflow run board.yml --repo "$REPO"` on its own with no `--ref` after it, the text `` `with: icon: <path>` ``, and that every numbered moment under `## What a session sets, and when` naming a "blocked by" link or a sub-issue says "dispatch the board".
3. l3a0/quantitative-trading's test asserts the same moments rule, and the line `gh workflow run board.yml --repo l3a0/quantitative-trading` on its own, which `## In each repository` below carries.

## Where the board lives

| What | Shared reusable workflow | Own generator |
| --- | --- | --- |
| The page | `https://<owner>.github.io/<name>/` | the same |
| Its data | `board.json` beside the page | the same |
| The caller | `.github/workflows/board.yml` in this repository | `.github/workflows/board.yml`, which also runs the generator and deploys |
| The build and deploy jobs | `.github/workflows/build-board.yml` in l3a0/repo-template, at the ref the caller pins | the repository's own `board.yml` |
| What builds the data | `scripts/build_board.py` in l3a0/repo-template | `$GEN` in the repository |
| The page's source | `.claude/skills/update-build-board/board.html` in l3a0/repo-template | `board.html` beside `$GEN`'s skill folder, as the setup table says |
| The page's tab icon and test stub | `favicon.ico` and `dom-stub.js` beside that page, unless the caller names its own icon | `favicon.ico` and `dom-stub.js` beside the page |

Each page's address is public and the same for every machine, so it lives here rather than in a file on the machine.

**In the shared setup the caller is short.** It holds the triggers, the `permissions`, and `concurrency: group: pages`, which makes runs deploy one at a time so an older snapshot never replaces a newer one. Its one job is `uses: l3a0/repo-template/.github/workflows/build-board.yml@<ref>`. In l3a0/repo-template itself the ref is `main`. A seeded repository pins a full commit SHA, so its board changes only when that repository moves the pin. The called workflow checks out the generator and the page from the template at its own commit, which it reads from `job.workflow_repository` and `job.workflow_sha`. Inside a called workflow the `github` context still describes the caller, so `github.workflow_sha` would name the wrong commit. It also checks out the caller's `.github/workflows/board.yml`, because the generator reads the schedule from it, and the file the caller's `icon` input names, when it names one. A seeded repository keeps no copy of the generator or the page, so every command here that runs either fetches it with `template`.

**A change reaches the page once a run of the Action finishes.** A label, a body edit and a comment each start a run, so the page changes within a few minutes. A "blocked by" link and a sub-issue start none, because GitHub Actions lists no trigger for either, and neither does a submitted pull request review. So the session that makes a link or a sub-issue dispatches the board itself once its changes are in, using the `gh` login it made them with. The moments below say where.

```bash
gh workflow run board.yml --repo "$REPO"
```

The dispatch runs on the default branch. Never pass `--ref`. The `github-pages` environment lets only `main` deploy, so GitHub refuses the deploy of a run from any other branch. The environment has a branch policy and no required reviewers, so a dispatch approves nothing. `gh workflow run` may ask for permission, because no allow rule covers it in some repositories, and a round says so in its report when it does.

The triggers, in every setup, are these.

1. `issues`, for any change to an issue.
2. `issue_comment`, for any comment.
3. `pull_request_target` into `main`, with the types `opened`, `synchronize`, `reopened`, `closed` and `edited`. Without `closed` a merged pull request that closes nothing would read as open until the next run, and without `edited` so would a corrected closing link.
4. `workflow_run` of `CI`, which is the only event that fires when the checks settle. In l3a0/marketlake it also names `Infra`.
5. `schedule`, with a `cron` line of two slots an hour, such as `8,38 * * * *`.
6. `workflow_dispatch`, for the command above.

**The `cron` line is a backstop that nothing can rely on.** It catches a change made with a workflow's own token, which starts no run, and a dispatch a session forgot. GitHub delays a scheduled run under load or drops it, and its documentation bounds neither. In l3a0/quantitative-trading, after the line moved to `8,38`, it fired in about 11% of its slots over the next 185 hours, with up to 603 minutes between two runs, which [l3a0/quantitative-trading#587](https://github.com/l3a0/quantitative-trading/issues/587) measured. In l3a0/marketlake it fired none of its first four due slots on 2026-10-12. Pages also tells a browser to cache `board.json` for ten minutes, and the page asks for a fresh copy every two minutes to get round it.

**To read the board, build it from GitHub rather than fetching the published copy**, because the build reads GitHub as it stands rather than as the last run saw it. Run it from the repository root, after the setup block, with a scratch directory as the output, never the repository. Remove any `board.json` an earlier build left there first, because a failed build writes no new one and a reader would take the old file as current.

```bash
rm -f <scratch>/board.json
if [ "$BOARD" = shared ]; then
  template scripts/build_board.py > <scratch>/build_board.py &&
  uv run --no-project --python '>=3.12' <scratch>/build_board.py build --repo "$REPO" --workflow .github/workflows/board.yml --out <scratch>
elif [ "$GEN" = scripts/build_board.py ]; then
  uv run --no-project --python '>=3.12' "$GEN" build --repo "$REPO" --workflow .github/workflows/board.yml --out <scratch>
else
  uv run python "$GEN" build --repo "$REPO" --out <scratch>
fi
```

Every generator needs Python 3.12 or later, and a bare `python3` can be an older one, such as the 3.9 at `/usr/bin/python3` on macOS, which fails on import. `uv run --python '>=3.12'` finds or fetches a version that works, and `--no-project` is safe because the shared and l3a0/quantitative-trading generators import only the standard library. l3a0/quantitative-trading's own copy of this skill ran its generator as `python3 scripts/build_board.py`, which works where `python3` is 3.12 or later. l3a0/marketlake's generator runs under the repository's own environment with `uv run python`, never `python3`.

Each build prints what it read to the terminal, including a summary table of what the read cost in GraphQL requests and points and what it found in the markers sessions set, and writes `<scratch>/board.json`. A run that fails says why, exits non-zero and writes nothing, because the generator stops on any read it cannot trust rather than writing a board that reads as correct.

## What a session sets, and when

Each moment below is one where the page's answer changes and nothing GitHub records on its own says so. `<n>` is the card's issue and `<b>` the issue it waits on.

1. **A decompose loop starts.** Add `working:decompose` to the issue. A `working:` label already on the issue is no lock. Check it against the stale-label rule in step 3 of the `sync-prune-next` skill, and ask the session that owns it before taking over. Each pass gets its own comment headed `## Plan audit, pass N`. l3a0/marketlake's generator counts these headings to find a loop that exited without a verdict, and does not count a combined heading such as `## Plan audit, passes 7 and 8`. A later loop on the same issue continues the numbering, and its verdict counts its own passes.
2. **A decompose loop exits.** Post the verdict as a comment carrying one line in this form, alone on its line, then take `working:decompose` off.

   ```text
   Board verdict: build after 5 passes
   ```

   `build` means the plan is ready for a builder. Write `decide` in place of `build` when the loop ended on a question only the owner can answer, and name the question in the same comment, because a status round lists the card and not the question. Once the owner answers, a loop posts a fresh verdict, because an answer carries no verdict line and without one the card reads "waits on an owner call" forever. The newest verdict wins, so a loop run again writes a new one rather than editing the old. A loop with passes and no exit writes no verdict, because the card's plan marker means the loop exited. In the same step, post the loop's cost as a separate comment starting with the line `## Cost`, under the owner's rule on posting cost on the issue.
3. **A build session starts on a card.** Add `working:build` to the issue, after the same check as a decompose loop. It stays after the pull request opens, because until the hand-over it is the only thing on the page saying the branch is still moving. If the label does not exist yet, `gh issue edit` fails. Report that and carry on. Never run `gh label create`, because creating labels is the owner's, or the template's `scripts/setup-repo.sh` in a seeded repository.
4. **A session hands its pull request over.** That means the review is posted under the heading moment 5 names, its fixes are pushed, the checks are green at the current head, and nothing more is coming. Take `working:build` off then, not when the pull request opens. Until then the label keeps the card under "Waiting on my review" and out of the owner's "Waiting on your review" column, whatever its review and checks say, which is its job while the review runs. In the same step, post the build's and the review's cost on the issue as a comment starting with the line `## Cost`.

   A `Part of` pull request leaves its issue open. Once it merges, the card drops back to "Planned, no builder" with its old verdict reading "ready to build", because the In flight section counts only open pull requests. So that hand-over also settles the verdict for the remainder. A build session runs no plan passes of its own, so it does one of two things.

   - If the remainder already has a plan that still holds, post `Board verdict: build after N passes`, with N that plan's pass count.
   - If it does not, edit the comment carrying the old verdict and remove its `Board verdict:` line, so the card stops reading ready. Sessions act as the owner, so they can edit the owner's comment.

   A verdict is otherwise withdrawn only by a newer one, or by editing or deleting its comment.
5. **A review lands on a pull request.** Post it as a pull request comment whose first line is the heading the repository's generator reads. Under l3a0/marketlake's generator a submitted review counts too, and under the other two it does not, because their query reads only the pull request's comments. A review headed anything else counts as none, and its card sits in "Waiting on my review" until somebody notices.

   - **Shared and l3a0/quantitative-trading generators** read an owner's pull request comment, never a submitted review, whose body, after leading whitespace, opens with `## Review` followed by a word boundary. `## Reviewer` is not one. Without one, the card's `review` reads "review in progress" while it carries a `working:` label, and "no review posted" otherwise.
   - **l3a0/marketlake's generator** reads only a comment or review whose whole first line is `## Review complete`, posted by the owner after the head commit's `committedDate`. A heading that only starts with those words, like `## Review completeness check`, does not count, and neither does a marker from an earlier round, because the commits pushed since then are code that review never saw. A session can post some lenses' results while another lens still runs, so a partial review stays headed something else. Any review comment was once enough there, and that sent [l3a0/marketlake PR #713](https://github.com/l3a0/marketlake/pull/713) to the owner while its mutation lens was still running. That repository's `CLAUDE.md`, under "Pull requests", is where review sessions read the rule for writing the heading.

   A final pull request comment whose first line is `## Review complete`, posted after the last push, satisfies all three generators, so it is the form to use where a session cannot tell which one runs.
6. **An issue is filed.** Add a label the board reads for the card's `kind` where one applies. The shared generator reads `deferred` and `decision`. l3a0/quantitative-trading's reads those and `blocked-on-data`. l3a0/marketlake's reads only `deferred`. These are separate from the label a repository's `CLAUDE.md` asks every filed issue for, saying what kind of work it is, such as `bug` or `documentation`. The card prints that one among its labels and decides nothing by it. Under the shared and l3a0/quantitative-trading generators, add a `band:N` label if the card joins the priority order, because a card with no band is left out of the board's default view. l3a0/marketlake has no `band:N` labels, and its `Board order:` line alone ranks a card. Add a native "blocked by" link for each open issue the card cannot start before, and a `Board after:` line for an ordering nothing enforces. If it set any link, dispatch the board once everything is set, because a link starts no run.
7. **A card's priority or ordering changes.** Move its `band:N` label, where the generator reads one, and add, change or remove its `Board order:` line. Add, change or remove its `Board after:` line when an ordering nothing enforces changes. Under l3a0/marketlake's generator, once any card in a milestone that is not deferred carries an order, the page hides that milestone's unranked cards behind "Show all". So rank a milestone's open issues that are not parents in one pass, rather than one card at a time. Orders form one sequence across every milestone, so do not restart the numbering at 1 in each. A leftover order line hides every unranked card in its milestone and nothing reports it, so remove an order line that no longer means anything. A deferred card's order hides nothing there, because the page ignores it.
8. **What a card waits on changes.** Add or remove its "blocked by" link, then dispatch the board, because the link starts no run.
9. **An issue gains or loses a sub-issue.** Dispatch the board once the sub-issues are set, because they start no run. A split in a decompose loop is the usual case. An issue with any sub-issue draws as a parent under the shared and l3a0/quantitative-trading generators, and one with any open sub-issue does under l3a0/marketlake's.

Nothing else needs setting. A pull request opening, merging or closing, its checks settling, and an issue closing, retitled or relabelled all reach the board from GitHub.

### Parents and deferred cards

A parent builds nothing, and its children carry the plans. l3a0/marketlake's generator drops a verdict or an order on a parent, and a verdict on a `deferred` card, because the board would otherwise offer a deferred card as free to pick up. It lists each drop, and removing `deferred` brings the verdict back on the next run. A deferred card keeps its order, and the page and the sync round both skip it. So in that repository a parent carries no verdict and no order, and a deferred card carries no verdict.

The shared and l3a0/quantitative-trading generators drop neither. A `deferred`, `decision`, `parent` or `data` card can carry a `build` verdict there and still not be one to start, and the page's plan marker says so by dropping "ready to build".

### The commands

Run these after the setup block.

```bash
gh issue edit <n> --repo "$REPO" --add-label working:build
gh issue edit <n> --repo "$REPO" --remove-label working:build
gh issue edit <n> --repo "$REPO" --add-label working:decompose
gh issue edit <n> --repo "$REPO" --remove-label working:decompose
gh issue comment <n> --repo "$REPO" --body-file <file>
gh api --method PATCH "repos/$REPO/issues/comments/<id>" -F body=@<file>
gh issue view <n> --repo "$REPO" --json body --jq .body > <file>
gh issue edit <n> --repo "$REPO" --body-file <file>
gh api --method POST "repos/$REPO/issues/<n>/dependencies/blocked_by" \
  -F issue_id="$(gh api "repos/$REPO/issues/<b>" --jq .id)"
gh api --method DELETE \
  "repos/$REPO/issues/<n>/dependencies/blocked_by/$(gh api "repos/$REPO/issues/<b>" --jq .id)"
```

A "blocked by" link takes the blocker's database id, which `--jq .id` reads, rather than its number. A body line is added by editing the issue's body with the view and edit pair above, and goes on a line of its own, which is what every generator reads.

## The markers and their grammar

Three kinds of marker carry a session's judgement, besides the review heading of moment 5.

1. **Labels.** `working:build` says a build session holds the card, and `working:decompose` says a decompose loop is planning it. `band:N` ranks it, where the generator reads bands.
2. **A verdict line in a comment.** `Board verdict: build after 11 passes` or `Board verdict: decide after 4 passes`.
3. **Order and after lines in the issue body.**

   ```text
   Board order: 14.5
   Board after: #51, #83
   ```

   `Board order:` ranks the card. The order takes a decimal, so `Board order: 2.5` puts a card between 2 and 3 without renumbering either. `Board after:` names the issues it should land after, where nothing enforces that order.

The labels, as the owner or the template's setup script creates them:

| Label | Colour | Description | Read by |
| --- | --- | --- | --- |
| `working:build` | `fbca04` | A build session holds this card until it hands its pull request over | every generator |
| `working:decompose` | `fbca04` | A decompose loop is planning this card | every generator |
| `band:1`, `band:2`, `band:3` | set by the setup script | The card's priority, lowest first | the shared and l3a0/quantitative-trading generators |
| `deferred` | set by the setup script | Deferred on purpose | every generator |
| `decision` | set by the setup script | Waits on an owner decision | the shared and l3a0/quantitative-trading generators |
| `blocked-on-data` | as created in the repository | Waits on data that has to be bought or captured | l3a0/quantitative-trading's generator only |

Each line follows the same grammar, which all three generators share at the commits in the compatibility table.

- It starts its line, with nothing before it but spaces or tabs. A list marker such as `- ` or `1. `, or a quote marker `> `, stops it being read. An order or verdict line also has nothing after it but spaces or tabs.
- The words are exactly as shown, in that case, with one ordinary space after the colon. `Board after:` takes any spacing after its colon.
- An order is an optional minus sign, then digits, then optionally a decimal point followed by at least one digit. So `+2`, `.5`, `2.` and `1e3` are not read. l3a0/marketlake's `board-markers` skill stated a limit of 15 digits in all for an order and for a pass count, and its generator lists a longer one as unread. A pass count is a whole number. `pass` and `passes` both read, and a trailing full stop is allowed.
- A line inside a fenced code block is not read, so a fence is how to quote the format. A line inside a code span is not one either, because it does not start the line. A line quoted inside a sentence is not read.

Three parts of the grammar differ by generator.

1. **What a `Board after:` line reads.** The shared and l3a0/quantitative-trading generators read every `#N` on the line, so `owner/name#N` would read as this repository's issue N. Never write a reference to another repository on that line. l3a0/marketlake's generator reads each `#N` and the link form `[#N](https://github.com/<owner>/<repo>/issues/N)`, which may carry an anchor or a query after the number, such as `#issuecomment-5`. It refuses a reference to another repository, written `owner/name#N` or as a link to another repository, rather than reading it as this repository's issue, and it refuses a link whose text and address name different numbers. Every generator keeps only open issues from the line.
2. **Whose text counts.** Anyone can comment on or open an issue in a public repository, and a stranger's text would otherwise move a card. A verdict and a review count only in a comment whose author GitHub reports as `OWNER`, under every generator. Sessions run `gh` as the owner, so their text counts. l3a0/marketlake's generator also reads an order or after line only in the body of an issue the owner opened, so a line the owner adds to someone else's issue is refused. The other two read a body line on any issue. A label and a link need triage access, so they count whoever set them.
3. **What a line that is not read does.** When an issue's comments carry several verdicts, the newest wins, and when a body carries several order lines, the first wins, under every generator. l3a0/marketlake's generator also lists, in its summary, a line that looks meant as a marker and is not read, such as `board order: 3`, `Board order 3`, `**Board order**: 3` or `1. Board order: 3`, along with conflicts, refused lines and dropped markers. A line counts as meant for a marker when the marker's words end it, or are followed, after optional emphasis and spaces, by a colon, a digit or a `#`. Prose that only starts with the words, such as "Board orders form one sequence", is not listed. The summary names the issue and the marker's kind, never the line, so read the issue for the line itself. None of these stops the Action.

**A branch that closes no issue gets no card at all**, because the page is built from the tracker. Check `closingIssuesReferences` when a pull request opens, and if it is empty and the branch means to close something, fix the body before going further. A pull request into any branch but `main` is the exception. GitHub reads closing keywords only on a pull request into the default branch, so a stacked one shows an empty list until its base moves to `main`. That query is also eventually consistent. On [l3a0/quantitative-trading PR #94](https://github.com/l3a0/quantitative-trading/pull/94) it reported nothing seconds after the body gained its closing keyword and reported the link on the next call, so read it a second time before concluding the keyword failed. Every generator also reads a `Part of #N` reference anywhere in the body outside code. A pull request from a fork gets no card entry under every generator, because GitHub registers a fork's closing keyword, so a stranger's fork reading `Closes #640` would otherwise move that issue into In flight.

**A label is owed its removal by the session that set it.** A session that ends without taking its `working:` label off leaves its card under "Waiting on my review", "Building" or "Being planned" until somebody removes it. That fails safe, because it delays a merge rather than inviting one too early. So report a stale label rather than removing another session's. The `sync-prune-next` skill's step 3 says how a round finds one.

## The data, and where each field comes from

The page loads each section of `board.json` into the variable of the same name in capitals, so `prs` becomes `PRS`, and the rest of this section uses those names. The shared and l3a0/quantitative-trading generators write each section other than `state` as `{"schema": 1, "items": [...]}`, while l3a0/marketlake's writes a bare list. So a reader that must work on every board unwraps a section first, as `jq '(.working | if type=="object" then .items else . end)[]'` does. Their `prs` also keeps merged and closed entries, so a reader asking for open pull requests filters on `state == "open"`. Change what GitHub holds. Never hand-write a sentence in the page stating a number the data already carries, because that sentence outlives the number.

### Shared and l3a0/quantitative-trading generators

| Section | Field | Comes from |
| --- | --- | --- |
| `STATE` | `repo`, `title` | shared only: the repository the run read, from `--repo`, and the board's title, from the reusable workflow's `title` input, which defaults to `<name> build board`. The page builds every issue and pull request link from `repo`, so nothing in the page names a repository |
| `STATE` | `updatedAt`, `issues.open`, `longestGapMinutes`, `staleAfterMinutes` | the time GitHub was read, the open issue count, the longest gap in the caller's schedule, and that gap plus a 600-minute allowance for a scheduled run GitHub starts late or drops |
| `TRACKER` | `n`, `ms`, `label`, `labels` | each open issue's number, milestone, title and labels, less the board's own `band:N` and `working:` labels, which the page draws as the rank chip and the busy stripe |
| `TRACKER` | `kind` | `parent` for an issue with any sub-issue, then `data` for `blocked-on-data` under l3a0/quantitative-trading's generator only, then `deferred` for `deferred` and `decision` for `decision`, in that order where an issue carries more than one, and `ready` otherwise |
| `TRACKER` | `needs` | the issue's native "blocked by" links, keeping only blockers that are open issues in this repository |
| `TRACKER` | `after` | the issue's `Board after:` line, keeping only open issues |
| `PRS` | `pr`, `issue`, `state`, `linked`, `partOf`, `rollup` | each pull request naming an open issue through a closing link or a `Part of #N` reference anywhere in its body outside code, with its checks at the current head |
| `PRS` | `reviewed`, `review` | an owner's comment opening with `## Review`. Without one, `review` reads "review in progress" while the card carries a `working:` label, and "no review posted" otherwise |
| `WORKING` | `n`, `kind` | the `working:build` and `working:decompose` labels |
| `PLANNED` | `n`, `passes`, `ready` | the newest owner comment carrying a `Board verdict:` line |
| `NEXT` | `issue`, `band`, `order` | the `band:N` label and the `Board order:` line |
| `NEXT` | `ready` | the card's verdict where it has one, `decide` for a card whose kind is `decision`, and `plan` otherwise |

`NEXT_SORTED` is `NEXT` put in order, by band, then order with 50 where a card has none, then readiness, then number. It is derived on every load.

### l3a0/marketlake's generator

```text
{ schema: 1, state, prs, working, planned, next, tracker }
```

- **`state`** holds `main`, the default branch's head as seven characters, `updatedAt`, the time GitHub was read, and `issues.open`. Nothing else is in it. The `deployed`, `lake`, `suite`, `page` and `issues.deferred` fields that rounds once wrote by hand are absent, because the page draws none of them.
- **`prs`** has one entry per open pull request and open issue it names, keyed by `issue`, as `{issue, pr, state, review, linked, partOf, reviewed, rollup}`. A pull request naming two open issues has two entries, and one naming no open issue has none. `state` is `open`. `linked` is true when the pull request's `closingIssuesReferences` names the issue, and `partOf` is true when only a `Part of` reference does. `reviewed` follows the `## Review complete` rule of moment 5. `review` is a fixed phrase, either `review complete` or `no Review complete marker since the head commit`, so it never names the lens still running. GitHub's review decision cannot tell whether the review ran, so it does not decide `reviewed`. A pull request whose final review was posted before the rule carries no marker, so it reads `reviewed: false` until a session posts one, and a round reports it rather than guessing whether its review finished. To check one pull request by hand, count its markers with this command, where a count above zero means reviewed.

  ```bash
  gh pr view <n> --repo "$REPO" --json comments,reviews,commits --jq '.commits[-1].committedDate as $head | [.comments[] | select(.createdAt > $head and .authorAssociation == "OWNER") | .body] + [.reviews[] | select(.submittedAt > $head and .authorAssociation == "OWNER") | .body] | map(select(test("\\A## Review complete\\r?(\\n|\\z)"))) | length'
  ```

- **`rollup`** is a list of `[name, conclusion]` pairs for the checks on the head commit, and the conclusion is one of five words. Together they cover every value of GitHub's `CheckConclusionState` and `StatusState`, and a value GitHub adds later is written as `"neutral"` until this list names it.

  1. `"success"` is a check that ran and passed: a check run's or a status context's SUCCESS.
  2. `"skipped"` is GitHub's SKIPPED, a job whose condition kept it from running. It counts as settled. l3a0/marketlake's `tofu apply (live)` job is skipped on every pull request, because it runs only on `main`.
  3. `"failure"` is a check that failed, including one that timed out or could not start: a check run's FAILURE, TIMED_OUT and STARTUP_FAILURE, and a status context's FAILURE and ERROR.
  4. `"running"` is a check that has not concluded: a check run with no conclusion yet, and a status context's PENDING and EXPECTED.
  5. `"neutral"` is a check that concluded without passing or failing: a check run's NEUTRAL, CANCELLED, STALE and ACTION_REQUIRED.

  The generator leaves out the board workflow's own checks, `board-build` and `board-deploy`. A `pull_request_target` run attaches them to the pull request's head commit, so without that a reviewed pull request would read as still running while the board rebuilds. The page reads a rollup as green when every entry is `"success"` or `"skipped"` and at least one is `"success"`. It reads any word outside these five as unsettled, the same as `"neutral"`, so an unknown word keeps a card out of the owner's queue rather than drawing a pass.
- **`working`**, `{n, kind}`, comes from a `working:build` or `working:decompose` label. One with `kind: "build"` draws under Building and keeps its pull request out of the owner's queue.
- **`planned`**, `{n, passes, ready}`, comes from the owner's newest `Board verdict:` comment line, and marks a card whose plan is finished.
- **`next`**, `{issue, band, order, ready}`, comes from a `Board order:` line in the body of an issue the owner opened, and ranks the card. `band` is 0 in every entry. `ready` is the card's verdict, or `plan` without one. With nothing ranked in the chosen milestone, the page's default view draws every card in it rather than only the ranked ones. Each list is sorted by issue number.
- **`tracker`** has one card per open issue, as `{n, label, labels, ms, kind, needs}`. Its `ms` is the milestone's title up to its first comma, so "MVP 2, capture on a hosted VM" reads `"MVP 2"`, or `"no milestone"`. Its `kind` is `parent` while an open sub-issue exists, else `deferred` under that label, else `ready`. The page also draws the kinds `decision` and `data`, which the generator never writes. Its `needs` holds the open issues in this repository that a native "blocked by" link names. Dependency sections in issue bodies are not read, so a blocker written only in a body is not on the board until someone adds the link. Its `after`, when present, lists the open issues other than itself that a `Board after:` line in the owner's body names. Its `labels` leave out the `working:` labels, which draw as its place under In flight instead.

The generator writes no `untracked`, which the page reads as empty. The page filters cards by milestone, with a selector that defaults to "MVP 2". So a card's milestone comes only from `tracker`, and an issue missing from `tracker` never draws, whatever `next` or `prs` say about it.

The page's `usable()` check refuses the whole document when any one of these fails. With nothing drawn yet, the page then shows only a banner saying the document is missing fields. With a board already drawn, it keeps that board on screen and says live updates stopped.

1. `state.main` and `state.updatedAt` are strings, and `state.issues.open` is a number.
2. `tracker` is a list with at least one entry, and `prs`, `working`, `planned` and `next` are lists.
3. Each `tracker` entry has a number `n`, a string `label` and `ms`, a `kind` of `ready`, `deferred`, `parent`, `decision` or `data`, and a `needs` list of numbers. An `after`, when present, is a list of numbers, and `labels`, when present, is a list of strings.
4. Each `prs` entry has a number `pr` and `issue`, a `state` of `open`, `merged` or `closed`, a string `review`, a boolean `reviewed`, and a `rollup` list whose every entry is a pair of strings. `linked` is a boolean or a list of issue numbers, and `partOf`, when present, is a boolean. The page reads a list as linked only when it names the entry's own `issue`.
5. Each `working` entry has a number `n`. A `kind`, when present, is a string.
6. Each `planned` entry has a number `n` and a number `passes`.
7. Each `next` entry has a number `issue` and a number `band`. An `order`, when present, is a number.
8. Each `planned` and `next` entry has a `ready` of `build`, `decide` or `plan`.

The numbers and the fixed sets are checked because the page writes those fields into links and attributes without escaping them. The booleans are checked because the page tests them for truth, and the string `"false"` is true. The lists of numbers are checked because the page compares them against card numbers, and a string in `needs` matches no card and frees a blocked one.

### Three fields carry judgement rather than measurement

1. **`needs` against `after`.** `needs` is a hard blocker and moves a card into a deeper column. `after` is an ordering somebody measured that nothing enforces, so it leaves the card where it is and sorts it below what it names. Use `after` when one card can be built first but is better built second, such as a fix that leaves the suite red until another issue lands. [l3a0/quantitative-trading#83](https://github.com/l3a0/quantitative-trading/issues/83) once carried `after: [51]` because its own body measured the split: three of the failures a second download causes belonged to [l3a0/quantitative-trading#51](https://github.com/l3a0/quantitative-trading/issues/51) and the rest did not, so it could be built first while the suite stayed red until 51 landed. A "blocked by" link there would have said something false. A link and an issue's `## Depends on` prose say the same thing twice. The link wins, because it is what the board reads, and the prose keeps the reason the wait exists.
2. **A verdict means a decompose loop exited**, on a pass that did not reduce the body. Not that a body looks thorough. Read the pass count as a cost rather than a depth. One l3a0/quantitative-trading run reached 109 passes under an older exit rule, which asked for two consecutive empty passes and could not terminate while the loop edited its own artifact.
3. **`band`** is priority, and what each band means is the repository's call, under the ranking directive in its own `CLAUDE.md`. `## In each repository` below says where each repository writes it down.

`question` is not `decision`. An issue can carry `question` while it waits on research rather than on the owner, as [l3a0/quantitative-trading#273](https://github.com/l3a0/quantitative-trading/issues/273) did, so the board reads only `decision` as needing the owner rather than a session.

### When two labels disagree

An issue carrying two `band:N` labels, both `working:` labels, two kinds, or two different `Board order:` lines has no single value. Every generator takes the lowest band, the `build` kind, the kind the tables above put first and the first line, and lists each conflict rather than failing, because one stray label would otherwise freeze the whole board. The one exception is l3a0/marketlake's generator, which takes `parent` over `deferred` without listing it. The shared and l3a0/quantitative-trading generators list conflicts in the run's job summary. l3a0/marketlake's lists them in the summary table its build prints, which a status round reads, because nobody reads the Action's own job summary there. Read the list after setting either, and fix the label the conflict names.

## In each repository

What follows holds for one repository only. Everything above it holds wherever its setup does.

### l3a0/quantitative-trading

The dispatch there is this line.

```bash
gh workflow run board.yml --repo l3a0/quantitative-trading
```

- **The page** is <https://l3a0.github.io/quantitative-trading/>, built by `scripts/build_board.py`, run by `.github/workflows/board.yml`, from the page source and tab icon beside that repository's copy of this skill.
- **What each band means** is 1 for work that blocks other work or risks data that cannot be recaptured, 2 for the reader chain everything waits behind, 3 for a sentence wrong where a reader acts on it, and 5 for deferred on purpose. No band 4 is defined, so no label exists for it.
- **The `blocked-on-data` label** gives a card the kind `data`, and the page draws such cards in a fourth build-order column, "Waiting on data", under the subtitle "not a backlog, a purchase". [l3a0/repo-template#24](https://github.com/l3a0/repo-template/issues/24) cut that kind and column from the shared board, because no other repository has the label, so moving this repository onto the shared board either drops the column or adds an input for it.
- **The Show all choice** is kept in the viewer's browser under the key `qt-board-all`.
- **The retired artifact.** Until [l3a0/quantitative-trading#533](https://github.com/l3a0/quantitative-trading/issues/533) the board was a claude.ai artifact whose figures sessions measured by hand and wrote into its database. That cost about $51 a day in session turns, measured on [l3a0/quantitative-trading#531](https://github.com/l3a0/quantitative-trading/issues/531), and it missed every change no session saw. That artifact is retired. Nothing writes it, and it is kept rather than deleted only because each ranked card's `why` and each plan's `note` exist nowhere else. Do not write to it, and do not publish the page to it.

### l3a0/repo-template

- **The page** is <https://l3a0.github.io/repo-template/>, and the caller's `uses:` ref is `main`, so the template's own board runs the template's newest generator and page.
- **What each band means** is left to each seeded repository. `scripts/setup-repo.sh` creates `band:1`, `band:2` and `band:3`, `working:build`, `working:decompose`, `deferred` and `decision` through `.github/labels.json`.

### l3a0/ithildin-runtime

- **The page** is <https://l3a0.github.io/ithildin-runtime/>, and it deploys only from `main`. Its caller pins the template at `4bb3f7f301300ed3f86a4992e6792fba3f7d3ed7`, which is before the `icon` input, so it serves the template's icon.
- **What each band means** is set by `## Keep the build board current` in that repository's `CLAUDE.md`, under its ranking directive. That section is the one place the meaning is written, so read it there rather than from a copy here.

### l3a0/marketlake

The dispatch there is this line.

```bash
gh workflow run board.yml --repo l3a0/marketlake
```

- **The page** is <https://l3a0.github.io/marketlake/>. Its generator, page, stub and icon sit beside that repository's `sync-prune-next` skill, and its `.github/workflows/board.yml` runs them.
- **Ranking** is the `Board order:` line alone, since no `band:N` label exists there, and the page filters by milestone, defaulting to "MVP 2".
- **The review heading** is `## Review complete`, under that repository's `CLAUDE.md` owner directive of 2026-10-06.

## Finishing

Report in the same reply that sets anything.

1. Each label, link and line set or removed, and on which issue.
2. Any conflict, unread line, refused line or dropped marker the next build listed, and what fixed it.
3. Any sentence the harness caught, and what replaced it, when the page's code changed.
4. Any disagreement between this skill and the generator the repository runs, under rule 1 of `## Generator compatibility`.

A run of the Action that fails leaves the last board up. Where the page has a stale banner, it says so once the stamp passes `staleAfterMinutes`. Read the failed run's log rather than re-running it, because a second run of the same read fails the same way unless the failure was GitHub's.

An update reports the idle cards it found and offers no task for any of them, for the reasons [record.md](record.md) gives under its last heading. What to start, and how many at once, is the owner's call.
