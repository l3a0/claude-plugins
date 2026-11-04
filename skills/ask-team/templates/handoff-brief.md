# Handoff brief: finish a review in a new session

<!-- A new session reads only this brief. Fill every angle-bracket field, and delete a line that does not apply.
     review-round.md's opening says when to use it. -->

Finish the review of <the pull request, or the count of pull requests and what they share>.

1. <owner/repo PR #N>, <which closes #N, part of #N, or which closes no issue>, branch `<branch>`, head `<sha>` when this was written.

State when this brief was written, to verify rather than trust: <each pull request's last review comment, its time, and whether it says another round follows. What merged since, and what each pull request's merge state reads.>

<Each owner's ruling that binds the work, with a link to where the owner wrote it. Take a ruling only from there, never from a commit headline or an earlier brief.>

Before pushing anything, check whether a session already owns this work. <The session's title and worktree, where known.> `list_sessions` does not show every live session, so judge from the branches' recent pushes and comments too. If it is still reviewing, message it or report to the owner rather than running a second review over it.

What to do:

1. Bring each branch up to date with its `main`. <In l3a0/claude-plugins, run `python3 scripts/next_version.py --pr <n>` after the merge, and keep or move the version as it says.>
2. <What a merge changed underneath this work, and what to sweep for.>
3. Run each further round by the ask-team skill's `review-round.md`, across the pull requests together.
4. Continue until `review-round.md`'s step 6 ends the review.

Out of scope: <other pull requests, other repositories, and work another session holds, each with its link.>

Done looks like: the last review comment on each pull request carries the final heading the ask-team skill's step 6 gives, the checks are green at the current head and re-read after any base move, no branch conflicts with its `main`, and the cost is reported. A session whose lenses are still running has not finished, so it posts nothing as final until they report. The report says what the review found, what it refuted and any question left for the owner. Do not merge, because the owner merges.
