#!/usr/bin/env python3
"""Split over-long string-literal lines and, on request, rewrap ragged runs of them.

Usage:
    reflow_strings.py FILE... [--ragged] [--changed-since REF] [--line-length N] [--check]

A mechanical rewrite followed by `ruff format` leaves two kinds of line that a
formatter does not fix, because a formatter never splits a string:

1. A line that holds one string literal and runs past the line length.
2. A run of adjacent string-literal lines, one implicit concatenation, broken
   at places that no longer fill the lines.

The script finds each run of lines that each hold only a string literal, at one
indent and with one quote character, where only the run's last line may carry a
tail of closing brackets, commas and a comment. By default it rewraps only a run
that holds a line past the length. --ragged also rewraps every run of two or more
lines. --changed-since REF limits both to runs that touch a line changed since
the git commit REF, so a message the rewrite never touched keeps its layout.

A rewrap joins the run's text and wraps it again greedily, breaking only after a
space, never inside an f-string placeholder. A piece keeps the `f` prefix only
when it holds a placeholder. A piece without one is written as a plain string,
with `{{` and `}}` turned back into single braces.

Every change is checked before it is kept. The script parses the file with the
change and compares its `ast` dump with the original's, which fails when the
joined text of any string differs, when a split would turn one statement into
two, or when the file stops parsing. A run that fails the check is left as it
was and reported. So a run inside a docstring is never touched.

The line length comes from --line-length, or else from ruff's own choice of
config: the nearest folder holding `.ruff.toml`, `ruff.toml`, or a
`pyproject.toml` with a `[tool.ruff]` table, checked in that order. That file's
`line-length` is used, or 88, ruff's default, when it sets none. An `extend`
setting is not followed. A tab counts as four columns, ruff's default indent
width. --check prints a unified diff of what would change, writes nothing, and
exits 1 if anything would change.

Lines the script leaves alone: a literal with an r, b or u prefix, a triple-
quoted string, a line holding two literals or anything before its literal, a
body with a `\\N{...}` escape, a run whose middle line carries a comment, a line
between `# fmt: off` and `# fmt: on`, and a line marked `# fmt: skip` or `noqa`.
The script needs Python 3.12 or later, to parse the syntax ruff formats.
"""

import argparse
import ast
import difflib
import os
import pathlib
import re
import subprocess
import sys

LITERAL = re.compile(
    r"^(?P<ind>[ \t]*)(?P<pre>[fF]?)(?P<q>[\"'])(?P<body>(?:\\.|(?!(?P=q))[^\\\n])*)(?P=q)(?P<rest>.*)$")
TAIL = re.compile(r"^[\s),\]}]*(#.*)?$")
MARKED = re.compile(r"#.*(fmt:\s*skip|noqa)")
FMT_OFF = re.compile(r"^\s*#\s*fmt:\s*off\b")
FMT_ON = re.compile(r"^\s*#\s*fmt:\s*on\b")
RUFF_TABLE = re.compile(r"(?m)^\[tool\.ruff[.\]]")
DEFAULT_LENGTH = 88
TAB_WIDTH = 4


def line_length_for(path):
    """Return the line length ruff would use for this file, and where it came from."""
    for folder in pathlib.Path(path).resolve().parents:
        for name in (".ruff.toml", "ruff.toml", "pyproject.toml"):
            config = folder / name
            if not config.is_file():
                continue
            text = config.read_text(encoding="utf-8")
            if name == "pyproject.toml":
                if not RUFF_TABLE.search(text):
                    continue
                table = re.search(r"(?ms)^\[tool\.ruff\]\s*$(.*?)(?=^\[|\Z)", text)
                text = table[1] if table else ""
            else:
                text = re.split(r"(?m)^\[", text, maxsplit=1)[0]
            found = re.search(r"(?m)^line-length\s*=\s*(\d+)", text)
            if found:
                return int(found[1]), str(config)
            return DEFAULT_LENGTH, f"ruff's default, since {config} sets no line-length"
    return DEFAULT_LENGTH, "ruff's default"


def width(line):
    return len(line.expandtabs(TAB_WIDTH))


def parse_line(line):
    """Return the parts of a line that holds one plain or f-string literal, or None."""
    m = LITERAL.match(line)
    if not m or "\\N" in m["body"] or MARKED.search(m["rest"]):
        return None
    if m["rest"].strip() and not TAIL.match(m["rest"]):
        return None
    return m["ind"], m["pre"], m["q"], m["body"], m["rest"]


def tokens(text):
    """Split f-string-style text into words, each with the spaces that follow it.

    A placeholder, with whatever spaces it holds, stays inside one word. Each word
    is returned with whether it holds a placeholder.
    """
    words, word, spaces, has_field, i = [], "", "", False, 0
    while i < len(text):
        c = text[i]
        if c == " ":
            spaces += c
            i += 1
            continue
        if spaces:
            words.append((word + spaces, has_field))
            word, spaces, has_field = "", "", False
        if text.startswith("{{", i) or text.startswith("}}", i):
            word += text[i:i + 2]
            i += 2
        elif c == "{":
            depth, j = 0, i
            while j < len(text):
                depth += {"{": 1, "}": -1}.get(text[j], 0)
                j += 1
                if depth == 0:
                    break
            word += text[i:j]
            has_field = True
            i = j
        else:
            word += c
            i += 1
    if word or spaces:
        words.append((word + spaces, has_field))
    return words


def literal(indent, quote, piece, has_field):
    if has_field:
        return f"{indent}f{quote}{piece}{quote}"
    return f"{indent}{quote}{piece.replace('{{', '{').replace('}}', '}')}{quote}"


def wrap(indent, quote, text, rest, length):
    words = tokens(text)
    lines, piece, field = [], "", False
    for n, (word, has) in enumerate(words):
        last = n == len(words) - 1
        candidate = literal(indent, quote, piece + word, field or has) + (rest if last else "")
        if piece and width(candidate) > length:
            lines.append(literal(indent, quote, piece, field))
            piece, field = word, has
        else:
            piece, field = piece + word, field or has
    lines.append(literal(indent, quote, piece, field) + rest)
    return lines


def formatter_off(lines):
    """Return the set of line indexes between `# fmt: off` and `# fmt: on`."""
    off, inside = set(), False
    for n, line in enumerate(lines):
        if FMT_OFF.match(line):
            inside = True
        elif FMT_ON.match(line):
            inside = False
        elif inside:
            off.add(n)
    return off


def run_end(lines, i):
    """Return the end of the run of literal lines that starts at line i, or None if none starts there."""
    first = parse_line(lines[i])
    if first is None:
        return None
    j = i
    while True:
        parts = parse_line(lines[j])
        j += 1
        if parts[4].strip() or j == len(lines):
            return j
        nxt = parse_line(lines[j])
        if nxt is None or nxt[0] != first[0] or nxt[2] != first[2]:
            return j


def changed_lines(path, ref):
    """Return the 1-based numbers of the lines in the file on disk that differ from REF."""
    folder, name = os.path.split(os.path.abspath(path))
    done = subprocess.run(["git", "-C", folder, "diff", "-U0", "--no-color", "--end-of-options", ref, "--", name],
                          capture_output=True, text=True)
    if done.returncode:
        raise ValueError(f"git diff against {ref} failed: {done.stderr.strip()}")
    numbers = set()
    for start, count in re.findall(r"(?m)^@@ -\S+ \+(\d+)(?:,(\d+))? @@", done.stdout):
        first, n = int(start), 1 if count == "" else int(count)
        numbers.update(range(first, first + n))
    return numbers


def reflow(text, length, ragged=False, changed=None):
    """Return the reflowed text and a list of (line, reason) for runs left as they were.

    `changed` is None to consider every run, or the set of 1-based line numbers a
    run must touch. Each run is checked against the file with every earlier run's
    outcome in place.
    """
    original = ast.dump(ast.parse(text))
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.split(newline)
    off = formatter_off(lines)
    skipped, i, shift = [], 0, 0
    while i < len(lines):
        end = run_end(lines, i)
        if end is None:
            i += 1
            continue
        old = lines[i:end]
        first_line = i - shift  # the run's index in the file as read, which `off` and `changed` use
        span = range(first_line, first_line + len(old))
        too_long = any(width(line) > length for line in old)
        wanted = too_long or (ragged and len(old) > 1)
        touched = changed is None or any(n + 1 in changed for n in span)
        if not wanted or not touched or any(n in off for n in span):
            i = end
            continue
        parsed = [parse_line(line) for line in old]
        indent, quote, rest = parsed[0][0], parsed[0][2], parsed[-1][4]
        joined = "".join(body if pre else body.replace("{", "{{").replace("}", "}}") for _, pre, _, body, _ in parsed)
        new = wrap(indent, quote, joined, rest, length)
        if new == old:
            i = end
            continue
        trial = lines[:i] + new + lines[end:]
        try:
            same = ast.dump(ast.parse(newline.join(trial))) == original
        except SyntaxError:
            same = False
        if same:
            lines = trial
            i += len(new)
            shift += len(new) - len(old)
        else:
            skipped.append((first_line + 1, "the rewrapped run would change the program"))
            i = end
    return newline.join(lines), skipped


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("files", nargs="+")
    parser.add_argument("--line-length", type=int)
    parser.add_argument("--ragged", action="store_true", help="also rewrap every run of two or more lines")
    parser.add_argument("--changed-since", metavar="REF", help="touch only runs on lines changed since this commit")
    parser.add_argument("--check", action="store_true", help="print the diff, write nothing, exit 1 on a change")
    args = parser.parse_args(argv)
    if sys.version_info < (3, 12):
        print("reflow_strings.py needs Python 3.12 or later", file=sys.stderr)
        return 2
    if args.changed_since and args.changed_since.startswith("-"):
        parser.error("--changed-since takes a commit, not an option")

    results = []
    for path in args.files:
        if args.line_length:
            length, origin = args.line_length, "--line-length"
        else:
            length, origin = line_length_for(path)
        with open(path, encoding="utf-8", newline="") as f:
            text = f.read()
        try:
            changed = changed_lines(path, args.changed_since) if args.changed_since else None
            new, skipped = reflow(text, length, args.ragged, changed)
        except SyntaxError as err:
            print(f"{path}: does not parse under Python {sys.version_info.major}.{sys.version_info.minor}, so no "
                  f"file was written: {err.msg} on line {err.lineno}", file=sys.stderr)
            return 2
        except ValueError as err:
            print(f"{path}: {err}, so no file was written", file=sys.stderr)
            return 2
        for line, reason in skipped:
            print(f"{path}:{line}: left as it was, because {reason}", file=sys.stderr)
        results.append((path, text, new, length, origin))

    any_change = False
    for path, text, new, length, origin in results:
        if new == text:
            continue
        any_change = True
        if args.check:
            sys.stdout.writelines(difflib.unified_diff(
                text.splitlines(keepends=True), new.splitlines(keepends=True), path, path))
        else:
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(new)
            print(f"{path}: reflowed at {length} columns, from {origin}")
    return 1 if args.check and any_change else 0


if __name__ == "__main__":
    sys.exit(main())
