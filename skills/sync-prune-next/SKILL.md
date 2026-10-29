---
name: sync-prune-next
description: Sync with origin, prune the worktrees and branches whose work is finished, check the repository's build board, and recommend what to take next. Use when asked to "git sync prune", to clean up worktrees or branches, to "update the build board and say what's next", or for any status round of a repository's sessions and pull requests.
---

# Sync, prune, and say what's next

Many sessions work on one repository at once, each in its own worktree, so the checkout fills with worktrees and branches whose work has merged. Removing them keeps the list readable. Removing the wrong one loses work nobody pushed, and that cannot be recovered. So most of this skill is about telling the two apart from evidence rather than from a branch name or a session title.

This skill is the union of four copies that had drifted apart, each read at its repository's `main`, and [l3a0/claude-plugins#28](https://github.com/l3a0/claude-plugins/issues/28) carries the inventory that maps every capability of each copy to a section here.

1. `.claude/skills/sync-prune-next/SKILL.md` in l3a0/quantitative-trading at `0237abf`, the original.
2. The same file in l3a0/repo-template at `9c6d7e2`, generalised so its commands read the repository from `gh`.
3. The same file in l3a0/ithildin-runtime at `3c2242c`, the template's copy at `4bb3f7f` with an `## In this repository` section.
4. The same file in l3a0/marketlake at `16666cb`, which tests merged work by a pull request's head ref, checks the board's page, and posts the cost totals a merge leaves owed.

The `update-build-board` skill in this plugin says what a session sets on GitHub for the board to read, which setup a repository runs, and how to build the board. This skill reads what it says rather than repeating it.

The round has four steps, and they run in this order because each feeds the next.

1. Fetch and prune, so every later check reads the current `main`.
2. Remove what is finished, and only that.
3. Check the build board.
4. Recommend what to take next.

Each Bash tool call starts a new shell, so run this line in the same call as any command below that uses `$REPO`.

```bash
REPO="$(gh repo view --json nameWithOwner --jq .nameWithOwner)"
```

## 1. Fetch and prune

```bash
git fetch --prune origin && git log --oneline -6 origin/main
git worktree list
```

The log shows what merged since the last round, which is what moves the board, and in a repository with blog posts, what can make a Substack draft stale.

`--prune` deletes every ref under `refs/remotes/origin/` that has no branch behind it on GitHub, including one made there by hand. So after this step, every ref under `refs/remotes/origin/` names a branch GitHub holds. When the repository's `delete_branch_on_merge` setting is on, GitHub deletes a pull request's branch as it merges, so a merged pull request's `origin/<branch>` goes at this step, and step 2 cannot lean on it. Check 3 below then rarely finds a merged commit on a remote branch, and the merged pull request's own record is what proves it safe. `## In each repository` below says which repositories have the setting on.

The setting does not reach back. The branches of pull requests that merged before it was turned on stay on GitHub, and so does a branch whose pull request closed unmerged. Deleting those is the owner's call, and this skill leaves them alone.

Fast-forward the main checkout only when it is clean and on `main`, since a session may be using it. `git -C` keeps the shell where it is, which matters because the Bash tool keeps a `cd` for every later command.

```bash
M=$(git worktree list | head -1 | cut -d' ' -f1)
[ "$(git -C "$M" branch --show-current)" = main ] && [ -z "$(git -C "$M" status --porcelain)" ] && git -C "$M" merge --ff-only origin/main
```

**When the main checkout is also the code a daemon runs**, a fast-forward on its own is half a deploy. A deploy is a fast-forward there followed by a restart. A calendar job starts fresh and runs the new code, while a resident job keeps the code it imported at start. Restarting is the owner's step and never the round's, so say in the report that the checkout moved, so the owner knows a restart is owed. In l3a0/marketlake the restart runs the restart script that `python -m lake.control_plane render --out <dir>` writes, and that script needs root.

## 2. Remove what is finished, and only that

A worktree is removable only when all five of these hold.

1. **It is not the worktree this round runs in.** `list_sessions` leaves out the current session, so nothing else protects it, and git removes a worktree from inside it without complaint. Compare against `git rev-parse --show-toplevel`.
2. **No unarchived session has it as its `cwd`.** Read `cwd`, not `branch`. `branch` is the branch a session started on, and a session that switched branches reports one it no longer uses. Read `isRunning` as no evidence either way. An open session between turns reports `false`, and so does one waiting on its own background sub-agents. Pass a `limit` above the default of 20 so no session is missed.
3. **Its `HEAD` commit is safe.** Test the worktree's `HEAD` itself, not only its branch, because a worktree with no branch checked out holds commits that no branch names. The commit is safe when `origin/main` contains it, when a branch on `origin` contains it, or when a merged pull request still holds it on GitHub. The text before the loops below says what counts as each and which refs do not.
4. **It holds no uncommitted changes.** `git status --porcelain` is empty. That listing omits ignored files, which `git worktree remove` deletes silently. `--ignored` shows them. Caches such as `.venv/` and `.pytest_cache/` are expected, and anything else is a reason to keep the worktree.
5. **It is not locked.** `git worktree list --porcelain` prints `locked` with a reason for a sub-agent's worktree. The pid in that reason belongs to the host session's `claude` process, not to the agent, so a live pid shows only that the host is alive. Leave a locked worktree alone. If its pid is gone and the other checks pass, `git worktree unlock` it first, because `git worktree remove` refuses any locked worktree.

`isRunning` cost something once already. On 2026-10-05 UTC the session building [l3a0/quantitative-trading#335](https://github.com/l3a0/quantitative-trading/issues/335) reported `isRunning: false`, and its branch sat at `main` with no commits of its own. Its worktree held seven modified files. Minutes later it opened [l3a0/quantitative-trading PR #369](https://github.com/l3a0/quantitative-trading/pull/369) from that branch, and the files turned out to be review fixes in progress. Check 4 is what kept the worktree.

The same evidence does not show that work has stalled. Before reporting a session as stuck, re-run `gh pr list --state open --limit 1000` and read its latest events with `list_events`, because a pull request may have opened since the worktree was classified.

### What counts as safe

**Only refs GitHub backs count for check 3.** After step 1, every ref under `refs/remotes/origin/` names a branch on GitHub. When `origin` is the checkout's only remote, a ref elsewhere under `refs/remotes/` was made locally, for example by `git fetch origin pull/N/head:refs/remotes/pr/N`, and proves nothing. Yet `git branch -r --contains` lists it like any remote branch, so both loops keep only that command's `origin/` lines. On 2026-10-07 l3a0/marketlake's checkout held five such refs, among them `refs/remotes/pr/492` and `refs/remotes/audit/pr697`, and [l3a0/marketlake#758](https://github.com/l3a0/marketlake/issues/758) found 34 clean worktrees whose only evidence was a ref like these. If a second remote is ever added, add its prefix beside `origin/` in both loops, or the round treats that remote's refs as unbacked.

**A merged pull request still holds its commits.** Squash merges make this case common, because the branch's commits never reach `main`, and deleting the branch on merge leaves no remote branch to contain them either. GitHub keeps every commit of a merged pull request, and keeps `refs/pull/N/head` for every pull request through the merge and the deletion of its branch. So any of its commits is safe, not only the head. That matters for a review lens's worktree detached at an earlier commit of the pull request, or a sub-agent's branch left there. On 2026-10-10 GitHub deleted the branches of [l3a0/quantitative-trading PR #433](https://github.com/l3a0/quantitative-trading/pull/433) and [l3a0/quantitative-trading PR #447](https://github.com/l3a0/quantitative-trading/pull/447) as they merged. Five sub-agent worktrees there sat at earlier commits of the two, such as `d88745a` in the first, whose head is `886754e`. After the next prune no remote branch contained them, and a test of the head alone would have kept all five.

The round runs two tests for this case, and a commit that passes either is safe.

1. **Membership in the commit list.** Exact comparison against the commits GitHub lists for each merged pull request, which l3a0/quantitative-trading and l3a0/repo-template's copies used.
2. **Ancestry against the head ref.** Whether a merged pull request's `refs/pull/N/head` reaches the commit, which l3a0/marketlake's copy used. A ref keeps every commit it reaches, so removing a worktree on any of them loses nothing.

Each covers a gap in the other. The list reads only the first 250 commits of each pull request, and the ancestry test reaches all of them. The ancestry test needs a fetch of every merged head, which can fail as a whole, and the list still runs then. Both refuse the same two cases, and must.

1. A commit force-pushed out of a pull request. The final head does not reach it, the list no longer names it, and GitHub may collect it.
2. A commit made on a worktree after the pull request's last push, or an amended or rebased copy of one of its commits, whose sha differs. Nothing on GitHub holds it.

Check 4 still catches uncommitted files.

**Never test this case with a search.** `gh pr list --search <sha>` matches a pull request that only mentions the sha in its text. `b27222b`, a commit in a sibling repository that l3a0/quantitative-trading does not hold, matched five merged pull requests there on 2026-10-10. On 2026-10-07 in l3a0/marketlake, `gh pr list --state merged --search 60ef88e` returned [l3a0/marketlake PR #646](https://github.com/l3a0/marketlake/pull/646), whose head ref reaches that commit, and [l3a0/marketlake PR #661](https://github.com/l3a0/marketlake/pull/661), whose head ref does not. The second matched only because a comment on it quotes the hash. A search reads text, while both tests ask whether something GitHub keeps still holds the commit.

### Fetch the merged pull requests once

Both tests need the merged pull requests. Fetch them once into files, so both loops below read the same ones. A shell variable would not reach the second loop, because each Bash tool call starts a new shell. Replace `<scratch>` with the round's scratch directory in this block and the two loops after it.

The commit list:

```bash
REPO="$(gh repo view --json nameWithOwner --jq .nameWithOwner)"
MERGED="<scratch>/merged-commits.txt"
gh api graphql --paginate -f owner="${REPO%%/*}" -f name="${REPO#*/}" -f query='query($owner: String!, $name: String!, $endCursor: String) { repository(owner: $owner, name: $name) { pullRequests(states: MERGED, first: 100, after: $endCursor) { pageInfo { hasNextPage endCursor } nodes { headRefOid commits(first: 250) { nodes { commit { oid } } } } } } }' --jq '.data.repository.pullRequests.nodes[] | .headRefOid, .commits.nodes[].commit.oid' | sort -u > "$MERGED"
wc -l < "$MERGED"
grep -cvE '^[0-9a-f]{40}$' "$MERGED" || true
```

`gh pr list --json commits` cannot fetch this list. It asks for each commit's authors too, and on 2026-10-10 GitHub refused that query for exceeding 500,000 possible nodes at any limit of 50 or more. The query above pages through 100 pull requests at a time, so no limit can cut it short. It reads the first 250 commits of each pull request, and prints each head on its own line as well, so a longer pull request loses only its later commits from the list and never its head. The longest merged pull request in l3a0/quantitative-trading had 70 commits on 2026-10-10.

Every way this fetch can fail leaves the list shorter, and a shorter list only keeps more worktrees. A failure does not always leave the file empty, though. When GitHub rejects the query, `gh` writes the error as one line of JSON, and `--jq` never runs. So the block prints two counts.

1. The first is the number of commits read. It is 0 only in a repository with no merged pull request, and in l3a0/quantitative-trading it is in the hundreds.
2. The second is the number of lines that are not a full sha, and it should be 0.

Anything else means the fetch failed, and the loops would then keep every worktree that is not on `main` or a remote branch, unless the head refs below prove it safe.

The head refs:

```bash
REPO="$(gh repo view --json nameWithOwner --jq .nameWithOwner)"
MERGEDPRS="<scratch>/merged-prs.txt"
gh pr list --repo "$REPO" --state merged --limit 1000 --json number --jq '.[].number' > "$MERGEDPRS"
wc -l < "$MERGEDPRS"
git for-each-ref --format='delete %(refname)' refs/pr-heads/ | git update-ref --stdin
[ -s "$MERGEDPRS" ] && { sed 's#.*#+refs/pull/&/head:refs/pr-heads/&#' "$MERGEDPRS" | git fetch --quiet --stdin origin || echo "FETCH FAILED: rerun before removing anything"; }
```

A count of exactly 1000 means `gh` cut the list, so raise the limit and fetch again. A count of 0 means either that `gh` failed or that the repository has no merged pull request, and the block then fetches nothing, because with no refspecs on its input `git fetch --stdin` falls back to the configured refspec and prints no failure. Check which it is before trusting the loops' `merged-pr/` column.

The fetch writes each head to `refs/pr-heads/N`, outside `refs/remotes/`. `git branch -r` lists everything under `refs/remotes/`, so heads fetched there would read as remote branches and rebuild the trap above.

The block deletes every ref under `refs/pr-heads/` before it fetches, because a head left by an earlier fetch can be stale. One fetched while its pull request was open still reaches any commit a later force-push dropped, and the loops' merged-number filter accepts it once the pull request merges. One missing ref on GitHub aborts the whole fetch, which then writes nothing, so without the delete every stale head would survive a failed fetch. With it, a failed fetch leaves no heads, and the ancestry test finds nothing rather than something false. The `+` on each refspec is a second guard. It lets the fetch overwrite a head the delete missed, where git would otherwise refuse to move a ref to a commit that does not descend from it.

If the fetch fails, find why and rerun the block before removing anything. The loops would report no worktree safe through a head ref, which loses nothing but tells the owner less than the round could.

### The loops

This prints what checks 3 to 5 need for every worktree.

```bash
MERGED="<scratch>/merged-commits.txt"
MERGEDPRS="<scratch>/merged-prs.txt"
git worktree list --porcelain | sed -n 's/^worktree //p' | while read -r w; do
  if ! h=$(git -C "$w" rev-parse HEAD 2>/dev/null) || [ "$(git -C "$w" rev-parse --show-toplevel 2>/dev/null)" != "$w" ]; then
    echo "$w unreadable, skipped"; continue
  fi
  safe=$( { git merge-base --is-ancestor "$h" origin/main && echo main; } || git branch -r --contains "$h" | grep -e '^ *origin/' | head -1 | tr -d ' ')
  grep -qxF "$h" "$MERGED" && safe="$safe merged-pr"
  pr=$(git for-each-ref --contains "$h" --format='%(refname:lstrip=2)' refs/pr-heads/ | grep -xF -f "$MERGEDPRS" | head -1)
  [ -n "$pr" ] && safe="$safe merged-pr/$pr"
  echo "$w head=${h:0:7} branch=$(git -C "$w" branch --show-current) safe=[${safe}] dirty=$(git -C "$w" status --porcelain | wc -l | tr -d ' ') ignored=$(git -C "$w" status --porcelain --ignored | grep -c '^!!')"
done
git worktree list --porcelain | grep -B3 '^locked'
```

`merged-pr` is the list test, and `merged-pr/N` is the ancestry test against pull request N. `git for-each-ref --contains` runs the ancestry test of `git merge-base --is-ancestor` against every fetched head in one call, rather than one process per head. The `grep -xF -f "$MERGEDPRS"` keeps only the merged numbers, so an open pull request's head that someone fetched into `refs/pr-heads/` does not count.

A worktree printed as unreadable usually has a directory that is gone or a `.git` file that is broken. Git cannot reach its files, so check 4 cannot pass, and the loop skips it rather than test an empty commit. Report it as kept. Before this guard, an empty `HEAD` reached `gh pr list --search ""`, which returns the most recently created merged pull request, so the line called an unchecked worktree safe.

The `--show-toplevel` comparison catches a quieter case. Worktrees can sit inside the main checkout, so a worktree directory with no `.git` file at all resolves to the main checkout, and without the comparison it reports the main checkout's `HEAD` as its own. The comparison also flags a worktree registered under a path whose letter case differs from the one on disk. Nothing is lost by keeping that one, so it is still reported as kept.

A `fatal:` or `warning:` line from the loop means some check could not run. A corrupt index, for one, makes `git status` fail and the line print `dirty=0`. Keep any worktree whose line came with one.

A branch checked out in no worktree is removable when check 3 holds for its head. Git refuses to delete a branch that a worktree has checked out, which protects every branch in use. The loop also lists, by full name, each ref under `refs/remotes/` outside `origin/`, such as `refs/remotes/pr/492`, since nothing on GitHub backs it. This loop runs the same tests as the one above. Matching on the branch name instead, with `gh pr list --head <branch>`, finds a pull request only when the local branch name equals the one it was pushed under.

```bash
MERGED="<scratch>/merged-commits.txt"
MERGEDPRS="<scratch>/merged-prs.txt"
{ git branch --format='%(refname:short)' | grep -v -e '^main$' -e '^(HEAD' -e '^(no branch'
  git for-each-ref --format='%(refname)' refs/remotes/ | grep -v -e '^refs/remotes/origin/'
} | while read -r b; do
  h=$(git rev-parse "$b")
  safe=$( { git merge-base --is-ancestor "$h" origin/main && echo main; } || git branch -r --contains "$h" | grep -e '^ *origin/' | head -1 | tr -d ' ')
  grep -qxF "$h" "$MERGED" && safe="$safe merged-pr"
  pr=$(git for-each-ref --contains "$h" --format='%(refname:lstrip=2)' refs/pr-heads/ | grep -xF -f "$MERGEDPRS" | head -1)
  [ -n "$pr" ] && safe="$safe merged-pr/$pr"
  echo "$b ${h:0:7} ahead=$(git rev-list --count origin/main.."$h") safe=[${safe}]"
done
```

When the loop runs from a worktree with no branch checked out, `git branch` adds a line for that worktree's `HEAD`. The line usually reads `(HEAD detached at <sha>)`. It reads `(no branch)` instead when the `HEAD` reflog does not record the detach, which is what `git worktree add --detach` leaves. It reads `(no branch, rebasing <branch>)` during a rebase and `(no branch, bisect started on <branch>)` during a bisect. The `^(HEAD` pattern misses all three, so the third pattern removes them.

Write one `-e` per pattern rather than joining them with `\|`. macOS's `/usr/bin/grep` reads the `$` before `\|` as a literal character, so the joined form keeps `main` in the list, and `main` then reads as safe to delete.

### Remove, and report

Remove with the commands that refuse to lose work. `git worktree remove` without `--force` refuses a worktree holding modified or untracked files, and that refusal is a check worth keeping. Use `git branch -D` only on a branch whose head passed check 3. A name the branch loop printed with the `refs/remotes/` prefix is a ref, not a branch. Delete it with `git update-ref -d` on the same evidence, and keep and report one whose commit fails check 3.

```bash
git worktree remove <path>
git branch -D <branch>
git update-ref -d <refs/remotes/...>
git worktree prune --dry-run -v
```

Run `git worktree prune` only when that dry run names no worktree the loop printed as unreadable. Prune deletes git's record of every worktree whose directory or `.git` file is gone, which is most of what the loop calls unreadable. That record holds the worktree's `HEAD` and its reflog, and while it exists git counts that `HEAD` as reachable. Once it goes, an unpushed commit on a detached `HEAD` there belongs to no branch and no reflog, and `git gc` may delete it. A branch whose worktree was pruned also loses its protection, so `git branch -D`, which refused it before the prune, deletes it after. So leave those records for the owner, and say so in the report.

Archive a finished session only when the owner has asked for it in this conversation. Archiving stops the session and is the owner's call, even when the board says its loop exited.

Report what was removed, and what was kept with the reason for each. Include stash entries from `git stash list`, which survive every removal above and which nothing else surfaces. The kept list is where the owner learns about work in progress that nothing else announces, such as the worktree check 4 kept.

## 3. Check the build board

A GitHub Action rebuilds the board from GitHub on every change, so a round writes nothing to it. Run the setup block in the `update-build-board` skill's `## Which board this repository runs` first, so `$BOARD`, `$GEN` and `template` are set in the same call as the commands below. The step runs in this order.

1. It starts a run of the Action.
2. It checks that the Action's last finished run succeeded.
3. It builds the same `board.json` into a scratch directory, so step 4 reads GitHub as it stands rather than as the last run saw it.
4. It reports what that build listed, any marker a session left unset, and any stale `working:` label.
5. It confirms the page drew the published board.

### Start a run, and check the last one

The round starts a run first because GitHub's schedule is unreliable. l3a0/marketlake's schedule fired none of that workflow's first four due slots on 2026-10-12, and its copy recorded a sibling board measuring one scheduled run in about 25 due slots. l3a0/quantitative-trading's fired in about 11% of its slots over 185 hours. A run takes 25 to 62 seconds, so a check of the page made straight after starting it reads the previous board. Building locally in between gives the run that time. The run deploys to the `github-pages` environment, which has a branch policy and no required reviewers, so starting it approves nothing.

```bash
gh workflow run board.yml --repo "$REPO"
gh run list --repo "$REPO" --workflow board.yml --event workflow_dispatch --limit 1 --json databaseId,status,createdAt,url
```

The second command shows the newest dispatched run. A new run takes a few seconds to appear, so a `createdAt` older than the dispatch means it printed the previous dispatch. Run it again until the new run shows. `gh workflow run` may ask for permission each round, because no allow rule covers it in some repositories. Say so in the report if it does.

This prints the board workflow's newest finished run that was not cancelled.

```bash
gh run list --repo "$REPO" --workflow board.yml --status completed --limit 20 --json databaseId,conclusion,createdAt,event,url --jq 'map(select(.conclusion != "cancelled"))[0]'
```

A cancelled run is normal, so the command reads past it. The workflow's `pages` concurrency group replaces a waiting run with a newer one, and l3a0/marketlake's copy recorded that 111 of a sibling board's last 300 runs ended `cancelled` that way. A run whose `conclusion` is not `success` goes in the report as a link, written `[run <databaseId>](<url>)`. Pages keeps the last good board while runs fail, so the page then shows GitHub as it stood before the failure. An output of `null` means every one of the last 20 finished runs was cancelled, so raise `--limit` and run it again. Where the page has a stale banner, also report a stamp older than the page's stale threshold, `staleAfterMinutes`, with a link to the run. l3a0/marketlake's page has none yet, so there a board that is stale rather than failed goes unreported until [l3a0/marketlake#874](https://github.com/l3a0/marketlake/issues/874) lands.

Nothing in a round waits on a suite run, because no board carries a test count. l3a0/quantitative-trading's board stopped carrying the commit, the test count and the vintage counts on 2026-10-05 UTC.

### Build the board into scratch

Build it with the build command in the `update-build-board` skill's `## Where the board lives`, which removes any `board.json` an earlier build left in the scratch directory first. In the shared setup that build fetches the generator from l3a0/repo-template at the ref the repository pins. A failed build exits non-zero before it writes `board.json`. Report the failure, and step 4 then reads the last board the workflow published, and reads the open pull requests again from GitHub.

### Report what the build found

What a build prints is the only place a round sees these, because nobody reads the Action's own job summary. Report every row that does not read `none`, with each issue linked.

- **Markers that disagree.** Two `band:N` labels, both `working:` labels, read as `build`, two kinds, or a body carrying several `Board order:` lines, read as the first. Every generator lists these, except that l3a0/marketlake's lists no kind conflict.
- **Marker lines not read.** A line of the owner's that looks meant as a marker and is not read. l3a0/marketlake's generator lists these.
- **Marker lines refused.** A marker in text the owner did not write, a `Board after:` reference to another repository, or a `Board after:` link whose text and address name different issues. l3a0/marketlake's generator lists these.
- **Markers dropped.** A verdict or an order on a parent, or a verdict on a deferred card. l3a0/marketlake's generator lists these.
- **Finished plans with no verdict after them.** An open issue with no `working:decompose` label whose newest owner `## Plan audit, pass N` heading comes after its newest owner verdict, in a later comment or lower in the same one, or that has passes and no verdict at all. Parents, deferred cards and cards with an open pull request are left out. Each is a plan loop that ended without saying so. l3a0/marketlake's generator lists these. An exit comment headed as the last pass and ending with the verdict is not listed.

A row names the issue and the marker's kind and never the line's text, so read the issue for the line itself. The `update-build-board` skill's `## The markers and their grammar` states the grammar and which lines count as meant for a marker.

Where the generator does not list them, check these by hand against what the round found since the last one.

- A decompose loop that exited since the last round owes its issue a `Board verdict:` line. Report any that is missing.
- A filed issue that is ranked owes a `band:N` label where the generator reads bands. Report any that is missing.
- The board's kind labels are owed only where one applies, per moment 6 in the `update-build-board` skill, so a card without one is not missing anything.

### Report a stale `working:` label

A `working:` label is owed its removal by the session that set it, so report a stale one rather than removing another session's label. A label that outlives its session keeps its card under Building or Being planned. A build session keeps `working:build` until it hands its pull request over, so a label on a card with an open pull request also keeps that card out of the owner's queue. GitHub cannot tell a live session from an ended one, and every label's actor is the owner, because sessions act as the owner. So the round reads two triggers, each on its own. The labels are the `working` entries of `<scratch>/board.json`.

```bash
jq -c '(.working | if type=="object" then .items else . end)[]' <scratch>/board.json
```

The shared and l3a0/quantitative-trading generators wrap each section as `{"schema": 1, "items": [...]}`, and l3a0/marketlake's writes a bare list, so the filter unwraps either. Read `prs`, `planned` and `next` the same way in step 4.

1. **No session names the issue.** List the sessions with the session-listing tool, and keep the unarchived ones whose `cwd` is under this repository. Flag `working:*` on #N when none of them names #N in its title or carries a `prNumber` whose pull request links #N. Read a pull request's links with `gh pr view <pr> --repo "$REPO" --json closingIssuesReferences,body`.
2. **Its pull request finished after the label went on.** Flag `working:build` on #N when no open pull request names #N, in `prs` of `<scratch>/board.json` filtered to `state == "open"`, since the shared and l3a0/quantitative-trading generators keep merged and closed entries there, and a pull request that closes #N or is `Part of` #N merged or closed after the label was added. Without that time gate, a new build of an issue's remainder would read as stale before its pull request exists. These print the time the label was added, the pull requests that close #N, and those whose body names it as `Part of`.

   ```bash
   gh api graphql -f owner="${REPO%%/*}" -f name="${REPO#*/}" -F n=<N> -f query='query($owner:String!,$name:String!,$n:Int!){repository(owner:$owner,name:$name){issue(number:$n){timelineItems(itemTypes:[LABELED_EVENT],last:100){nodes{... on LabeledEvent{createdAt label{name}}}} closedByPullRequestsReferences(first:50,includeClosedPrs:true){nodes{number state closedAt}}}}}' --jq '{labeled: [.data.repository.issue.timelineItems.nodes[] | select(.label.name == "working:build") | .createdAt] | last, closing: .data.repository.issue.closedByPullRequestsReferences.nodes}'
   gh pr list --repo "$REPO" --state all --limit 1000 --search '"Part of #<N>" in:body' --json number,state,closedAt
   ```

   The search matches loosely, so confirm a `Part of #N` reference in the body of any pull request it returns before counting it.

Before calling a label stale, ask the session that owns it, when one exists, through the session-messaging tool. Report a stale label, and never remove one. Removing it is the owning session's step, or the owner's. Neither trigger has a test. The first needs the session list, which CI cannot see, and the second needs closed pull requests and label timelines, which no generator fetches. The rule misses sessions on another machine and finished sessions nobody archived.

### Confirm the page drew it

A green run proves the workflow published the files. It does not prove the page drew them, because a page that refuses a document shows only a banner. So open `https://<owner>.github.io/<name>/` and read what it drew.

1. **Read the page's text.** Pages serves the board as an ordinary page rather than inside a frame, so a browser tool's text extraction reads it. On a page drawn from live data, the banner under the strip is empty. On l3a0/marketlake's page the footer also names the `main` sha the board was built against.
2. **Look under every selector the page has.** l3a0/marketlake's page filters by milestone and defaults to "MVP 2", so check the cards under "MVP 2", then again under "All". Bugs that can lose a captured minute and bugs in an alarm carry no milestone there, so they never draw under the default.

## 4. Recommend what to take next

Read `<scratch>/board.json`, the file step 3 built, rather than the page, which can be a run behind. The ranking directive in the repository's `CLAUDE.md`, and its exceptions, decide the order. Read them there rather than from a copy here.

The file's `next` section stores the order, from each issue's `band:N` label, where the generator reads bands, and its `Board order:` line, so read it rather than re-deriving it. Sort it as the page does, which is `NEXT_SORTED` in the `update-build-board` skill's data section: by band, then by `order` with 50 where a card has none, then readiness, then number. Under l3a0/marketlake's generator every band is 0, so that is `order`, lowest first. Skip a `next` entry whose card is `deferred`, as the page does, so the round never recommends a card the page hides. Then rank the open issues `next` leaves out by the directive itself, after the ranked ones. When `next` is empty, the directive ranks everything, and the report says nothing is ranked.

When step 3 could not build the file, read the last board the workflow published instead, and print the time it read GitHub.

```bash
curl -fsS "https://${REPO%%/*}.github.io/${REPO#*/}/board.json?t=$(date +%s)" -o <scratch>/board.json
jq -r .state.updatedAt <scratch>/board.json
```

The `t` parameter asks for a URL no cache has seen, because Pages tells caches to keep `board.json` for ten minutes. Report the `updatedAt` time, because the file is as old as the workflow's last good run. Read its tracker as it is. Then read the open pull requests, their checks and their review markers again straight from GitHub, rather than trust the file's `prs`. Pass `--limit 1000` to every `gh` list command that feeds a candidate, because `gh` stops at its limit without a warning and its default is 30. A cut list prints the same way a complete one does.

Collect candidates from these places, and give the evidence for each one.

1. **The owner's queue.** Nothing moves until the owner answers, so these come first.
   - Pull requests that are reviewed, green at the current head, and whose card carries no `working:` label, other than one step 3 reported stale. A `working:decompose` label holds a card back as surely as `working:build` does, because the page counts any session as one the branch still owes. Green means what the repository's generator says it means, which the `update-build-board` skill's data section gives. Green does not count when the base moved after the last push, as the paragraphs after this list explain. When the card's `needs` names an issue still open, or its `after` names one, the owner can review now but may not be able to merge, so name each open blocker rather than present the pull request as ready to merge, as the board's In flight note does.
   - `planned` entries with `ready` of `decide`.
   - Questions a session handed back.
2. **Plans ready to build with no builder.** These are `planned` entries with `ready` of `build`, with no `working:` label other than one step 3 reported stale, no open pull request, nothing open in `needs`, and no pull request merged with no `Part of`. That last one leaves the card only a close by hand, so it is not a candidate. Beyond those, take only cards the board calls free, so only a `kind` of `ready`. A `deferred`, `decision`, `parent` or `data` card can carry a `build` verdict and still not be one to start, and its plan marker says so by dropping "ready to build".
3. **Blog drafts, when the repository has blog posts synced to Substack.** List the Substack drafts and their schedule. A merged or open pull request that touches `blog/` can leave its draft stale. A stale draft that is neither published nor scheduled is synced rather than asked about, where the repository's `CLAUDE.md` gives standing approval for it, as l3a0/quantitative-trading's `## Write-ups and their Substack drafts` does. A pull request's own session may already have synced it. So first compare the live draft with the copy of it recorded at the last sync, and pull any edit the owner made since then into the Markdown rather than overwrite it. A change to a published or scheduled post stays in the owner's queue, because writing to its draft changes what goes out. Publishing, scheduling and sending stay there too. The draft ids and the recorded copies live outside the repository, in Claude's local memory for it. The repository's `sync-substack` skill carries the procedure for a sync.
4. **The ranked backlog**, in `next`'s order across every milestone, then the directive's order for the rest, for when nothing above is waiting. Skip a card whose `kind` is not `ready`, under every generator, since a `build` there can be a deferred card's verdict and a parent builds nothing. l3a0/marketlake's copy listed every remaining open issue, parents included, and the merge applies the filter there too. A card blocked by an open issue is not a candidate until its blockers close, so name what it waits on rather than recommending it. In l3a0/quantitative-trading this is the replication backlog.

**A milestone can mark the path.** In l3a0/marketlake the open MVP milestone tracks the work ([MVP 2, capture on a hosted VM](https://github.com/l3a0/marketlake/milestone/5), when its copy was written). An issue off that path carries no milestone and the `deferred` label. Bugs that can lose a captured minute, and bugs in an alarm, are never deferred, so they carry neither and stay candidates even without the milestone. That is why step 3's check of the page looks under "All" as well.

**A stacked pull request is the usual way a base moves without a push.** It is one built on another pull request's branch rather than on `main`. GitHub's documentation on deleting branches says that deleting a merged pull request's branch moves every open pull request built on it onto the merged one's base. The move starts no CI run, because a `pull_request` trigger runs only on GitHub's default activity types and a base change is not one of them. In l3a0/quantitative-trading no stacked pull request had been moved that way by the setting on 2026-10-10, so that case rests on the documentation rather than on a run.

The cost is a rollup that reads green with checks missing. While a pull request sits on another's branch, only the checks that run on any base run. CodeQL's default setup scans only pull requests into the default branch or a protected one, so its checks never appear, and nothing new runs after the base moves until the next push. [l3a0/quantitative-trading PR #466](https://github.com/l3a0/quantitative-trading/pull/466) shows the cost. While it sat on [l3a0/quantitative-trading PR #464](https://github.com/l3a0/quantitative-trading/pull/464)'s branch, only `docs` and `test` ran. Both were green, so the rollup read green with four checks missing. Its base was moved by hand on 2026-10-10, and no run started until its next push. This prints when a pull request's base moved, to compare with its last push.

```bash
gh api --paginate "repos/$REPO/issues/<n>/timeline" --jq '.[]|select(.event=="base_ref_changed")|.created_at'
```

**Link every issue and pull request number.** Name each pull request's tracking issue beside it, linked, with how the two relate, in the form `[PR #<p>](https://github.com/<owner>/<repo>/pull/<p>), which closes [#<i>](https://github.com/<owner>/<repo>/issues/<i>)` or `[PR #<p>](https://github.com/<owner>/<repo>/pull/<p>), part of [#<i>](https://github.com/<owner>/<repo>/issues/<i>)`. A pull request that tracks no issue says "closes no issue". A table of pull requests gets an issue column. Read the relation from GitHub at report time, from `closingIssuesReferences` and any `Part of #NN` reference in the body outside code, rather than from memory. This holds in step 2's kept list too, wherever it names a pull request. The owner's global `CLAUDE.md` and each repository's `## Writing style` carry the rule.

Say which candidates only the owner can act on, and which a new session can start without them.

### Post the cost totals a merge left owed

The owner's rule on cost has the session that hands over work post a `## Cost` comment on its issue, and has a `## Cost total` posted once the issue closes. A merge that closes an issue leaves nobody to post the total, so the round posts it. This prints each issue closed in the last 14 days that has a `## Cost` comment newer than its newest `## Cost total`, or no total at all.

```bash
since=$(date -v-14d +%Y-%m-%d 2>/dev/null || date -d '14 days ago' +%Y-%m-%d)
gh issue list --repo "$REPO" --state closed --limit 1000 --search "closed:>=$since" --json number,comments --jq '.[] | ([.comments[] | select(.body | test("\\A## Cost\\r?\\n")) | .createdAt] | max) as $c | ([.comments[] | select(.body | test("\\A## Cost total\\r?(\\n|\\z)")) | .createdAt] | max) as $t | select($c != null and ($t == null or $c > $t)) | .number'
```

`date -v-14d` is macOS's form, and `date -d` is GNU's. A `## Cost` comment posted after a total counts as owed again, so the newer comment gets a new total that covers it. For each issue the command prints, post a comment that starts with the line `## Cost total`.

1. Sum every `## Cost` comment on the issue and on each of its closed sub-issues, and link each comment summed.
2. Name any loop known to have run on the issue that posted no `## Cost` comment.
3. Give the figures as lower bounds, as the comments do.

Report the totals posted in the round's summary, with their links.

## In each repository

What follows holds for one repository only, as its own copy recorded it.

### l3a0/quantitative-trading

- **Merged branches are deleted.** Since 2026-10-10 GitHub deletes a pull request's branch when the pull request merges, because the owner turned on the repository's `delete_branch_on_merge` setting. The branches of 102 pull requests that merged before it stayed on GitHub on 2026-10-10.
- **Blog drafts are a candidate source**, under its `CLAUDE.md`'s `## Write-ups and their Substack drafts`.

### l3a0/repo-template

- **Nothing repository-specific.** A seeded repository records its own facts under its own heading here, through a plugin release.

### l3a0/ithildin-runtime

- **Where worktrees sit.** Every worktree sits under `.claude/worktrees/` inside the main checkout. A session's is `.claude/worktrees/<name>` on a branch named `claude/<name>`. A sub-agent's is `.claude/worktrees/agent-<id>` on a branch named `worktree-agent-<id>`, and is locked while its host session runs. `.gitignore` lists `.claude/worktrees/`, so the main checkout's `git status` never shows them. The main checkout is not always on `main` either, and step 1 then leaves it alone.
- **Merged branches stay on GitHub.** The repository's `delete_branch_on_merge` setting was off on 2026-10-28. So a merged pull request's branch keeps its `origin/<branch>` ref, and step 2's remote-branch test passes for its commits. Deleting those branches, or turning the setting on, is the owner's call.

### l3a0/marketlake

- **Merged branches are deleted**, so the merged pull request's head ref is what proves a merged commit safe.
- **The main checkout is the code the daemon runs**, so a fast-forward there leaves a restart owed, as step 1 says.
- **The work follows the open MVP milestone**, and the page's selector defaults to it, as step 4 says.
