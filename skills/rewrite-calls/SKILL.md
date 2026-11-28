---
name: rewrite-calls
description: Rewrite every call of one Python function across a codebase in one pass, when a signature change forces dozens of call sites to change the same way, then lay the result out and prove no message text changed. Uses `ast` to find each call and fill a template from its own argument text, `ruff format` to lay it out, a reflow script to split the string lines a formatter leaves too long or ragged, and a check that compares every string with git's copy. Use when asked to change every call of a function or method, to wrap each call's arguments in a new type, to rename a call's keywords across files, or whenever a mechanical rewrite of many call sites is about to be done by hand.
---

# Rewrite calls

A change to a function's signature forces every caller to change, and a caller rewritten by hand costs a tool round trip per call site. A regular expression is cheaper per site, but it breaks on a call split across lines, on a nested bracket, and on a call whose name only ends with the target. This skill rewrites the calls from the parse tree instead, then fixes the layout the rewrite leaves.

The scripts come from the build of l3a0/ithildin-runtime [#257](https://github.com/l3a0/ithildin-runtime/issues/257), in [PR #266](https://github.com/l3a0/ithildin-runtime/pull/266). That build changed `core.ports.Alerts.alarm` to take a structured `Alarm`, so about 60 call sites in `src/` had to change, and later every supervisor alarm was routed through one helper. The session wrote three scripts and ran them four times in the same shape: rewrite each call, run `ruff format`, then fix the lines the rewrite left too long or ragged.

## When to use it

Use it when many calls of one function change in the same way, such as these.

- Each call's arguments get wrapped in a new type: `alarm("disk full", code=3)` becomes `alarm(Alarm("disk full", code=3))`.
- A call moves to another function, with its arguments reordered or renamed.
- Most calls change one way, and a few another way or not at all.

The skill expects a repository formatted with `ruff`, because step 3 runs it and the reflow reads ruff's line length. A rename that touches only the name, with no change to the arguments, needs no skill. `ruff` or a plain search and replace does it. A change that needs judgement at each call site, such as choosing a severity from what the message says, still uses this skill, through a spec that gives each call its own template.

## The order

Run the steps in this order, from the root of the repository being changed. `<this skill>` stands for this skill's folder. The scripts need Python 3.12 or later, because Python 3.9 reports wrong positions for a call inside a multi-line f-string placeholder and cannot parse newer syntax. A bare `python3` can be older, such as the 3.9 at `/usr/bin/python3` on macOS, so each command below runs through `uv run --no-project --python '>=3.12' python`, which finds or fetches a version that works. `--no-project` is safe because the scripts import only the standard library.

1. **List the calls.** `--list` prints each matching call with its number and line, and changes nothing.

   ```bash
   uv run --no-project --python '>=3.12' python <this skill>/scripts/rewrite_calls.py self._alerts.alarm --list src/app/*.py
   ```

2. **Rewrite them.** Run with `--check` first, which prints a diff and writes nothing, then run again without it. The script works out every file's new text before writing any, so a refusal in one file leaves every file as it was.

   ```bash
   uv run --no-project --python '>=3.12' python <this skill>/scripts/rewrite_calls.py self._alerts.alarm '{func}(Alarm({args}))' src/app/*.py --check
   uv run --no-project --python '>=3.12' python <this skill>/scripts/rewrite_calls.py self._alerts.alarm '{func}(Alarm({args}))' src/app/*.py
   ```

3. **Format.** Run `ruff format` on the changed files, because a template does not lay out the lines it makes.
4. **Reflow the strings.** A formatter never splits a string, so a message that moved one level deeper can run past the line length, and a message the rewrite broke up can sit on ragged lines. `reflow_strings.py` fixes both, and refuses any change that would alter the program. Give it only the files step 2 changed. `--changed-since HEAD` limits it to runs on lines changed since the last commit, and `--ragged` lets it rewrap a ragged run as well as a long one, so together they fix what the rewrite left and keep every other message's layout. Run it with `--check` first here too.

   ```bash
   uv run --no-project --python '>=3.12' python <this skill>/scripts/reflow_strings.py $(git diff --name-only -- '*.py') --ragged --changed-since HEAD --check
   uv run --no-project --python '>=3.12' python <this skill>/scripts/reflow_strings.py $(git diff --name-only -- '*.py') --ragged --changed-since HEAD
   ```

5. **Check every string against git.** `check_strings.py` compares the strings in each file with the committed copy, so it covers all three steps above at once. It fails if any committed string is gone or changed, and lists each string a template added, for review.

   ```bash
   uv run --no-project --python '>=3.12' python <this skill>/scripts/check_strings.py src/app/*.py
   ```

6. **Run the suite and the linter.** Run the repository's tests, `ruff check`, and `ruff format --check`. The rewrite can leave an import missing, such as the `Alarm` the template names, and only the linter and the tests see that.
7. **Search for calls the match missed.** The match is exact on the spelling, so a call through another name, such as `alerts = self._alerts` followed by `alerts.alarm(...)`, is not rewritten. Search for the bare method name, such as `rg -n '\.alarm\('`, and handle what is left.

Each step leaves the tree in a state worth reading, so review `git diff` between steps rather than only at the end.

## Templates

A template is the text that replaces the whole call. Its fields are filled from that call's own source text, exactly as written.

**Table:** The fields a template can use

| Field | Filled with |
| --- | --- |
| `{call}` | the whole call |
| `{func}` | the called name, such as `self._alerts.alarm` |
| `{args}` | every argument, from the first one's start to the last one's end, with comments and line breaks between them |
| `{0}`, `{1}` | one positional argument, a starred one with its `*` |
| `{name}` | the value of the keyword argument `name` |

A literal brace in a template is written `{{` or `}}`. A field a call lacks stops the run and names the call, and no file is written.

When calls change in different ways, `--list` gives their order, and a JSON spec gives each call its own entry. An entry is a template, or `null` to leave that call alone. A spec covers one file, and a count that differs from the file's matching calls stops the run.

```bash
uv run --no-project --python '>=3.12' python <this skill>/scripts/rewrite_calls.py self._alerts.alarm --spec spec.json src/app/supervisor.py
```

```json
["{func}(Alarm({args}, severity=Severity.HIGH))", null, "{func}(Alarm({0}, severity=Severity.LOW))"]
```

## How the reflow works

The reflow script finds each run of lines that hold only a string literal, at one indent and with one quote character. Only a run's last line may carry a tail of closing brackets, commas and a comment. It joins the run's text and wraps it again greedily, breaking only after a space and never inside an f-string placeholder. A piece keeps the `f` prefix only when it holds a placeholder, so `f"the job {name} failed after many retries"`, indented four spaces, becomes these two lines at 40 columns.

```python
    f"the job {name} failed after many "
    "retries"
```

Before keeping a change, the script parses the file with it and compares the parse tree with the original's. The comparison fails when the joined text of any string differs, when a split would turn one statement into two, or when the file stops parsing. A run that fails is left as it was and reported. That is why a long line inside a docstring is never split.

By default the script rewraps only a run that holds a line past the length. `--ragged` also rewraps every run of two or more lines, and `--changed-since REF` limits both to runs that touch a line changed since that commit. A run between `# fmt: off` and `# fmt: on`, and a line marked `# fmt: skip` or `noqa`, are left alone, as ruff leaves them.

The line length comes from `--line-length`, or else from the config file ruff itself would pick. That is the nearest folder holding `.ruff.toml`, `ruff.toml`, or a `pyproject.toml` with a `[tool.ruff]` table, checked in that order. Its `line-length` is used, or 88, ruff's default, when it sets none. An `extend` setting is not followed, so a repository that keeps its length in an extended file passes `--line-length`. A tab counts as four columns, ruff's default indent width.

## What the scripts do not handle

These cases are refused or left alone, never rewritten wrongly. Each needs a hand edit.

- **A matching call inside another matching call.** Replacing the outer call would copy the inner call's old text, so `rewrite_calls.py` stops. Rewrite such a file in two passes with a spec.
- **A comment inside a call that no field of the template carries.** A comment after the last argument is outside `{args}`, and one between arguments is outside `{0}` and `{name}`, so the rewrite would drop it. `rewrite_calls.py` stops and names the line. A template that uses `{call}` keeps every comment.
- **A keyword argument named `call`, `func` or `args`.** Its value would hide the field of that name, so `rewrite_calls.py` stops.
- **A call reached through another name.** Step 7 of the order finds these.
- **A string with an r, b or u prefix, which covers bytes literals.** Joining a raw string with a plain one would change its escapes, so `reflow_strings.py` leaves every such line alone.
- **A triple-quoted string, and a line that holds two literals or anything before its literal.** This covers an implicit concatenation inside parentheses on one line, such as `("a " "b")`.
- **A run whose middle line carries a comment.** The comment ends the run, and each part reflows on its own.
- **A body with a `\N{...}` escape.** The script treats braces as placeholders or as literal braces, and this escape's braces are neither.
- **A word longer than the line.** The script breaks only after a space, so a long URL stays on one over-long line.

Line widths are counted in characters, with a tab as four, so a line of wide characters, such as CJK text, can still look long in an editor.

## Checks

`tests/test_rewrite_calls.py` in this plugin's repository runs each script on small files, under Python 3.12 or later. It covers each refusal above, an f-string split next to a placeholder, a placeholder that holds spaces, lines one short of, at and one past the length, a docstring line that must not be split, a statement-level string that must not become two statements, ruff's choice of config file, and a string check given an absolute path or a ref that names no commit.
