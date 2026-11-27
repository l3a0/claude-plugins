---
name: fast-mutation
description: Run a mutation review fast, by scripting every mutant into one call scoped to the tests that reach it, instead of one tool round trip per edit. Drives pytest, or a suite of plain test scripts that exit non-zero on a failure. Use for a mutation lens on a pull request, for confirming that a new test catches the bug it claims to, or whenever a mutation run is taking far longer than its tests do.
---

# Fast mutation

A mutation run asks whether the tests notice when the code is broken. Its cost should be the
tests' run time, and usually it is not. On marketlake's [PR #713](https://github.com/l3a0/marketlake/pull/713) the entitlement tests took
0.98 s per mutant, while a lens that broke the code by hand ran for over an hour. The time went
to model round trips, about four tool calls per mutant, and to full-suite runs on survivors.
This skill moves the whole loop into one script call, and spends model time only on choosing
mutants and judging survivors.

## The runner

`scripts/mutate.py` takes a JSON spec and runs every mutant in it, in one process. Its
docstring gives the spec format. For each mutant it does five things.

1. It applies exact `[old, new]` string edits. Each `old` must occur exactly once, or the mutant
   is reported NOT-APPLIED and nothing is written.
2. It clears `__pycache__`, because a same-length edit can keep stale bytecode and fake a
   survivor.
3. It runs pytest, or the spec's commands for a suite of plain scripts, on the mutant's own selection, or on the spec's default selection.
4. It restores the file from a byte copy taken before the run, never from git, and checks the
   restore byte for byte. `git checkout --` would also discard uncommitted work.
5. It records CAUGHT, SURVIVED, TIMEOUT or NO-TESTS, with the first failing test.

Before any mutant, it runs the baseline and stops if the baseline is not green. A baseline
that already fails, for example a wall-clock test under load, makes every mutant read as
caught.

After the loop, the runner re-runs each scoped survivor on its own against the tests in the
`escalate` selection that reach its code. Survivors cannot share one run: two applied together
can mask each other, and a failure could not be pinned on either.

```bash
python3 <this skill>/scripts/mutate.py spec.json --out /path/to/scratch/run1
```

Use `--only NAME ...` to re-run chosen mutants after adding a test, `--no-escalate` to skip
the wide runs, `--escalate-full` to re-run each survivor against the whole `escalate`
selection, and `--workers N` to spread the wide runs over pytest-xdist workers.

## Plain test scripts

A suite of plain scripts, each run as `python3 tests/<file>` and exiting non-zero on a failure, has no pytest to drive. l3a0/claude-plugins is one: each test file prints an `ok` or `FAIL` line per check. On l3a0/claude-plugins [PR #100](https://github.com/l3a0/claude-plugins/pull/100), the test engineer in each of seven review rounds wrote its own loop to apply a mutant, run the script and restore the file, because this runner only drove pytest.

Set `"runner": "script"` in the spec for such a suite. Each selection is then a command the spec's interpreter runs, such as `["tests/test_brief_anchors.py"]`, or a list of such commands that must all pass. A run is green when every command exits 0. Its failures are the output lines that match `fail_pattern`, which defaults to lines starting `FAIL` or `FAILED`. A command that fails without printing such a line is reported by its last output line.

Three things change in this mode.

1. The baseline and each mutant run the same way as with pytest, including the byte-copy restore and the cleared `__pycache__`.
2. A survivor escalates against the full `escalate` selection, and its line says `scope=full (script runner, no coverage map)`, because the coverage map is a pytest plugin.
3. Workers are not used, and asking for them prints a line that says so.

```json
{
  "runner": "script",
  "root": "/path/to/worktree",
  "python": "/usr/bin/python3",
  "baseline": ["tests/test_brief_anchors.py"],
  "select": ["tests/test_brief_anchors.py"],
  "escalate": [["tests/test_brief_anchors.py"], ["tests/test_review_post.py"]],
  "mutants": [
    {"name": "refuse no overwrite", "file": "skills/ask-team/scripts/brief_anchors.py",
     "edits": [["if os.path.exists(out):", "if False:"]]}
  ]
}
```

## Escalation scoped by coverage

The wide run exists to catch a test far from the mutated code that still reaches it. Running
the whole suite per survivor is an expensive way to find that test. On marketlake's [PR #738](https://github.com/l3a0/marketlake/pull/738)
each full run took about 250 s on a loaded laptop, which put 48 survivors at more than 3 hours,
and every one that finished survived the full suite anyway. Coverage answers the same question
exactly, so escalation runs only the tests that execute the mutated function. It takes three
steps.

1. The runner runs the `escalate` selection once, unmutated, with `scripts/cover_map.py`
   loaded as a pytest plugin. The plugin uses `sys.monitoring` from Python 3.12 to record
   which tests start each function in the mutated files, and it needs no third-party package.
   This run doubles as the full-suite run of workflow step 6. If it is red, escalation is
   skipped and the runner exits with code 3, because every wide verdict would read as caught.
2. The runner maps each survivor's edits to the outermost function whose body holds the
   bytes they change. Context that `old` and `new` share, added only to make `old` unique, does not
   count. Code nested inside a function, such as an inner function or a generator
   expression, counts as that function.
3. The runner re-runs the survivor against exactly the tests that started its function. When
   no test did, it reports the survivor UNREACHED and runs nothing.

The method rests on one assumption: a test that never starts the mutated function cannot
observe the mutation. The runner cannot rely on it in three cases, and each falls back to the
full `escalate` run for that mutant.

1. The edit sits outside every function body. That covers module level, a decorator, a
   signature or its defaults, and a class body outside its methods. Such code runs at import.
2. The function runs outside any test, for example when a `parametrize` argument calls it
   during collection.
3. The map run never imported the file. The runner also prints a warning, because the
   virtualenv may import a different copy of the source.

Every survivor falls back to the full run when the target interpreter is older than 3.12, or
when another tool already holds the `sys.monitoring` coverage slot.

Two other routes reach code without starting it in the test's own run, and the map covers
both. A fixture wider than function scope is set up once, inside the first test that asks for
it, so the map credits code it starts to every test that uses the fixture. A test that spawns a
process can run the code in a child the plugin cannot see, so every such test joins every
scoped selection. State carried between tests, such as a memoized result, is not covered.
Use `--escalate-full` when a suite relies on it.

Each escalated line ends with `scope=coverage (N tests)` or `scope=full (<reason>)`.
`results.jsonl` records the map's path in its MAP row and each mutant's scope in its row.

Measured on [PR #738](https://github.com/l3a0/marketlake/pull/738) at commit 7d817c6, on a laptop that other sessions kept at a load average
between 5 and 30, so every time here is rough.

1. The 48 survivors took 81 min end to end: a 6 s baseline, about 5 min of scoped runs, a
   274 s map run, and 72 min of escalation at a median of 82 s per survivor. The old full
   escalation ran at a median of 253 s per survivor over the 32 it finished, which puts all 48
   at about 3.4 hours.
2. All 48 survived again. The 32 survivors both runs finished got the same verdict.
3. The map gave each survivor 131 or 330 of the suite's 6,705 tests. Of those, 120 spawn
   processes and so join every selection. Back to back, the 210 in-process tests for one
   function ran in 6 s, the same tests plus the 120 spawning ones in 79 s, and the whole suite
   in 262 s. The spawning tests are most of what a scoped run costs on this suite.
4. Every one of the 295 test failures that caught a function-body mutant in the lens's narrow
   run fell inside the scope the map gave that mutant.

## Workers for the wide runs

The map run and every full-suite fallback each cost one full-suite run. pytest-xdist splits a
run across worker processes. On marketlake a trial for [issue #746](https://github.com/l3a0/marketlake/issues/746) measured the full suite at a
median of 246.7 s serially and 75.0 s with 8 workers. The runner can pass `-n N` to the wide
runs, and it never passes it anywhere else.

Ask for workers with `"workers": 8` in the spec, or with `--workers 8`, which wins over the
spec. `--workers 0` turns them off. Without either, nothing changes. The runner then adds
`-n N` to three kinds of run.

1. The map run.
2. Every full escalation, including a fallback from a coverage-scoped run.
3. A coverage-scoped escalation whose tests took at least `workers_min_secs` in the map run.
   The default is 10 s. The map records each test's run time for this decision.

The baseline and the per-mutant runs stay serial. Starting workers costs 2 to 3 s, and a narrow
run takes about 5 s, so workers there would slow the loop down. For the same reason, keep `-n`
out of the `escalate` selection itself, or every scoped escalation pays the startup.

When the target interpreter cannot import xdist, the runner prints that pytest-xdist is
missing and runs everything serially.

Under xdist each worker is its own process with its own `sys.monitoring` state, so each worker
maps only the tests it ran. It writes that map next to `cover_map.json`, as
`cover_map.gw0.json` and so on. The controller, the process that starts the workers and runs no
test itself, merges them into `cover_map.json` at the end of the run. The merge unions the
tests per function, `outside_tests` and the files seen, and it refuses maps that disagree on the
root directory. The rules above still hold inside each worker. Collection runs in every worker,
so a function a `parametrize` argument calls still counts as running outside tests. A worker sets
up its own copy of each wider fixture, so the fixture rule credits the tests in that worker. A
test that spawns a process is caught in whichever worker ran it. A process that xdist starts
for itself does not count as a spawn. That covers each worker, and on macOS the `uname` and
`file` calls a worker makes to report its platform.

A worker that crashes leaves no map. The controller then writes no merged map and prints a
`cover_map:` line. The crash also fails a test, so the runner treats the map run as red and
skips escalation with exit code 3.

The coverage-scoped runs work under xdist too. Every worker reads the same list of test IDs and
so collects the same filtered set, which xdist requires. Only the controller writes the report
of which IDs matched.

Measured on [PR #738](https://github.com/l3a0/marketlake/pull/738) at commit 8abb35f, with six survivors known to be equivalent, run serially
and then with `"workers": 8` on a laptop other sessions kept loaded, so every time is rough.

1. The map run took 224 s serially at a load average of 4 to 6, and 88 s with 8 workers at a
   load average of 8 to 11.
2. Five scoped escalations ran about 350 tests each, 120 of them tests that spawn processes.
   They took 75 to 81 s serially and 45 to 48 s with workers. The sixth ran 144 tests, in 70 s
   serially and 42 s with workers.
3. The whole run took 11 min 55 s serially and 6 min 40 s with workers.
4. The merged map equalled the serial map apart from ordering: 6,727 tests, 120 spawning tests
   and the same six functions running outside tests. All six survivors survived both runs.

## Workflow

1. **Commit first.** The runner restores from its own backup, but a mutation session that
   also edits tests needs a commit to return to.
2. **Measure the selections before choosing them.** Time the baseline files, then a `-k` or
   node-ID selection that reaches the mutated code. On [PR #713](https://github.com/l3a0/marketlake/pull/713) the two whole files took 7.79 s,
   and the 17 entitlement tests took 0.98 s. Use the narrow selection per mutant, and the whole
   files as the baseline and for escalation.
3. **Write the mutants as guarantees.** Name each mutant after the guarantee it breaks, such as
   "count rows before the data-row filter". Start from the changed lines, then the helpers they
   call, then the test oracles. Ask whether an expected value shares code with the code under
   test, because an oracle built from the code's own constant cannot fail.
4. **Run the spec once.** Read the BASE line first. If it is not green, fix the baseline before
   trusting anything.
5. **Judge each survivor.** It is either equivalent or a real gap.
   - **Equivalent:** prove by executing that the mutant cannot change any answer, such as
     comparing outputs over random inputs.
   - **Real gap:** name the input it gets wrong, add the assertion that closes it, and re-run
     that mutant with `--only` to show it is now caught.
6. **Run the full suite once at the end**, unmutated, whatever happened above. When survivors
   were escalated against the whole suite, the MAP line already records that run.

## Running it from a lens

A lens prompt should name this skill and give the lens the scoped selection and the target
commit. The lens writes the spec, runs it once, and spends its turns on survivors.
The prompt should also forbid the slow pattern outright: no hand edit, test run and restore
per mutant as separate tool calls, and no full-suite run per mutant.

A run that outlasts the shell's ten-minute foreground limit goes in the background with
`run_in_background`, and its own completion notice says when it is done. Do not watch it with
`until ! pgrep -f "<spec file>"`. `pgrep -f` matches the loop's own command line, which
contains the spec file's name, so the loop never exits. On 2026-10-10 one lens left six such
loops running for up to two hours. The lens stops any background task it started before it
reports. The global `CLAUDE.md` rule "Leave no background job waiting on itself" carries the
full reasoning.

## Safety

The runner executes code only through pytest, or through the commands a script spec names, in the given worktree. A repository whose
default paths point at live configuration must redirect them in its test setup. Marketlake's
conftest redirects the config directory. A standalone probe that imports the package before
redirecting can write to live configuration, which happened on 2026-10-06. Keep every
mutation run inside the test runner, and point `root` at a worktree, never at a main checkout that
another session uses.

## What it does not do

It does not generate mutants. That is deliberate. Generated mutants come in bulk and need
triage: `mutmut` ran 243 mutants in 29.7 s on marketlake, but 15 of its 19 survivors were
equivalent. Hand-written mutants aimed at stated guarantees find the gaps that matter. For
breadth, run `mutmut` with `only_mutate` scoped to the changed file, separately.

It does not run mutants in parallel. Workers split the tests of one wide run, but the mutants
still run one at a time against one source tree. Parallel mutants would need one source copy
per worker. A copied virtualenv can still import the original source, so verify
`module.__file__` points inside the copy. Parallelism also pays only when cores are idle.
