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

Since then all four repositories have moved onto the shared reusable workflow. Nine pull requests on l3a0/repo-template ported what l3a0/marketlake's generator read into it, each behind an input that is off by default, and [l3a0/marketlake PR #945](https://github.com/l3a0/marketlake/pull/945) moved l3a0/marketlake onto it under [l3a0/marketlake#942](https://github.com/l3a0/marketlake/issues/942).

Three files beside this one hold what a session needs only some of the time.

- [page.md](page.md) says what the page is made of, how to change the page or the generator, and how to verify a change by running the page.
- [record.md](record.md) is the record of what has gone wrong on the page, and the offer of a task per idle card that was tried and withdrawn.
- The `sync-prune-next` skill in this plugin runs the status round that reads the board and reports what a session left unset.

## Which board this repository runs

Every repository with a board runs one setup. A short caller, `.github/workflows/board.yml` in the repository, calls the reusable workflow `.github/workflows/build-board.yml` in l3a0/repo-template. That workflow runs the generator `scripts/build_board.py` and publishes the page `.claude/skills/update-build-board/board.html`, both read from l3a0/repo-template at the ref the caller pins. What differs between repositories is that pin and the inputs the caller passes. An input changes which labels and lines the generator reads, so find both before setting anything.

| Repository | Pin | Inputs |
| --- | --- | --- |
| l3a0/repo-template | `main` | none |
| l3a0/ithildin-runtime | `9c6d7e23d6381339c09102608c0958caca1401ce` | `icon` |
| l3a0/quantitative-trading | `cf2959a3e48aeec3d71a6ade5fc9641fc9e82073` | `title`, `data-label` |
| l3a0/marketlake | `fd8317e537a3d85423757c56c034ace623878a81` | `title`, `icon`, `subtitle`, `note`, `default-branch-head`, `milestone-default`, `ranking`, `owner-body-lines`, `review-heading`, `settled-rollup`, `sort-labels`, `label-colors` |

Run this from the repository root to find the pin and the inputs. Each Bash tool call starts a new shell, so run these lines in the same call as any command below that uses `$REPO`, `$BOARD` or `template`.

```bash
REPO="$(gh repo view --json nameWithOwner --jq .nameWithOwner)"
PIN="$(sed -nE 's#^ *uses: l3a0/repo-template/\.github/workflows/build-board\.yml@([^ ]+).*#\1#p' .github/workflows/board.yml)"
template() { gh api "repos/l3a0/repo-template/contents/$1?ref=$PIN" -H "Accept: application/vnd.github.raw"; }
if [ -n "$PIN" ]; then BOARD=shared; else BOARD=none; fi
echo "$REPO board=$BOARD pin=${PIN:-none}"
sed -n '/^    with:$/,/^[^ ]/p' .github/workflows/board.yml
```

The last line prints the caller's `with:` block, which names its inputs. A caller that prints none passes none, and its board reads the defaults below.

Check that `$PIN` is not empty before trusting anything `template` returns, because an empty pin means the `uses:` line did not match. `board=none` means the repository has no board this skill knows, so stop and report it.

Only l3a0/repo-template keeps the generator, the page, the page's test stub `dom-stub.js` and the board's default tab icon `favicon.ico`. A caller keeps its `board.yml`, and its own icon when it names one. So every command here that runs the generator or the page fetches it with `template`.

### The inputs a caller passes

Every input is a string that defaults to empty, and an empty one leaves the board as it was before the input existed. An on-or-off input takes empty or `"true"`, quoted because a bare `true` in YAML is a boolean while the inputs are strings. Any other value of an on-or-off input fails the run, and so does a `ranking` other than `order`. A failed run leaves the last board up and says why in its job summary.

| Input | What it changes | Written in the caller as |
| --- | --- | --- |
| `title` | the page's heading and tab, `<name> build board` when empty | `with: title: Marketlake Build Board` |
| `icon` | the tab icon, a `.ico` file in the caller, the template's when empty | [page.md](page.md) gives the form |
| `data-label` | the label whose cards take the kind `data` and draw in a "Waiting on data" column | `with: data-label: blocked-on-data` |
| `subtitle`, `note`, `default-branch-head` | the line under the heading, a paragraph under the strip, and the default branch's head in the footer | [page.md](page.md) gives the forms |
| `label-colors`, `sort-labels` | label chips filled with GitHub's colours, and each card's labels sorted by name | [page.md](page.md) gives the forms |
| `review-heading` | the heading that closes a review, read as moment 5 says | `with: review-heading: Review complete` |
| `settled-rollup` | a rollup that leaves out the board's own checks and reads a skipped check as settled | `with: settled-rollup: "true"` |
| `milestone-default` | a milestone selector, opening on the milestone the input names, with `<n>` for a number | `with: milestone-default: MVP <n>` |
| `owner-body-lines` | `Board order:` and `Board after:` lines read only from issues the owner opened | `with: owner-body-lines: "true"` |
| `ranking` | a card ranked by its `Board order:` line alone, with no `band:N` label read | `with: ranking: order` |

The band rule is what a caller without `ranking: order` gets: a card ranks only with a `band:N` label, and its order line places it within the band. The moments below say where the two rules differ.

## Generator compatibility

The skill and the generator share formats: the label names, the comment and body lines, the review heading, the inputs, and the list of changes that start no run. A repository pins the generator to one commit, while this skill moves whenever the plugin updates. [l3a0/repo-template#24](https://github.com/l3a0/repo-template/issues/24) kept the skill as a per-repository file for exactly that reason, and the owner asked on 2026-10-29 UTC to move it into the plugin anyway. The price is that a plugin update and a generator change can land apart, so this section names what the formats here were checked against.

The formats here were checked against the generator at `bde82a9e674432f6db928701821d99a73129d623` on l3a0/repo-template's `main`, and again at `fd8317e537a3d85423757c56c034ace623878a81`. `git diff --stat bde82a9 fd8317e` shows that the second changed only the page and a test, so the two read the same formats. The page change makes a card with no milestone name that in its pill, from [l3a0/repo-template PR #68](https://github.com/l3a0/repo-template/pull/68). So `fd8317e` is the pin to use, because it reads every format `bde82a9` reads and draws that pill as well. Every other place in this plugin that needs a pin points here rather than naming one. A release that adds an input names the head of the l3a0/repo-template pull request that declares it as the pin to use, because until that pull request merges no commit on `main` declares the input. The follow-up that moves l3a0/repo-template's `PLUGIN_COMMIT` to the release's merge commit also moves this pin to the template's merge commit.

A caller passing an input the called workflow does not declare fails, so each input needs a pin at or after the commit that first declared it. `git log -S` on `.github/workflows/build-board.yml` measured these.

| Input | First declared at |
| --- | --- |
| `title` | `4bb3f7f`, the first shared workflow |
| `icon` | `9c6d7e2` |
| `data-label` | `26e5010` |
| `subtitle`, `note`, `default-branch-head` | `8abb7a5` |
| `label-colors`, `sort-labels` | `ec53810` |
| `review-heading`, `settled-rollup` | `8b59b93` |
| `milestone-default` | `2593289` |
| `owner-body-lines` | `4c546fc` |
| `ranking` | `14656aa` |

From `14656aa` on, every input the workflow declares carries a type. `bde82a9` changed only a test after it, and `fd8317e` only the page and a test. Never pin `4c546fc`. At that commit the `default-branch-head` input carries no type, GitHub refuses the reusable workflow, and every run ends with no jobs. So `owner-body-lines` is first usable at `14656aa`, which fixed the declaration, and `bde82a9` added the test that catches it.

| Repository | Pinned at | Formats that pin reads | Caller read at |
| --- | --- | --- | --- |
| l3a0/repo-template | `main` | everything this skill states, at `9e3c160` when this was checked, whose generator, workflows and page are `fd8317e`'s | `9e3c160` |
| l3a0/ithildin-runtime | `9c6d7e23d6381339c09102608c0958caca1401ce` | the formats of `4bb3f7f`, which `9c6d7e2` did not change, without the fixes listed below | `9a2d722` |
| l3a0/quantitative-trading | `cf2959a3e48aeec3d71a6ade5fc9641fc9e82073` | the formats of `9c6d7e2` plus the `data-label` input, without the fixes listed below | `f1c4c0b` |
| l3a0/marketlake | `fd8317e537a3d85423757c56c034ace623878a81` | everything this skill states | `b53be9d` |

A pin before `4c546fc` reads the same labels and lines, but lacks some or all of six fixes that hold for every caller whatever its inputs. Each names the commit it landed in.

1. A closing link reads only within the caller's repository. Before, the run read a pull request reference by number in this repository whichever repository it named. A pull request elsewhere that closes an issue here could stop every run, as it did in l3a0/ithildin-runtime on 2026-10-29, and one here closing `other/repo#1` drew a branch on this repository's issue 1. Fixed at `7b86e28`.
2. `Board order: 0` sorts ahead of a card with no order, rather than as if it had none. Fixed in the page at `a8794fb`.
3. A body or comment saved with Windows line endings, as GitHub's web editor saves one, reads the same as one with Unix line endings. Before, an order or verdict line ending in a carriage return was not read. Fixed at `4c546fc`.
4. A `Board after:` line refuses a reference to another repository and a link whose text and address name different issues. Before, every `#N` on the line read as this repository's issue N, so `owner/name#N` did too. Fixed at `4c546fc`.
5. A number in a marker line or a `Part of` reference carries no more digits than the grammar's `MAX_DIGITS` bullet allows. Fixed at `4c546fc`.
6. The run summary lists the markers the board did not use, in the four rows `## The markers and their grammar` names. Added at `c61d3cf`.

Three rules keep the skill and the generator in step.

1. **A repository on a generator commit this section does not name follows its generator, not this skill.** The generator is what the board reads. So before setting a format, read the generator at the commit the repository runs, with `template scripts/build_board.py`. Grep it for `re.compile`, `KIND_LABELS` and `WORKING`. Where it disagrees with this skill, set what the generator reads, and report the disagreement, so the owner can move the pin or release the plugin.
2. **A format change to the generator ships with a plugin release in the same step.** The pull request that changes what the generator reads, or adds an input, also opens a pull request on l3a0/claude-plugins that updates this skill and this section and bumps the plugin's version. Neither merges without the other, because a generator merged alone leaves every session following the old rules on the new board. The nine pull requests that added those inputs and fixes batched their plugin edits into one release. With no new input each writes the same `board.json` as `cf2959a` for every caller at the time, which a golden test and a live measurement checked.
3. **Moving a pin is a format change when the generator moved between the two commits.** Compare the two commits with `git diff <old>..<new> -- scripts/build_board.py .github/workflows/build-board.yml` in l3a0/repo-template before moving the pin, and treat any change to a regex, a label list, a query field or an input as rule 2.

One repository has tests that read this skill's text. They pin these strings, so the strings stay here verbatim for those tests.

1. `test_the_skill_quotes_the_allowance_the_script_adds` in l3a0/repo-template asserts the phrase "a 600-minute allowance".
2. l3a0/repo-template's tests assert the `PIN=` line above, the line `gh workflow run board.yml --repo "$REPO"` on its own with no `--ref` after it, the text `` `with: icon: <path>` `` in `page.md` and `` `with: data-label: blocked-on-data` `` here, and that every numbered moment under `## What a session sets, and when` naming a "blocked by" link or a sub-issue says "dispatch the board". They find the moments under that heading and stop at the sentence "Nothing else needs setting."
3. They assert `` `with: title: `` and `` `with: review-heading: Review complete` ``, `` `with: settled-rollup: "true"` ``, `` `with: owner-body-lines: "true"` ``, `` `with: milestone-default: MVP <n>` `` and `` `with: ranking: order` `` here, and `` `with: subtitle: ` ``, `` `with: note: ` ``, `` `with: default-branch-head: "true"` ``, `` `with: label-colors: "true"` ``, `` `with: sort-labels: "true"` `` and `` `board-ms:<owner/repo>` `` in `page.md`. Every `` `with: <name>: `` form in either file, and every input under a `with:` line inside a fence whose sibling `uses:` names `l3a0/repo-template/.github/workflows/build-board.yml@`, has to name an input the workflow declares. They read those forms in the whole file, this list included.
4. They read the heading `### The inputs a caller passes` and its table, whose rows start with each input's name in a code span, comma-separated where a row holds several. The names have to equal the inputs the workflow declares.
5. They read the digit-limit phrase in the grammar, once in the whole file.
6. They read an example in a code span of each marker line the generator matches, the review heading and `Part of #N` included, of each kind label it reads, and of each `working:` label.
7. They read the table of first declarations in `## Generator compatibility`, whose header row is `| Input | First declared at |`. Its first column has to name each input the workflow declares exactly once, in code spans. They also read the one sentence in the whole file of the form `` `<sha>` is the pin to use ``, fetch the reusable workflow at that commit, and check that it declares every input with `type: string`. That commit is never `4c546fc`.
8. They read the setup block's `template()` line, and run it to check its whole `gh api` call, which fetches `?ref=$PIN` with the `Accept: application/vnd.github.raw` header. They also read the table in `## Which board this repository runs`. Every name in a code span in its inputs column has to be an input the workflow declares, and no row's pin may start with `4c546fc`.
9. They run the build command whose first line is `rm -f <scratch>/board.json`, from a stand-in caller, and check that every input reaches the generator. Every `--with` in it names an exact version, as in `pyyaml==<version>`. Four of their mutants rewrite its text in place, so keep these pieces verbatim: `if k != "icon"`, `f"--{k}=`, `, *flags])` and `str(v).lower() if isinstance(v, bool) else v`.
10. They run every `jq` filter in this skill and in `sync-prune-next` against a golden board and compare each with an expected output, so a new or reworded filter fails until the tests carry its output. They count every `jq` command inside a fence or a code span in either skill, so a `jq` in plain prose is not one. Each has to be a call they can read, with its filter in single quotes or bare. They compare each skill's filters on their own, and check that every call reads `<scratch>/board.json`.
11. They run the setup block's `sed` line that prints the caller's `with:` block, which they find by its `/^    with:$/` pattern and `board.yml`.
12. They read the command in `sync-prune-next`'s fallback that prints a pull request's head commit date, found by `headRefOid` and `committedDate`, exactly once. They check that its query asks for `commits(last:1)`, run its `--jq` filter on stand-in answers holding two commits, the head first and then last, and check that the fallback reads a head commit dated "later than the file's `state.updatedAt`" as unknown. The test is `test_the_fallback_reads_the_head_commits_date`.
13. They remove this list from the skill before reading it. The list starts with the sentence "One repository has tests that read this skill's text." and ends at its last numbered item. A paragraph indented under an item is fine, but any other text between the list and the next `## ` heading fails them.

## Where the board lives

| What | Where |
| --- | --- |
| The page | `https://<owner>.github.io/<name>/` |
| Its data | `board.json` beside the page |
| The caller | `.github/workflows/board.yml` in this repository |
| The build and deploy jobs | `.github/workflows/build-board.yml` in l3a0/repo-template, at the ref the caller pins |
| What builds the data | `scripts/build_board.py` in l3a0/repo-template |
| The page's source | `.claude/skills/update-build-board/board.html` in l3a0/repo-template |
| The page's tab icon and test stub | `favicon.ico` and `dom-stub.js` beside that page, unless the caller names its own icon |

Each page's address is public and the same for every machine, so it lives here rather than in a file on the machine.

**The caller is short.** It holds the triggers, the `permissions`, and `concurrency: group: pages`, which makes runs deploy one at a time so an older snapshot never replaces a newer one. Its one job is `uses: l3a0/repo-template/.github/workflows/build-board.yml@<ref>`, with a `with:` block for the inputs it passes. That job grants the union of the scopes the two called jobs declare, because a called job can only narrow what its caller grants. Those are `contents`, `issues`, `pull-requests`, `checks`, `statuses` and `actions` to read, and `pages` and `id-token` to write. In l3a0/repo-template itself the ref is `main`. A seeded repository pins a full commit SHA, so its board changes only when that repository moves the pin. The called workflow checks out the generator and the page from the template at its own commit, which it reads from `job.workflow_repository` and `job.workflow_sha`. Inside a called workflow the `github` context still describes the caller, so `github.workflow_sha` would name the wrong commit. It also checks out the caller's `.github/workflows/board.yml`, because the generator reads the schedule from it, and the file the caller's `icon` input names, when it names one.

**A change reaches the page once a run of the Action finishes.** A label, a body edit and a comment each start a run, so the page changes within a few minutes. A "blocked by" link and a sub-issue start none, because GitHub Actions lists no trigger for either, and neither does a submitted pull request review. So the session that makes a link or a sub-issue dispatches the board itself once its changes are in, using the `gh` login it made them with. The moments below say where.

```bash
gh workflow run board.yml --repo "$REPO"
```

The dispatch runs on the default branch. Never pass `--ref`. The `github-pages` environment lets only `main` deploy, so GitHub refuses the deploy of a run from any other branch. The environment has a branch policy and no required reviewers, so a dispatch approves nothing. `gh workflow run` may ask for permission, because no allow rule covers it in some repositories, and a round says so in its report when it does.

The caller's triggers are these.

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
template scripts/build_board.py > <scratch>/build_board.py &&
uv run --no-project --python '>=3.12' --with pyyaml==6.0.3 python - <scratch>/build_board.py "$REPO" <scratch> <<'PY'
import subprocess, sys, yaml
jobs = yaml.safe_load(open(".github/workflows/board.yml"))["jobs"]
inputs = next(iter(jobs.values())).get("with") or {}
flags = [f"--{k}={'' if v is None else str(v).lower() if isinstance(v, bool) else v}" for k, v in inputs.items() if k != "icon"]
generator, repo, out = sys.argv[1:]
sys.exit(subprocess.call([sys.executable, generator, "build", "--repo", repo,
    "--workflow", ".github/workflows/board.yml", "--out", out, *flags]))
PY
```

The build passes the caller's inputs, other than `icon`, which only the workflow reads. A build without them reads the defaults, so under `ranking: order` it would rank nothing and under `review-heading` it would count the wrong reviews. The generator needs Python 3.12 or later, and a bare `python3` can be an older one, such as the 3.9 at `/usr/bin/python3` on macOS, which fails on import. `uv run --python '>=3.12'` finds or fetches a version that works, and `--no-project` is safe because the generator imports only the standard library. `--with pyyaml==6.0.3` is for reading the caller, which the generator does not need, and the exact version keeps every round and l3a0/repo-template's tests of this command on the same parser.

The command reads the caller's `with:` values literally, as PyYAML parses them, and passes an input written with no value as empty. GitHub parses the file itself and evaluates expressions, so a `${{ }}` expression, or a YAML 1.1 form such as `yes` or `010`, reads differently here from what GitHub passes the workflow. Write each input as a plain string, and an on-or-off input as `"true"`.

Each build prints what it read to the terminal, including a summary table of what the read cost in GraphQL requests and points and what it found in the markers sessions set, and writes `<scratch>/board.json`. A run that fails says why, exits non-zero and writes nothing, because the generator stops on any read it cannot trust rather than writing a board that reads as correct.

## What a session sets, and when

Each moment below is one where the page's answer changes and nothing GitHub records on its own says so. `<n>` is the card's issue and `<b>` the issue it waits on.

1. **A decompose loop starts.** Add `working:decompose` to the issue. A `working:` label already on the issue is no lock. Check it against the stale-label rule in step 3 of the `sync-prune-next` skill, and ask the session that owns it before taking over. Each pass gets its own comment headed `## Plan audit, pass N`. The generator counts these headings to find a loop that exited without a verdict, and does not count a combined heading such as `## Plan audit, passes 7 and 8`. A later loop on the same issue continues the numbering, and its verdict counts its own passes.
2. **A decompose loop exits.** Post the verdict as a comment carrying one line in this form, alone on its line, then take `working:decompose` off.

   ```text
   Board verdict: build after 5 passes
   ```

   `build` means the plan is ready for a builder. Write `decide` in place of `build` when the loop ended on a question only the owner can answer, and name the question in the same comment, because a status round lists the card and not the question. Once the owner answers, a loop posts a fresh verdict, because an answer carries no verdict line and without one the card reads "waits on an owner call" forever. The newest verdict wins, so a loop run again writes a new one rather than editing the old. A loop with passes and no exit writes no verdict, because the card's plan marker means the loop exited. In the same step, post the loop's cost as a separate comment starting with the line `## Cost`, under the owner's rule on posting cost on the issue.
3. **A build session starts on a card.** Add `working:build` to the issue, after the same check as a decompose loop. It stays after the pull request opens, because until the hand-over it is the only thing on the page saying the branch is still moving. If the label does not exist yet, `gh issue edit` fails. Report that and carry on. Never run `gh label create`, because creating labels is the owner's, or the template's `scripts/setup-repo.sh` in a seeded repository.
4. **A session hands its pull request over.** That means the review is posted under the heading moment 5 names, its fixes are pushed, the checks are green at the current head, and nothing more is coming. Take `working:build` off then, not when the pull request opens. Until then the label keeps the card under "Waiting on my review" and out of the owner's "Waiting on your review" column, whatever its review and checks say, which is its job while the review runs. In the same step, post the build's and the review's cost on the issue as a comment starting with the line `## Cost`.

   A `Part of` pull request leaves its issue open. Once it merges, the card drops back to "Planned, no builder" with its old verdict reading "ready to build", because the In flight section counts only open pull requests. So that hand-over also settles the verdict for the remainder. A build session runs no plan passes of its own, so it does one of two things.

   - If the remainder already has a plan that still holds, post `Board verdict: build after N passes`, with N that plan's pass count.
   - If it does not, edit the comment carrying the old verdict and remove its `Board verdict:` line, so the card stops reading ready. Sessions act as the owner, so they can edit the owner's comment. Once the pull request merges, the run summary lists the card under finished plans with no verdict, because no verdict follows its plan passes any more, and it needs a new loop.

   A verdict is otherwise withdrawn only by a newer one, or by editing or deleting its comment.
5. **A review lands on a pull request.** Post it as a pull request comment whose first line is the heading the caller's generator reads. A review headed anything else counts as none, and its card sits in "Waiting on my review" until somebody notices.

   - **With no `review-heading` input**, the generator reads an owner's pull request comment, never a submitted review, whose body, after leading whitespace, opens with `## Review` followed by a word boundary. `## Reviewer` is not one. It counts whenever it was posted. Without one, the card's `review` reads "review in progress" while it carries a `working:` label, and "no review posted" otherwise.
   - **Under `with: review-heading: Review complete`**, the generator reads only a comment or a submitted review whose whole first line is `## Review complete`, posted by the owner after the head commit's `committedDate`. A submitted review counts only when it names the head commit, and it reaches the board at the next run of any other kind, because submitting one starts no run. A heading that only starts with those words, like `## Review completeness check`, does not count, and neither does a marker from an earlier round, because the commits pushed since then are code that review never saw. A session can post some lenses' results while another lens still runs, so a partial review stays headed something else. Any review comment was once enough in l3a0/marketlake, and that sent [l3a0/marketlake PR #713](https://github.com/l3a0/marketlake/pull/713) to the owner while its mutation lens was still running. That repository's `CLAUDE.md`, under "Pull requests", is where review sessions read the rule for writing the heading. A pull request whose final review was posted before a repository took the rule carries no marker, so it reads as unreviewed until a session posts one, and a round reports it rather than guessing whether its review finished. To check one pull request, read the generator's own answer from a local build, made with the build command in `## Where the board lives`, rather than counting markers by hand. It prints `true` or `false` once for each open issue the pull request names.

     ```bash
     jq '.prs.items[] | select(.pr == <n>) | .reviewed' <scratch>/board.json
     ```

     A pull request that names no open issue in its own repository, through a closing link or a `Part of #N` reference, is never on the board, so the read prints nothing and answers nothing for it. That is common. Of l3a0/repo-template's 35 pull requests up to PR #70, 20 named no issue in their own repository at all, and so did 16 of l3a0/marketlake's 60 from PR #818 to PR #945, counting every state and measured with the generator's own closing-link and `Part of` rules. A round reports the review of each such pull request as unknown rather than counting markers by hand, because a second copy of the rule drifts from the generator's.

   A final pull request comment whose first line is `## Review complete`, posted after the last push, satisfies both rules, so it is the form to use where a session cannot tell which one runs.
6. **An issue is filed.** Add a label the board reads for the card's `kind` where one applies. The generator reads `deferred` and `decision`, and also the label a caller names in its `data-label` input, which reads as the kind `data`. Read the caller's `.github/workflows/board.yml` for that name. The build's job summary names the label and counts the open issues carrying it, so a count of zero there means the input matches no label. l3a0/quantitative-trading's caller names `blocked-on-data`. These are separate from the label a repository's `CLAUDE.md` asks every filed issue for, saying what kind of work it is, such as `bug` or `documentation`. The card prints that one among its labels and decides nothing by it. Under the band rule, add a `band:N` label if the card joins the priority order, because a card with no band is left out of the board's default view. Under `ranking: order` no `band:N` label is read, and a `Board order:` line alone ranks a card. Add a native "blocked by" link for each open issue the card cannot start before, and a `Board after:` line for an ordering nothing enforces. If it set any link, dispatch the board once everything is set, because a link starts no run.
7. **A card's priority or ordering changes.** Move its `band:N` label under the band rule, and add, change or remove its `Board order:` line. Add, change or remove its `Board after:` line when an ordering nothing enforces changes. Under `ranking: order`, once any card in a milestone carries an order and is not deferred, the page's default view hides that milestone's unranked cards behind "Show all". So rank a milestone's open issues that are not parents in one pass, rather than one card at a time. Orders form one sequence across every milestone, so do not restart the numbering at 1 in each. A leftover order line hides every unranked card in its milestone and nothing reports it, so remove an order line that no longer means anything. A deferred card's order hides nothing there, because the page ignores it.
8. **What a card waits on changes.** Add or remove its "blocked by" link, then dispatch the board, because the link starts no run.
9. **An issue gains or loses a sub-issue.** Dispatch the board once the sub-issues are set, because they start no run. A split in a decompose loop is the usual case. An issue with any sub-issue draws as a parent under the band rule, and one with any open sub-issue does under `ranking: order`.

Nothing else needs setting. A pull request opening, merging or closing, its checks settling, and an issue closing, retitled or relabelled all reach the board from GitHub.

### Parents and deferred cards

A parent builds nothing, and its children carry the plans. Under `ranking: order` the generator drops a verdict or an order on a parent, and a verdict on a card labelled `deferred`, because the board would otherwise offer a deferred card as free to pick up. The run summary lists each drop, and removing `deferred` brings the verdict back on the next run. A deferred card keeps its order, and the page and the sync round both skip it. So under that input a parent carries no verdict and no order, and a deferred card carries no verdict.

Under the band rule the generator drops neither. A `deferred`, `decision`, `parent` or `data` card can carry a `build` verdict there and still not be one to start, and the page's plan marker says so by dropping "ready to build". It does drop an order line on a card with no `band:N` label, because the order ranks nothing without one, and the summary lists that drop too.

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

A "blocked by" link takes the blocker's database id, which `--jq .id` reads, rather than its number. A body line is added by editing the issue's body with the view and edit pair above, and goes on a line of its own, which is what the generator reads.

## The markers and their grammar

Three kinds of marker carry a session's judgement, besides the review heading of moment 5.

1. **Labels.** `working:build` says a build session holds the card, and `working:decompose` says a decompose loop is planning it. `band:N` ranks it under the band rule.
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
| `working:build` | `fbca04` | A build session holds this card until it hands its pull request over | the generator |
| `working:decompose` | `fbca04` | A decompose loop is planning this card | the generator |
| `band:1`, `band:2`, `band:3` | set by the setup script | The card's priority, lowest first | the generator under the band rule, and nothing under `ranking: order` |
| `deferred` | set by the setup script | Deferred on purpose | the generator |
| `decision` | set by the setup script | Waits on an owner decision | the generator |
| `blocked-on-data` | as created in the repository | Waits on data that has to be bought or captured | the generator, under a caller that names it in its `data-label` input, as l3a0/quantitative-trading's does |

Each line follows this grammar under the generator at the pin `## Generator compatibility` names. A pin before `4c546fc` lacks some of the fixes `## Generator compatibility` lists, and l3a0/ithildin-runtime and l3a0/quantitative-trading run such pins today.

- It starts its line, with nothing before it but spaces or tabs. A list marker such as `- ` or `1. `, or a quote marker `> `, stops it being read. An order or verdict line also has nothing after it but spaces or tabs.
- The words are exactly as shown, in that case, with one ordinary space after the colon. `Board after:` takes any spacing after its colon.
- An order is an optional minus sign, then digits, then optionally a decimal point followed by at least one digit. So `+2`, `.5`, `2.` and `1e3` are not read. An order and a pass count carry at most 15 digits, the generator's `MAX_DIGITS`, because the page reads every number as a double, and a longer one is listed as unread. A pass count is a whole number. `pass` and `passes` both read, and a trailing full stop is allowed.
- A line inside a fenced code block is not read, so a fence is how to quote the format. A line inside a code span is not one either, because it does not start the line. A line quoted inside a sentence is not read.
- A body or comment saved with Windows line endings reads the same as one with Unix line endings. On a pin before `4c546fc`, an order or verdict line saved that way is not read, so edit it from the command line or re-save it there.
- A verdict counts only in a comment, and an order or after line only in an issue's body. Each one in the wrong place is listed as unread.

Three rules decide what a line that is read counts for.

1. **What a `Board after:` line reads.** It reads each `#N`, each `owner/name#N` naming this repository, and the link form `[#N](https://github.com/<owner>/<repo>/issues/N)`, which may carry an anchor or a query after the number, such as `#issuecomment-5`. It refuses a reference to another repository, written `owner/name#N` or as a link to another repository, rather than reading it as this repository's issue. It also refuses a link whose address is no issue or pull request address on `https://github.com`, and a link whose text and address name different numbers. Each refusal is listed, and the rest of the line still reads. The card keeps only open issues from the line, other than itself, and a line naming only the card itself is listed as dropped. On a pin before `4c546fc`, every `#N` on the line reads as this repository's issue, so never write a reference to another repository there.
2. **Whose text counts.** Anyone can comment on or open an issue in a public repository, and a stranger's text would otherwise move a card. A verdict and a review count only in a comment whose author GitHub reports as `OWNER`, and a stranger's verdict is listed as refused. Sessions run `gh` as the owner, so their text counts. Under `with: owner-body-lines: "true"`, and always under `ranking: order`, an order or after line counts only in the body of an issue the owner opened. A line the owner adds to someone else's issue is refused, and a stranger's is listed as refused. Without either input a body line counts on any issue, which is safe there because only a `band:N` label ranks a card, and a label needs triage access. A label and a link count whoever set them.
3. **What a line that is not read does.** When an issue's comments carry several verdicts, the newest wins, and when a body carries several order lines, the first wins. The run summary lists four kinds of marker the board did not use, each in its own row. None of them stops the Action.
   1. **Marker lines not read** are lines in the owner's text that look meant as a marker and are not read, such as `board order: 3`, `Board order 3`, `**Board order**: 3` or `1. Board order: 3`. A line counts as meant for a marker when the marker's words end it, or are followed, after optional emphasis and spaces, by a colon, a digit or a `#`. Prose that only starts with the words, such as "Board orders form one sequence", is not listed, and neither is a stranger's near miss.
   2. **Marker lines refused** are the refusals under rules 1 and 2.
   3. **Markers dropped** are markers read and then not used, which `### Parents and deferred cards` and rule 1 name.
   4. **Finished plans with no verdict after them** are open issues whose newest owner `## Plan audit, pass N` heading comes after their newest verdict, or that have passes and no verdict at all. Parents, deferred cards, cards a decompose loop holds and cards with an open pull request are left out.

   Each row names the issue and the marker's kind, never the line, so read the issue for the line itself.

**A branch that closes no issue gets no card at all**, because the page is built from the tracker. Check `closingIssuesReferences` when a pull request opens, and if it is empty and the branch means to close something, fix the body before going further. A closing keyword naming another repository's issue gives no card entry here either. A pull request into any branch but `main` is the exception. GitHub reads closing keywords only on a pull request into the default branch, so a stacked one shows an empty list until its base moves to `main`. That query is also eventually consistent. On [l3a0/quantitative-trading PR #94](https://github.com/l3a0/quantitative-trading/pull/94) it reported nothing seconds after the body gained its closing keyword and reported the link on the next call, so read it a second time before concluding the keyword failed. The generator also reads a `Part of #N` reference anywhere in the body outside code. A pull request from a fork gets no card entry, because GitHub registers a fork's closing keyword, so a stranger's fork reading `Closes #640` would otherwise move that issue into In flight.

**A label is owed its removal by the session that set it.** A session that ends without taking its `working:` label off leaves its card under "Waiting on my review", "Building" or "Being planned" until somebody removes it. That fails safe, because it delays a merge rather than inviting one too early. So report a stale label rather than removing another session's. The `sync-prune-next` skill's step 3 says how a round finds one.

## The data, and where each field comes from

The page loads each section of `board.json` into the variable of the same name in capitals, so `prs` becomes `PRS`, and the rest of this section uses those names. The generator writes each section other than `state` as `{"schema": 1, "items": [...]}`, so a reader takes a section's list from its `items`, such as `.working.items`. `prs` also keeps merged and closed entries, so a reader asking for open pull requests filters on `state == "open"`. Change what GitHub holds. Never hand-write a sentence in the page stating a number the data already carries, because that sentence outlives the number.

### The sections and their fields

| Section | Field | Comes from |
| --- | --- | --- |
| `STATE` | `repo`, `title` | the repository the run read, from `--repo`, and the board's title, from the `title` input, which defaults to `<name> build board`. The page builds every issue and pull request link from `repo`, so nothing in the page names a repository |
| `STATE` | `updatedAt`, `issues.open`, `longestGapMinutes`, `staleAfterMinutes` | the time GitHub was read, the open issue count, the longest gap in the caller's schedule, and that gap plus a 600-minute allowance for a scheduled run GitHub starts late or drops |
| `STATE` | `subtitle`, `note`, `main` | each written only when the caller sets the matching input. `subtitle` is the line under the heading. `note` is the caller's paragraph as a list of pieces, each `{text}` or `{text, href}`, because the generator parses its `[words](https://...)` links and fails the run on any other address. `main` is the default branch's head as seven characters, from `default-branch-head`, for one more request a run |
| `STATE` | `labelColors` | under `label-colors` only: each label a card draws, mapped to the six-digit colour GitHub stores for it, in lower case |
| `STATE` | `milestoneDefault` | under `milestone-default` only: the short name of the open cards' milestone that matches the input, taking the lowest number in place of `<n>`, or null when none matches, and the page then opens on every milestone |
| `STATE` | `ranking` | under `ranking: order` only: `"order"`, which the page reads to draw every card in a milestone where none is ranked |
| `TRACKER` | `n`, `ms`, `label`, `labels` | each open issue's number, milestone, title and labels. `ms` is the milestone's whole title, or the empty string for none. Under `milestone-default` it is the title up to its first comma, so "MVP 4, serve the bars" reads `MVP 4`. `labels` leave out the board's own `band:N` and `working:` labels, which the page draws as the rank chip and the busy stripe, and keep the order GitHub returns them in, which is the order they were added, or name order under `sort-labels` |
| `TRACKER` | `kind` | `parent` for an issue with a sub-issue, which under `ranking: order` means an open one, then `data` for the label the caller's `data-label` input names, then `deferred` for `deferred` and `decision` for `decision`, in that order where an issue carries more than one, and `ready` otherwise. The generator reads no `data` kind when the input is empty, and refuses a data label that names a label it already reads, such as `deferred` |
| `TRACKER` | `needs` | the issue's native "blocked by" links, keeping only blockers that are open issues in this repository |
| `TRACKER` | `after` | the issue's `Board after:` lines, read as `## The markers and their grammar` says, keeping only open issues other than the card itself. Under `owner-body-lines` or `ranking: order`, only from an issue the owner opened |
| `PRS` | `pr`, `issue`, `state`, `linked`, `partOf`, `rollup` | each pull request from a branch in this repository that names an open issue in this repository, through a closing link or a `Part of #N` reference anywhere in its body outside code, with one entry per issue it names and its checks at the current head |
| `PRS` | `reviewed`, `review` | the review rule of moment 5. With no `review-heading` input, `review` reads "review posted", or without one "review in progress" while the card carries a `working:` label and "no review posted" otherwise. Under the input it reads the heading with its first letter in lower case, such as "review complete", or "no Review complete marker since the head commit", so it never names a lens still running |
| `WORKING` | `n`, `kind` | the `working:build` and `working:decompose` labels |
| `PLANNED` | `n`, `passes`, `ready` | the newest owner comment carrying a `Board verdict:` line, less a verdict `ranking: order` drops |
| `NEXT` | `issue`, `band`, `order` | under the band rule, one entry per issue with a `band:N` label, its `order` from its `Board order:` line. Under `ranking: order`, one entry per issue other than a parent whose body carries a `Board order:` line the generator reads, with `band` 0 in every entry |
| `NEXT` | `ready` | the card's verdict where it has one, `decide` for a card whose kind is `decision`, and `plan` otherwise |

`NEXT_SORTED` is `NEXT` put in order, by band, then order with 50 where a card has none, then readiness, then number. So an order of 0 or below sorts ahead of a card with none. Under `ranking: order` every band is 0, so the order alone decides. It is derived on every load.

`rollup` is a list of `[name, word]` pairs, one for each check on the head commit, in the order GitHub lists them. The word is one of five.

1. `success` is a check run's or a status context's SUCCESS.
2. `failure` is a check run's FAILURE, TIMED_OUT and STARTUP_FAILURE, and a status context's FAILURE and ERROR. Without `settled-rollup` it is also a check run's CANCELLED and ACTION_REQUIRED.
3. `running` is a check run that has not completed, and a status context's PENDING and EXPECTED.
4. `neutral` is a check run's NEUTRAL and STALE, and its SKIPPED without `settled-rollup`. Under that input it is also CANCELLED and ACTION_REQUIRED. A state GitHub adds later reads as `neutral` too, and the run summary names it under "Check states mapped to neither way".
5. `skipped` is a check run's SKIPPED under `settled-rollup` only, a job whose condition kept it from running. l3a0/marketlake's `tofu apply (live)` job is one on every pull request, because it runs only on `main`.

Under `settled-rollup` the generator also leaves out the board's own checks, which it tells apart by their workflow file, `.github/workflows/board.yml`, and sorts the pairs by name. A `pull_request_target` run attaches the board's checks to the pull request's head commit, so without that a reviewed pull request would read as still running while the board rebuilds. The page reads a rollup as green when every entry is `success` or `skipped` and at least one is `success`, and it reads any word outside these five as reported neither way.

### Three fields carry judgement rather than measurement

1. **`needs` against `after`.** `needs` is a hard blocker and moves a card into a deeper column. `after` is an ordering somebody measured that nothing enforces, so it leaves the card where it is and sorts it below what it names. Use `after` when one card can be built first but is better built second, such as a fix that leaves the suite red until another issue lands. [l3a0/quantitative-trading#83](https://github.com/l3a0/quantitative-trading/issues/83) once carried `after: [51]` because its own body measured the split: three of the failures a second download causes belonged to [l3a0/quantitative-trading#51](https://github.com/l3a0/quantitative-trading/issues/51) and the rest did not, so it could be built first while the suite stayed red until 51 landed. A "blocked by" link there would have said something false. A link and an issue's `## Depends on` prose say the same thing twice. The link wins, because it is what the board reads, and the prose keeps the reason the wait exists.
2. **A verdict means a decompose loop exited**, on a pass that did not reduce the body. Not that a body looks thorough. Read the pass count as a cost rather than a depth. One l3a0/quantitative-trading run reached 109 passes under an older exit rule, which asked for two consecutive empty passes and could not terminate while the loop edited its own artifact.
3. **`band`** is priority under the band rule, and what each band means is the repository's call, under the ranking directive in its own `CLAUDE.md`. `## In each repository` below says where each repository writes it down.

`question` is not `decision`. An issue can carry `question` while it waits on research rather than on the owner, as [l3a0/quantitative-trading#273](https://github.com/l3a0/quantitative-trading/issues/273) did, so the board reads only `decision` as needing the owner rather than a session.

### When two labels disagree

An issue carrying two `band:N` labels, both `working:` labels, two kinds, or, on a ranked card, more than one `Board order:` line has no single value. The generator takes the lowest band, the `build` kind, the kind the table above puts first and the first line, and lists each conflict rather than failing, because one stray label would otherwise freeze the whole board. A parent carrying `deferred` is a conflict too, read as `parent`. Several order lines are a conflict even when they agree, because an edit to the second copy would move nothing. Under `milestone-default`, two milestone titles cut to the same short name are listed as well, because the selector would merge them. The run summary's "Labels or lines that disagree" row lists them all, and a local build prints the same table, which a status round reads. Read it after setting either, and fix the label the conflict names.

## In each repository

What follows holds for one repository only. Everything above it holds wherever the repository's pin and inputs do.

### l3a0/quantitative-trading

The dispatch there is this line.

```bash
gh workflow run board.yml --repo l3a0/quantitative-trading
```

- **The page** is <https://l3a0.github.io/quantitative-trading/>, built by the shared workflow at the pin above, with the template's page and tab icon. The icon it served before the move was the same file. Its caller names the title Quantitative Trading Build Board.
- **What each band means** is 1 for work that blocks other work or risks data that cannot be recaptured, 2 for the reader chain everything waits behind, 3 for a sentence wrong where a reader acts on it, and 5 for deferred on purpose. No band 4 is defined, so no label exists for it.
- **The `blocked-on-data` label** gives a card the kind `data`, and the page draws such cards in a fourth build-order column, "Waiting on data", under the subtitle "not a backlog, a purchase". [l3a0/repo-template#24](https://github.com/l3a0/repo-template/issues/24) cut that kind and column from the shared board, and [l3a0/repo-template#40](https://github.com/l3a0/repo-template/issues/40) brought them back behind the `data-label` input. [l3a0/quantitative-trading#785](https://github.com/l3a0/quantitative-trading/issues/785) moved this repository's caller onto the shared workflow, passing that input.
- **The Show all choice** is kept in the viewer's browser under the key `board-all:l3a0/quantitative-trading`.
- **The retired artifact.** Until [l3a0/quantitative-trading#533](https://github.com/l3a0/quantitative-trading/issues/533) the board was a claude.ai artifact whose figures sessions measured by hand and wrote into its database. That cost about $51 a day in session turns, measured on [l3a0/quantitative-trading#531](https://github.com/l3a0/quantitative-trading/issues/531), and it missed every change no session saw. That artifact is retired. Nothing writes it, and it is kept rather than deleted only because each ranked card's `why` and each plan's `note` exist nowhere else. Do not write to it, and do not publish the page to it.

### l3a0/repo-template

- **The page** is <https://l3a0.github.io/repo-template/>, and the caller's `uses:` ref is `main`, so the template's own board runs the template's newest generator and page.
- **What each band means** is left to each seeded repository. `scripts/setup-repo.sh` creates `band:1`, `band:2` and `band:3`, `working:build`, `working:decompose`, `deferred` and `decision` through `.github/labels.json`.

### l3a0/ithildin-runtime

- **The page** is <https://l3a0.github.io/ithildin-runtime/>, and it deploys only from `main`. Its caller pins the template at `9c6d7e23d6381339c09102608c0958caca1401ce` and serves its own tab icon, `.github/board/favicon.ico`, through the `icon` input.
- **What each band means** is set by `## Keep the build board current` in that repository's `CLAUDE.md`, under its ranking directive. That section is the one place the meaning is written, so read it there rather than from a copy here.

### l3a0/marketlake

The dispatch there is this line.

```bash
gh workflow run board.yml --repo l3a0/marketlake
```

- **The page** is <https://l3a0.github.io/marketlake/>, built by the shared workflow. Its caller pins l3a0/repo-template at the commit, and passes the inputs, that its row in `## Which board this repository runs` names. It serves its own tab icon, `.github/board/favicon.ico`, through the `icon` input.
- **The move** is [l3a0/marketlake PR #945](https://github.com/l3a0/marketlake/pull/945), under [l3a0/marketlake#942](https://github.com/l3a0/marketlake/issues/942). It removed the repository's own generator, page and page tests, so a session there reads the generator with `template` and tests a page change in l3a0/repo-template, as in every other repository.
- **Ranking** is the `Board order:` line alone, under `ranking: order`, since no `band:N` label exists there. The page opens on the open MVP milestone, under `milestone-default: MVP <n>`.
- **The review heading** is `## Review complete`, under that repository's `CLAUDE.md` owner directive of 2026-10-06, which its `review-heading` input carries.

## Finishing

Report in the same reply that sets anything.

1. Each label, link and line set or removed, and on which issue.
2. Any conflict, unread line, refused line or dropped marker the next build listed, and what fixed it.
3. Any sentence the harness caught, and what replaced it, when the page's code changed.
4. Any disagreement between this skill and the generator the repository runs, under rule 1 of `## Generator compatibility`.

A run of the Action that fails leaves the last board up. The page's stale banner says so once the stamp passes `staleAfterMinutes`. Read the failed run's log rather than re-running it, because a second run of the same read fails the same way unless the failure was GitHub's.

An update reports the idle cards it found and offers no task for any of them, for the reasons [record.md](record.md) gives under its last heading. What to start, and how many at once, is the owner's call.
