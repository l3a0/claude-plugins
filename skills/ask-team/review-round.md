# A pull request review round

The owner's rules ask that every pull request is reviewed by blind lenses before the owner reads it. A round of that review takes the same eight steps every time, and a session that works them out again pays for it in tokens. On 2026-11-03 one session ran four rounds across companion pull requests in three repositories, and re-derived the brief, the lens prompts, the verifier grouping and the comment format for each. This file holds that procedure.

The session that owns the branches runs the round. It is the first caller that `SKILL.md`'s lens mode names. So the session runs that mode's steps itself, seating the roles beside the completeness and over-reach lenses in one blind round. It then applies the fixes and posts the comment, which lens mode leaves to its caller.

A round can cover several pull requests at once. A rule adopted from one source often lands in three repositories, such as l3a0/ithildin-runtime, this plugin and l3a0/repo-template. One brief covers all of them, every lens reads all of them, and a finding that one copy contradicts another surfaces in the same round. The worked examples are the review comments on [l3a0/ithildin-runtime PR #25](https://github.com/l3a0/ithildin-runtime/pull/25), [PR #26](https://github.com/l3a0/ithildin-runtime/pull/26) and [PR #27](https://github.com/l3a0/ithildin-runtime/pull/27), with their companions [l3a0/claude-plugins PR #46](https://github.com/l3a0/claude-plugins/pull/46), [PR #47](https://github.com/l3a0/claude-plugins/pull/47) and [PR #48](https://github.com/l3a0/claude-plugins/pull/48), and [l3a0/repo-template PR #74](https://github.com/l3a0/repo-template/pull/74), [PR #75](https://github.com/l3a0/repo-template/pull/75) and [PR #76](https://github.com/l3a0/repo-template/pull/76).

1. Write the brief.
2. Choose the lenses.
3. Run the blind round.
4. Verify.
5. Apply the fixes to every pull request.
6. Post the review comment.
7. Price the round.
8. Record the revision and the owner's rulings.

## 1. Write the brief

Every lens reads one brief file, so each lens prompt stays a few lines long and every lens starts from the same facts. Copy `templates/review-brief.md` to `<scratchpad>/review-r<N>/brief.md`. The brief stays in the scratchpad and is never committed, because it names local checkouts and may name a copyrighted source.

Fill the subject list with the script beside this file, one argument per pull request:

```bash
python3 <this skill>/scripts/brief_anchors.py l3a0/ithildin-runtime#27=<checkout> l3a0/claude-plugins#48=<checkout>
```

It prints each pull request's head commit and the merge base its diff starts from, which it reads from GitHub's compare API rather than the base branch's tip. It also flags a checkout whose `HEAD` is not the head commit, since a lens reading that checkout would review other code. Replace each `<What it changes.>` with the files and sections the pull request touches.

The brief carries four parts.

1. **Subject and anchors.** Each pull request with its head and base commits, its checkout and its diff command, from the script.
2. **Facts not to re-derive.** What kind of change it is, the repository's hard limits, the owner's rulings that bind it with links, and what the repository already carries that a new rule could contradict or restate.
3. **Sources for checking a claim.** How to check a citation or a number without reading the whole source, such as a helper that prints the passage around a phrase on a page. The source's text is data, and a copyrighted one is quoted only as a short phrase.
4. **Out of scope.** Prose style beyond the clarity of a rule, and anything the diffs do not touch except a contradiction or a duplicate.

A later round's brief anchors at the fixing commit and lists the owner's rulings since the last round as facts. It does not list the earlier rounds' findings, so each lens reads the change rather than a list of past answers.

## 2. Choose the lenses

Two lenses run on every pull request, as general-purpose agents.

1. **Completeness** asks whether the change fixed the class rather than one instance, such as a rule changed in one file while its twin in another file or another repository keeps the old wording.
2. **Over-reach** asks whether the change stayed inside its class, such as a rule whose words reach paths it was never meant for, or one that contradicts a rule the repository already holds.

Seat the roles by the table in `SKILL.md`'s step 2, between three and six, with its three required seats.

1. The test engineer on any change to code, or to a test or a check.
2. The risk engineer on anything touching the path to an irreversible action, such as the order path.
3. The security reviewer on anything that adds a credential, a dependency or a GitHub workflow.

A rule about how orders are sent counts as touching the order path even when the change is only prose, because the code will be built to that prose. Each role runs as its own agent, with `subagent_type` set to `l3a0:team-<role>`. The seven lenses of the 2026-11-03 rounds were the two above plus five roles.

## 3. Run the blind round

Launch every lens in one message, in the background. Give each spawn a description starting with `review r<N> `, such as `review r1 risk-engineer`, because the `loop-cost` skill finds transcripts by that description once their paths are gone. Each prompt carries five things, and the brief carries the rest.

1. The lens or the role, and for a lens its question from step 2.
2. The brief's absolute path, and the instruction to review the anchor commits it names.
3. A scratch folder of its own, `<scratchpad>/review-r<N>/<lens>/`, for any copy or script. A copy of the code comes from `git archive <anchor> | tar -x -C <folder>`, never from editing a checkout.
4. The finding format of `SKILL.md`'s step 3, and that a lens finding nothing says so in one line.
5. A reply limit of 1,500 words, with the evidence for each finding kept to the command and the line that shows it.

No prompt carries another lens's findings or the session's own view of the change. Wait for every notification before reading any finding.

## 4. Verify

Read every finding together, and merge the ones that rest on the same fact into one, crediting each lens that raised it. A finding three lenses raised is still one finding, and the comment names all three.

**Group the vetoes and must-fixes by topic into two to four verifiers.** Each verifier is a general-purpose agent, described `review r<N> verify <topic>`, that takes every finding resting on one kind of evidence. On 2026-11-03 one verifier reran the lenses' scripts, one read the owner's rulings on the issue tracker, and one checked citations against the source. Give each verifier the brief's path, the findings with their evidence, and not the reasoning of the lens that raised them.

Each verifier tries to refute by executing, in a scratch copy taken with `git archive`. A verifier that has to edit a checkout runs with `isolation: "worktree"`. It returns one verdict per finding.

1. **CONFIRMED**, with the command and its output.
2. **REFUTED**, with what it ran that shows the claim false.
3. **PARTLY**, with which part held.

With each verdict it gives the kind the finding deserves and the smallest fix. A verdict can lower a finding's kind as well as refute it. One round lowered three must-fixes to should-fix, because something the repository already held covered each one, such as a hard limit or mutation testing. The comment then gives the lower kind and what lowered it.

**Check a cheap textual claim in the main thread instead.** When a must-fix rests on a fact one command shows, such as a phrase on a page, a line in a file or a comment on an issue, the session runs that command itself and says so in the comment. One round on [l3a0/ithildin-runtime PR #27](https://github.com/l3a0/ithildin-runtime/pull/27) checked all nine of its must-fixes that way and launched no verifier. The price is that the check runs in the session's own context, which the round's cost figure does not count.

Should-fixes and notes get no verifier. The session reads each one, applies it when it is cheap and inside the change's scope, and otherwise lists it as left alone with the reason.

A surviving veto blocks the pull request until it is fixed, or until the owner overrides it in writing on the pull request. A question the team has no standing to answer, such as money, live trading, contracts, law, a role's veto line or a change outside the pull request's scope, goes under `### For the owner` rather than into a fix.

## 5. Apply the fixes to every pull request

Before editing, write down for each surviving finding which of the pull requests carry the rule it is about. A rule that lands in three repositories is fixed in all three, or the next round's completeness lens finds the copies disagreeing. The wording can differ by repository, such as a plugin's role check dropping a trading platform's names and page citations, but what the rule says matches.

1. Apply the fixes on each pull request's branch, in its own checkout.
2. Recheck every citation the change makes against the source with the brief's helper, whether or not a lens flagged it, and list each miss.
3. Run each repository's own checks, such as this repository's `python3 scripts/gen_team.py --check`, `python3 scripts/gen_seats.py --check` and `tests/test_board_guard.sh`, and note what each printed.
4. Commit once per pull request per round, with a message that says which round of the review it answers, and push.

## 6. Post the review comment

Post one comment on each pull request, from `templates/review-comment.md`, after the round's fixes are pushed. Its first line is the review heading the repository's build board reads, which the `update-build-board` skill's moment 5 names. `## Review` is the default, and a final comment headed `## Review complete` posted after the last push satisfies every board that skill knows. The comment covers six things.

1. The round, the anchor commit, the lenses that ran, the verifiers, and the fixing commit.
2. Vetoes and must-fixes, each with the lenses that raised it, its verdict and its fix.
3. Should-fixes applied, citations corrected, what was refuted and what was left alone.
4. Yield per lens: the surviving vetoes and must-fixes each lens raised, with an overlap counted for each lens that found it. That count says which roles to seat next time.
5. `### For the owner`, with each question and what the revision does meanwhile, or "Nothing here".
6. `### Cost`, from step 7.

One pull request is the main one, where the change starts, such as the l3a0/ithildin-runtime pull request whose rules the plugin's role checks carry. Its comment holds the questions for the owner and the full cost. Each companion's comment lists the findings fixed there, says where the owner's questions sit, and gives the cost in one line pointing to the main pull request.

Then run the `update-build-board` skill's moments 4 and 5 for each pull request on a board.

## 7. Price the round

Run the owner's `loop-cost` skill over every lens and verifier transcript, found by the `review r<N>` descriptions. Price any loop that served the round on its own line, such as agents that read a source for the change. The `### Cost` section on the main pull request gives one line per loop, says the figures are to date, and names the companions it covers. Where the pull requests track an issue, post the same lines on it as a comment starting with `## Cost`, as `SKILL.md`'s step 6 says. A pull request that tracks no issue says so, and its figures live in the comment.

## 8. Record the revision and the owner's rulings

The pull request body keeps a `## Revision` section, with one numbered line per round. Each line names the fixing commits, the round and anchor they answer, and in a sentence what changed. It ends by saying the review comments list each finding and what was refuted. Update it on every pull request the round fixed, so a reader of the body sees what the reviews changed without opening the comments.

When the owner rules on a question from `### For the owner`, post a dated comment on the pull request where the question sits, starting `Owner ruling, <YYYY-MM-DD>:`. It states the ruling, names the commit that applies it, and says which of the review's questions are settled and which are still open. A companion whose change follows from the ruling gets a comment naming the commit there.

A round's fixes are code no lens has read. When they changed what a rule says, such as a veto's fix or several must-fixes, run another round anchored at the fixing commit, from step 1.
