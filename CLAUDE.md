# CLAUDE.md — claude-plugins

claude-plugins is the owner's personal collection of Claude Code skills, published as one plugin under the `l3a0` namespace. The repository is both the plugin and its own marketplace. `.claude-plugin/plugin.json` describes the plugin, and `.claude-plugin/marketplace.json` lists it. Each skill lives under `skills/<name>/`. One skill ships today, `kindle-highlights`, whose `SKILL.md` carries the method and whose `scripts/` folder carries the helpers it runs.

**Every gotcha in a skill was earned on a real run.** `skills/kindle-highlights/SKILL.md` names the five books it has run against and what each run recovered. [PR #2](https://github.com/l3a0/claude-plugins/pull/2), [PR #3](https://github.com/l3a0/claude-plugins/pull/3) and [PR #13](https://github.com/l3a0/claude-plugins/pull/13) each folded one run's lessons into the skill. [PR #5](https://github.com/l3a0/claude-plugins/pull/5) and [PR #18](https://github.com/l3a0/claude-plugins/pull/18) are the skill changes that did not come from a run. Both hardened the capture receiver. [PR #5](https://github.com/l3a0/claude-plugins/pull/5) followed a CodeQL alert, and [PR #18](https://github.com/l3a0/claude-plugins/pull/18) followed a review of [PR #17](https://github.com/l3a0/claude-plugins/pull/17) that found any web page open in the browser could write into the receiver's pages folder. A skill also runs against the user's own logged-in browser session and local app data, and is designed to keep that data on the user's machine. [SECURITY.md](SECURITY.md) states that scope. The capture receiver binds `127.0.0.1`. It refuses a write outside its pages folder, the guard [PR #5](https://github.com/l3a0/claude-plugins/pull/5) added, and any request whose `Origin` is not `https://read.amazon.com`, the guard [PR #18](https://github.com/l3a0/claude-plugins/pull/18) added.

Status: the repo has no test suite, no design doc, no build plan and no milestones. [README.md](README.md) and each `SKILL.md` carry the reasoning. Two kinds of check run on every pull request:

1. The Plugin Security Scan workflow in `.github/workflows/plugin-security-scan.yml`, which also runs on every push.
2. CodeQL, through GitHub's default code-scanning setup.

Dependabot bumps the workflow's pinned actions weekly, per `.github/dependabot.yml`.

## Writing style

The owner's global `~/.claude/CLAUDE.md` is the source for these rules. This section repeats them because the repo is public and a reader or an agent may arrive without that file. The price is that the two copies can drift. The global file wins, and this section is what gets corrected.

Clarity comes first. Write plain sentences a reader understands on one read. Prefer short, complete sentences, but never at the cost of clarity. Do not chop an idea into cryptic one-idea fragments. When a short sentence turns hard to parse, write the clear sentence instead, even if it runs a little longer. Explain as you go, like teaching, so the reader follows without backtracking. Avoid em dashes and semicolons. This applies to every prose surface: this file, each `SKILL.md`, commit messages, pull request bodies, and chat replies.

**Impersonal voice.** Write without the first person. No "I," "my," or "mine." The subject is the process, the mechanism, or the finding, not the author. "Running the script reproduced the result" beats "I ran the script to reproduce it." Keep it active, not passive: "The check reads the config," never "the config is read." Direct advice stays as an imperative. Drop the explicit "you" and "your" where it reads cleaner.

**Explain every concept on first use.** Coined vocabulary, borrowed tools, and non-obvious behaviors get their gloss where they first appear, not in a glossary. If a reader must ask "what is X," the writing failed at X's first appearance.

**Drop the jargon rather than glossing it.** Given the choice between defining an in-group term and deleting it, delete it. The test: when a sentence names a concept where it could say what happens, say what happens. "No test covers it" beats "it is unheld." A gloss works once, at first use, while the term keeps reappearing and costs the reader attention every time. Being native to a repo does not save a term. Cut the whole family at once, since the same idiom usually survives under a second word. One exemption: a term a `SKILL.md` defines on purpose and then reuses with that exact meaning, like the `kindle-highlights` skill's run directory.

**List a counted set. Do not inline it.** When a sentence names a count of items, like "four seams" or "three tests," the items follow as a list, not a run-on of sentences. Number the list when the prose states the count. Use a bulleted list for an unordered set with no count.

**Lead with why it matters, show the reasoning, and name the price.** Establish why something matters before explaining what it is. State the claim, then walk through why. When a choice carries a cost, name it outright, as in "the price for X is Y." When weighing two options, hand over the metric that decides between them instead of gesturing at "tradeoffs."

**Cut what carries nothing.** Throat-clearing, significance-announcing pivots, self-effort asides, hedging, redundancy, decorative modifiers that survive the subtraction test, unsubstantiated superlatives, reversal scaffolding, reassurance tags, and a closing moral that restates the heading. The global file carries the worked examples for each.

**Restyle an existing file in a change of its own.** `README.md` and `SKILL.md` predate these rules and still carry em dashes and the second person. An edit to one line follows the rules for that line and leaves the rest of the file alone, since a restyle swept into an unrelated change hides the change it rode in with.

**Link every issue and pull request number (owner directive, 2026-09-26).** In a chat reply, a message to another session, or a Markdown file in this repository, each number is a Markdown link: `[#NN](https://github.com/l3a0/claude-plugins/issues/NN)` for an issue and `[PR #NN](https://github.com/l3a0/claude-plugins/pull/NN)` for a pull request. [Issue 6](https://github.com/l3a0/claude-plugins/issues/6) and [PR #13](https://github.com/l3a0/claude-plugins/pull/13) are written that way. A number written out in prose, like "issue 6", takes the same link around the words. Link every mention, not only the first, including numbers inside lists, tables and summaries. A bare `#NN` in chat is text the owner has to copy into a browser, and GitHub renders a bare `#NN` in a repository file as plain text too. A report that links its first number and leaves the rest bare fails the same way. A number that belongs to another repository links there.

The prefix still matters. Issues and pull requests share one number space, so a bare number cannot tell the reader whether it names scope or work in review. An issue is `#NN` and a pull request is `PR #NN`.

Two places keep the bare form.

1. **GitHub's own text.** In an issue body, a comment, a pull request body or a commit message, GitHub links a bare `#NN` on its own, and a closing keyword needs the number right after it.
2. **Code and quotations.** A command, a code span, a file name or a quoted commit subject stays exactly as written, because a link inside it breaks it.

## Markdown hygiene

No CI job runs markdownlint here yet, and the repo carries no markdownlint config, so nothing enforces these rules and each change checks them by hand. markdownlint's defaults are not the standard either, because they cap lines at 80 columns, which `README.md`, `SKILL.md`, the blog post and this file already exceed. The rules that bite most: use real headings, never a bold line as a heading (MD036). No trailing whitespace (MD009). No stacked blank lines (MD012). End the file with exactly one newline (MD047). Table delimiter rows use single-space padding, so `| --- |` and never `|---|` (MD060). Escape an "approximately" tilde in prose as `\~`, since a bare tilde can render as strikethrough on some surfaces. Code fences are exempt.

After any edit, sweep. Both commands also match inside code spans and fences, so read each hit before changing it.

The first sweep already reports four lines in `SKILL.md`, which predate this file. Fix those in a change of their own, per the restyle rule under `## Writing style`.

```bash
rg -n --pcre2 '(?<![\s~\\`<])~' --glob '*.md' .
rg -n '\|-{1,}\|' --glob '*.md' .
```

## Cross-surface consistency

A repo drifts when two surfaces describe the same thing and only one gets updated. The fix is to give each surface exactly one job, so nothing is stated twice. Where a fact has to appear in more than one place, the list below names every place, so an edit to one is checked against the others.

- **The plugin's version** sits in `.claude-plugin/plugin.json`. The supported-versions table in [SECURITY.md](SECURITY.md) tracks only the minor version, as `0.3.x`. So a patch bump changes `plugin.json` alone, the way [PR #5](https://github.com/l3a0/claude-plugins/pull/5) moved 0.2.1 to 0.2.2, and a minor bump changes both, the way [PR #13](https://github.com/l3a0/claude-plugins/pull/13) moved to 0.3.0.
- **What the plugin holds** is described in four places, each worded differently: `.claude-plugin/plugin.json`, the marketplace and plugin entries in `.claude-plugin/marketplace.json`, and the repository's About text on GitHub. Each one names the skills, so adding a skill changes all four, and [README.md](README.md)'s `## Skills` section with them.
- **The run counts.** `skills/kindle-highlights/SKILL.md` carries each run's own figures, and [README.md](README.md) carries their totals: five books, 2,733 highlights, 1,038 of them blocked by the export limit. A new run moves both.
- **The capture receiver's guards** are described in three places besides `receiver.py` itself, so a change to what the receiver accepts changes all three.
  1. The opening paragraph of this file.
  2. The scope list in [SECURITY.md](SECURITY.md).
  3. The receiver gotcha under Step 2 of `skills/kindle-highlights/SKILL.md`.
- **The blog post** in `blog/how-to-take-back-your-kindle-highlights.md` is also published on Substack, and nothing syncs the two copies.

Before reporting a change done, sweep the prose surfaces for what the change could have invalidated, and end the response with a short **Consistency sweep** note listing what was checked, what was updated, and what is still stale. For a pure-internal refactor that changes no observable behavior, say "no prose-facing surfaces affected" so it is clear the check was considered rather than forgotten.

A mechanical consequence of an edit is part of that edit, not a separate decision. When a change leaves a generated artifact stale, regenerate it in the same change without asking.

## Secrets and machine paths

This repo is public. Tracked files never carry secrets or machine-specific paths. Sweep for leaks before any publish.

The repo holds no secrets today, and no skill needs a credential of its own. The `kindle-highlights` skill works through the user's existing Amazon session in Chrome and the Mac Kindle app's local files, so three things stay out of tracked files.

1. **Extracted highlights, captures and run directories.** They hold copyrighted book text, and [README.md](README.md) asks that extracted notes stay private.
2. **Amazon account identifiers.** The Kindle app's annotation database sits under a folder named for the account, so a tracked file writes that segment as a wildcard, the way `SKILL.md` writes `amzn1.account.*`.
3. **A path that names a machine or a person.** A home-relative path such as `~/Downloads` is fine.

## Committing

**Commit, push and open the pull request without waiting.** A session that has finished the deliverable it was given commits it, pushes the branch, and opens the pull request on its own. It does not stop to ask first.

An earlier version of this rule asked for explicit approval before every commit. The cost was a session idle on finished work whenever the owner was away from the keyboard, and the approval bought nothing the pull request's own diff does not show better and later.

Three things still hold.

1. `main` requires a pull request. An active repository ruleset enforces it, and it also asks for one approving review. The owner is the only collaborator, so a merge goes through the owner's bypass. Never use that bypass to push to `main`: branch, push, and open a PR, even for a one-line docs change.
2. A commit carries only what the session actually did. Unrelated edits found on the way past are filed as their own issue, per the closing rule below, and never swept into the branch.
3. Work outside the session's own deliverable still waits for the owner. That covers this file and anything outside the repository, such as the owner's `~/.claude/` folder.

Branch before the first edit, not just before the commit. The moment a task will modify any tracked file, run `git branch --show-current` and branch if it shows `main`. Re-check before every commit, not just the first of a session, because a mid-session squash-merge deletes the branch and leaves the checkout on `main`.

## Pull requests

**Review every pull request before the owner does.** A PR the owner has not seen reviewed is not finished work. This holds whether the PR is yours or someone else's, whether it is one line or a thousand, and whether or not a review was asked for. The owner's time is the scarce thing, so a PR reaches them already checked rather than waiting to be read cold.

**Send the link as soon as the pull request exists, then review it.** Opening the pull request and starting the review are one step, and neither waits on the owner. The link is what lets them watch the review land, so holding it back leaves them blind to work that is already pushed. Post the findings on the pull request, and say plainly what the review found and what it refuted, including when it found nothing.

Review by fanning out independent lenses, then verifying each finding adversarially. Several reviewers in parallel, each with one lens and no sight of the others, produce the findings. Verifiers then try to refute each one, and only what survives is acted on. Point one lens at completeness and one at over-reach, which catch the two failures that recur:

1. Fixing the instance rather than the class, such as a false claim corrected in one file while it still stands in three more.
2. Fixing past the class, such as generalising a change into places it does not belong.

Verify by executing, not by reading. Break the code and confirm a check notices. A check that still passes on broken code does not cover what it claims to cover. With no test suite here, that means a fixture the changed script fails on before the fix and passes on after it, the way [PR #13](https://github.com/l3a0/claude-plugins/pull/13) reproduced a `finalize.py` bug on a fixture before fixing it.

**Watch the checks and fix what they find.** A pull request is not handed over until its checks have run and settled. Pushing is not the end of the work, because the branch that passes locally is not the branch CI builds. CI builds the merge of the branch and its base, and the base moves.

So watch the run rather than assume it. `gh pr checks <n> --watch` blocks until every check settles, and `gh pr view <n> --json statusCheckRollup` says what each one concluded. When a check fails, read its log, fix the cause, and push again, in the same session and without waiting to be asked. A red check the owner finds first is work handed over unfinished.

Three behaviours make the rule sharper than "look for a green tick". The first two were measured on pull requests in the sibling `marketlake` repo, and the third on the template this file was seeded from.

1. **A conflicting pull request gets no run at all.** A `pull_request` workflow builds the merge ref, and a branch that conflicts has none, so no run is created. [PR #414](https://github.com/l3a0/marketlake/pull/414) there showed three green CodeQL entries and no `test` run whatsoever. An absent check reads as a short rollup rather than as a failure, so count what ran instead of scanning for red. Here the security scan also runs on every push, so a conflicting branch still shows one green `scan` entry from the push run.
2. **Green goes stale.** A run is computed against one merge ref, and a later merge to the base replaces it. [PR #433](https://github.com/l3a0/marketlake/pull/433) there read green after the branch had already conflicted underneath it. Re-read the rollup whenever the base has moved.
3. **Red goes stale the same way, and costs more.** A failure inherited from the base survives in the rollup after the base has been fixed. The template's [PR #3](https://github.com/l3a0/repo-template/pull/3) carried a red `test` check from a run computed 25 seconds before the pull request that fixed its base merged. Rebasing made it green, and a monitor reading the older snapshot reported the failure again afterwards. A red check is a claim about one merge ref at one moment, so re-read it before acting, and check whether the pull request has already merged before fixing anything.

Fix the cause rather than the symptom. A check that fails on one file usually fails on its siblings, so sweep for the class. Re-running a job changes nothing the second time unless the failure was the runner rather than the code. Where a failure comes from another branch's merge rather than from this change, say so on the pull request instead of absorbing an unrelated fix into it.

**A filed issue carries its labels.** Filing is not finished when the issue exists. An issue with no label appears in no view scoped by kind, so only a sweep for unlabelled issues finds it, and nothing brings it back on its own. The repo has no milestones today, so a label is the only grouping an issue has. A filed issue is finished when it says two things.

1. A label says what kind of work it is.
2. A dependency says what it waits on, where it waits on anything.

No automation supplies the label. The same applies to an issue a spawned session is told it may file. The instruction to file carries the instruction to triage, or the work lands where nothing will look for it.

**Close an issue only when nothing is left in it.** Before a PR closes an issue, move whatever that PR does not do into its own issue. A piece described only inside a body goes when the body closes, and nothing surfaces it again.

While a piece is outstanding, a PR writes `Part of #NN` and the closing keyword waits for the PR that leaves nothing. GitHub reads the keyword only when the number follows it immediately, so `Closes #101` closes and `Closes the second half of #101` closes nothing at all. The keyword also has to be plain text, and a code span around it defeats it the same way. Rendered, a code span and plain text differ only in font, so reading the body back does not distinguish them. `gh pr view <n> --json closingIssuesReferences` does, and an empty result on a pull request that means to close something is the signal to fix the body before merging.

An issue whose pieces have all been split has no finishing PR left, so close it by hand and name where each piece went. Do the same when two PRs are open against one issue, because merge order decides which lands last and neither body can know it. A split leaves code comments pointing at the parent for work that moved, so repoint those in the PR that splits. A comment naming a closed issue in the past tense records what happened rather than pointing anywhere, and it stays.

PR titles use a Conventional Commits prefix. The form is `type(scope): summary`. `gh pr list --state merged --json title` reports which prefixes this repo has used, rather than a list here that goes stale on the first unfamiliar one. Add a scope in parens when it sharpens the title, like `docs(CLAUDE.md)`. Drop it when none does, like a plain `docs:` for a whole-doc change.

PR bodies use Markdown section headings, not a wall of prose. Lead with `## Why`, then `## What`. Add situational sections after as the change needs them, like `## Scope`, `## Notes`, or `## Evidence`. The body's prose obeys the writing-style rules above. So clear, short sentences and no em dashes. End every body with the footer line: `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.
