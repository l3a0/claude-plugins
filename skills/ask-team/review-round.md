# A pull request review round

The owner's rules ask that every pull request is reviewed by blind lenses before the owner reads it. A round of that review takes the same steps every time, and a session that works them out again pays for it in tokens. On 2026-11-03 review rounds on companion pull requests in three repositories worked out the brief, the lens prompts, the verifier grouping and the comment format again each time. This file holds that procedure.

`SKILL.md` stays the one definition of how roles are seated, prompted and verified, and of what a review comment must hold. This file adds what a round needs around those steps, and points to `SKILL.md` by step number rather than restating it:

- one brief that every lens reads,
- one round covering several companion pull requests,
- fixes applied to every companion,
- the order of pricing, posting and handover,
- the body's `## Revision` section and the owner's rulings.

The session that owns the branches runs the round, as the pull request review that lens mode names as its first caller. It runs `SKILL.md`'s steps 2 to 4 itself, in the same session, as lens mode allows, and launches the roles beside the completeness and over-reach lenses in one blind round.

A round can cover several pull requests at once. A rule adopted from one source often lands in three repositories, such as l3a0/ithildin-runtime, this plugin and l3a0/repo-template. One brief covers all of them, every lens reads all of them, and a finding that one copy contradicts another surfaces in the same round. The worked examples are the review comments on [l3a0/ithildin-runtime PR #25](https://github.com/l3a0/ithildin-runtime/pull/25), [PR #26](https://github.com/l3a0/ithildin-runtime/pull/26) and [PR #27](https://github.com/l3a0/ithildin-runtime/pull/27), with their companions [l3a0/claude-plugins PR #46](https://github.com/l3a0/claude-plugins/pull/46), [PR #47](https://github.com/l3a0/claude-plugins/pull/47) and [PR #48](https://github.com/l3a0/claude-plugins/pull/48), and [l3a0/repo-template PR #74](https://github.com/l3a0/repo-template/pull/74), [PR #75](https://github.com/l3a0/repo-template/pull/75) and [PR #76](https://github.com/l3a0/repo-template/pull/76).

1. Write the brief.
2. Choose the lenses.
3. Run the blind round.
4. Verify.
5. Apply the fixes to every pull request.
6. Price the round and decide whether another follows.
7. Post the review comment.
8. Record the revision and the owner's rulings.

## 1. Write the brief

Every lens reads one brief file, so each lens prompt stays a few lines long and every lens starts from the same facts. Copy `templates/review-brief.md` to `<scratchpad>/review-r<N>/brief.md`. The brief stays in the scratchpad and is never committed, because it names local checkouts and may name a copyrighted source.

Fill the subject list with the script beside this file, one argument per pull request:

```bash
python3 <this skill>/scripts/brief_anchors.py l3a0/ithildin-runtime#27=<checkout> l3a0/claude-plugins#48=<checkout>
```

It prints each pull request's head commit and the merge base its diff starts from, which it reads from GitHub's compare API rather than the base branch's tip. It flags a checkout whose `HEAD` is not the head commit, since a lens reading that checkout would review other code, and a pull request that is no longer open. Replace each `<What it changes.>` with the files and sections the pull request touches.

The template's sections say what else the brief holds: the facts every lens would otherwise spend turns finding, how to check a source, the limits every agent in the round works under, and what is out of scope. A source helper, such as one that prints the passage around a phrase at a location, comes with the source rather than with this skill.

A later round's brief anchors at the fixing commit and lists the owner's rulings since the last round as facts. It does not list the earlier rounds' findings, so each lens reads the change rather than a list of past answers.

## 2. Choose the lenses

Run the completeness and over-reach lenses `SKILL.md`'s step 2 names, as general-purpose agents, and seat the roles and the required seats by the same step. Each role runs as its own agent, with `subagent_type` set to `l3a0:team-<role>`. The 2026-11-03 rounds ran between five and eight lenses.

A round run this way follows lens mode's run limit, as `SKILL.md`'s lens mode says: the roles and the verifiers stay under ten runs, and the two lenses are the caller's own.

## 3. Run the blind round

Launch the lenses as `SKILL.md`'s step 3 says. Give each spawn a description starting with `review <tag> r<N> `, where the tag is the main pull request's number, such as `review 49 r1 risk-engineer`. The `l3a0:loop-cost` skill finds transcripts by that description once their paths are gone, and the tag keeps two subjects reviewed in one session apart.

A role's prompt carries the six things `SKILL.md`'s step 3 lists. The brief holds the subject, the charter, the files to read and what is out of scope, so the prompt names the brief's absolute path for those and adds the role's scratch folder, `<scratchpad>/review-r<N>/<role>/`. A completeness or over-reach prompt carries the same and its question. It also carries the finding format block from `SKILL.md`'s step 3 in full, and the limits in the brief written out, because a general-purpose agent has no agent file to supply them and holds every tool and the session's GitHub login. Every prompt asks for a reply under 1,500 words, with the evidence for each finding cut to the command and the line that shows it.

## 4. Verify

Read every finding together, and merge the ones that rest on the same fact into one, crediting each lens that raised it. A finding three lenses raised is still one finding, and the comment names all three.

Then verify by `SKILL.md`'s step 4, including its rule for grouping and its limit on what the session may check itself. On [l3a0/ithildin-runtime PR #25](https://github.com/l3a0/ithildin-runtime/pull/25) one verifier reran the lenses' scripts, one read the owner's rulings on the issue tracker, and one checked citations against the source. Describe each verifier `review <tag> r<N> verify <topic>`, give it the brief's path, and write out the brief's limits in its prompt. Each returns one verdict per finding.

1. **CONFIRMED**, with the command and its output.
2. **REFUTED**, with what it ran that shows the claim false.
3. **PARTLY**, with which part held.

With each verdict it gives the kind the finding deserves and the smallest fix. A verdict can lower a finding's kind as well as refute it. One round on [l3a0/ithildin-runtime PR #26](https://github.com/l3a0/ithildin-runtime/pull/26) lowered three must-fixes to should-fix, because something the repository already held covered each one, such as a hard limit or mutation testing. The comment then gives the lower kind and what lowered it.

Should-fixes and notes get no verifier. The session reads each one, applies it when it is cheap and inside the change's scope, and otherwise lists it as left alone with the reason. Work outside the pull request's scope is filed as its own issue and linked under `### Left alone`. A question only the owner can rule on, such as one `SKILL.md` sends to the board or a change to a role's vetoes, goes under `### For the owner`.

## 5. Apply the fixes to every pull request

Before editing, write down for each surviving finding which of the pull requests carry what it is about. A rule that lands in three repositories is fixed in all three, or the next round's completeness lens finds the copies disagreeing. The wording can differ by repository, such as a plugin's role check dropping a trading platform's names and citations, but what the rule says matches.

1. Apply the fixes on each pull request's branch, in its own checkout.
2. Where the change cites a source, recheck every citation against it with the brief's helper, whether or not a lens flagged it, and list each miss.
3. Where the fixes change code, show the test catches what it claims by breaking the code, with the `fast-mutation` skill or a fixture the code fails on before the fix.
4. Run every check the repository's CI workflow runs, such as this repository's `.github/workflows/board-guard-test.yml`, and note what each printed.
5. Commit, naming in each message the round it answers, and push.
6. Watch the pull request's checks until they settle, with `gh pr checks <n> --watch`, and fix any red one before posting.

## 6. Price the round and decide whether another follows

Price the round before posting, so each comment goes out once and complete. Run the plugin's `l3a0:loop-cost` skill over the transcripts of this round's lenses and verifiers, found by the `review <tag> r<N>` descriptions. Give the lenses and the verifiers a line each and then their sum. Price any other loop that served the round on its own line, such as agents that read a source for the change. List only loops this round ran. An earlier round's figures were already posted, and repeating them would count them twice in the `## Cost total` that sums every `## Cost` comment. That is why a round's figures say "this round" where the `l3a0:loop-cost` skill's handover comment says "to date". Main-thread checks run in the session's own context, which these figures leave out, so the comment says so when step 4 used them.

Then decide whether another round follows. A round's fixes are code no lens has read. When the round confirmed a veto, plan another round anchored at the fixing commit, from step 1. A round that confirmed no veto is the last, and so is a third round, after which the owner decides whether to go on. This departs from the 2026-11-03 rounds, where only [l3a0/ithildin-runtime PR #25](https://github.com/l3a0/ithildin-runtime/pull/25) ran a second round. A veto still blocking at the last round leaves the review open: the comment takes the heading for a round that is not the last, and the handover waits for the fix or the owner's written override.

## 7. Post the review comment

Before posting, check that each pull request's head is the commit the comment will name, with `gh pr view <n> -R <repo> --json headRefOid`. That is the fixing commit, or the anchor where the round fixed nothing on that pull request. On any mismatch, post nothing on any of the companions until it is resolved. Read each pull request's comments first too, and skip one that already carries this round and anchor, so a retried post does not land twice.

Post one comment on each pull request, from `templates/review-comment.md`. On the round step 6 named the last, the first line is the heading `SKILL.md`'s step 6 gives for a final comment. On an earlier round it is `## Review, round <N>`, which a board that reads only the final heading does not count, so the card does not reach the owner while another round is planned. The comment holds the four parts `SKILL.md`'s step 6 lists, laid out as the template's sections. A quoted command uses a path relative to the repository or a placeholder such as `<scratch>`, never an absolute local path, because the comment is public.

One pull request is the main one, where the change starts, such as the l3a0/ithildin-runtime pull request whose rules the plugin's role checks carry. Its comment holds the questions for the owner and the full cost. Each companion's comment lists the findings fixed there, says where the owner's questions sit, and gives the cost in one line pointing to the main pull request. Where the pull requests track issues, post the `## Cost` comment `SKILL.md`'s step 6 asks for on the main pull request's issue alone. Its first line after the heading is `Review round <N>, of <anchor>, on <pull request link>`, and before posting the session reads the issue's comments and skips the post when one already carries that line. Each companion's issue gets a one-line pointer that does not start with `## Cost`, so a `## Cost total` never reads it. A companion built in its own session still posts its own build's cost on its own issue. None of the worked examples tracked an issue, so this branch has not yet run.

After each round's comment, run the `update-build-board` skill's moment 5 for each pull request on a board. Run its moment 4, the handover, only after the last round. Moment 4's `## Cost` comment is the last round's own, not a second one, so on that round add the build's line to it when the session also built the change. Each `## Cost` comment then counts each loop once, which is what a `## Cost total` needs.

## 8. Record the revision and the owner's rulings

The pull request body keeps a `## Revision` section, with one numbered line per round. Each line names the fixing commits, the round and anchor they answer, and in a sentence what changed. It ends by saying the review comments list each finding and what was refuted. Update it on every pull request the round fixed, and write no line on one it did not change. Re-read the body just before `gh pr edit --body`, and change only this round's line, so an edit the owner made meanwhile survives. Find the line inside the `## Revision` section, between its heading and the next heading or the body's end, and never with a pattern run over the whole body, because the body's other numbered lists use the same numbers. In round 3 on [l3a0/ithildin-runtime PR #28](https://github.com/l3a0/ithildin-runtime/pull/28), a regular expression that replaced the first line starting `2. ` overwrote item 2 of the `## What` list on both companions, and round 4 restored them from GitHub's edit history.

An owner's ruling on a question from `### For the owner` sits where the owner wrote it, on the issue when there is one, as `SKILL.md` says. Post a comment on the pull request where the question sits, starting with the date, such as `Owner ruling, <YYYY-MM-DD>:`. It links the owner's own words, or says it is relayed from the owner's chat of that date, names the commit that applies the ruling, and says which of the review's questions are settled and which are still open. A companion whose change follows from the ruling gets a comment naming the commit there. Before either post, read the pull request's comments and skip it when one already carries that date and commit.
