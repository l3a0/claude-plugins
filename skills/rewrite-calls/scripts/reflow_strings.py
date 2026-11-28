#!/usr/bin/env python3
"""Split over-long string-literal lines and rewrap ragged runs of them.

Usage:
    reflow_strings.py FILE... [--line-length N] [--long-only] [--check]

A mechanical rewrite followed by `ruff format` leaves two kinds of line that a
formatter does not fix, because a formatter never splits a string:

1. A line that holds one string literal and runs past the line length.
2. A run of adjacent string-literal lines, one implicit concatenation, broken
   at places that no longer fill the lines.

The script handles both the same way. It finds each run of lines that each hold
only a string literal, at one indent and with one quote character, where only
the run's last line may carry a tail of closing brackets, commas and a comment.
It joins the run's text and wraps it again greedily, breaking only after a
space, never inside an f-string placeholder. A piece keeps the `f` prefix only
when it holds a placeholder. A piece without one is written as a plain string,
with `{{` and `}}` turned back into single braces.

Every change is checked before it is kept. The script parses the file with the
change and compares its `ast` dump with the original's, which fails when the
joined text of any string differs, when a split would turn one statement into
two, or when the file stops parsing. A run that fails the check is left as it
was and reported. So a run inside a docstring is never touched.

The line length comes from --line-length, or else from the nearest
pyproject.toml with a [tool.ruff] line-length or ruff.toml with a line-length,
or else 88, ruff's default. --long-only touches only the runs that hold a line
past the length. --check prints a unified diff of what would change, writes
nothing, and exits 1 if anything would change.

Lines the script leaves alone: a literal with an r, b or u prefix, a triple-
quoted string, a line holding two literals or anything before its literal, a
body with a `\\N{...}` escape, and a run whose middle line carries a comment.
"""

import argparse
import ast
import difflib
import pathlib
import re
import sys

LITERAL = re.compile(
    r"^(?P<ind>[ \t]*)(?P<pre>[fF]?)(?P<q>[\"'])(?P<body>(?:\\.|(?!(?P=q))[^\\\n])*)(?P=q)(?P<rest>.*)$")
TAIL = re.compile(r"^[\s),\]}]*(#.*)?$")
DEFAULT_LENGTH = 88


def line_length_for(path):
    for folder in pathlib.Path(path).resolve().parents:
        for name in ("ruff.toml", ".ruff.toml"):
            config = folder / name
            if config.is_file():
                found = re.search(r"(?m)^line-length\s*=\s*(\d+)", config.read_text(encoding="utf-8"))
                if found:
                    return int(found[1]), str(config)
        pyproject = folder / "pyproject.toml"
        if pyproject.is_file():
            section = re.search(r"(?ms)^\[tool\.ruff\]\s*$(.*?)(?=^\[)|^\[tool\.ruff\]\s*$(.*)",
                                pyproject.read_text(encoding="utf-8"))
            if section:
                found = re.search(r"(?m)^line-length\s*=\s*(\d+)", section[1] or section[2] or "")
                if found:
                    return int(found[1]), str(pyproject)
    return DEFAULT_LENGTH, "ruff's default"


def parse_line(line):
    """Return the parts of a line that holds one plain or f-string literal, or None."""
    m = LITERAL.match(line)
    if not m or "\\N" in m["body"]:
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
        if piece and len(candidate) > length:
            lines.append(literal(indent, quote, piece, field))
            piece, field = word, has
        else:
            piece, field = piece + word, field or has
    lines.append(literal(indent, quote, piece, field) + rest)
    return lines


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


def reflow(text, length, long_only=False):
    """Return the reflowed text and a list of (line, reason) for runs left as they were.

    Each run is checked against the file with every earlier run's outcome in place.
    """
    original = ast.dump(ast.parse(text))
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.split(newline)
    skipped, i = [], 0
    while i < len(lines):
        end = run_end(lines, i)
        if end is None:
            i += 1
            continue
        old = lines[i:end]
        too_long = any(len(line) > length for line in old)
        if (len(old) < 2 and not too_long) or (long_only and not too_long):
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
        else:
            skipped.append((i + 1, "the rewrapped run would change the program"))
            i = end
    return newline.join(lines), skipped


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("files", nargs="+")
    parser.add_argument("--line-length", type=int)
    parser.add_argument("--long-only", action="store_true", help="touch only runs that hold an over-long line")
    parser.add_argument("--check", action="store_true", help="print the diff, write nothing, exit 1 on a change")
    args = parser.parse_args(argv)

    any_change = False
    for path in args.files:
        if args.line_length:
            length, origin = args.line_length, "--line-length"
        else:
            length, origin = line_length_for(path)
        with open(path, encoding="utf-8", newline="") as f:
            text = f.read()
        try:
            new, skipped = reflow(text, length, args.long_only)
        except SyntaxError as err:
            print(f"{path}: does not parse, so nothing was changed: {err.msg} on line {err.lineno}", file=sys.stderr)
            return 2
        for line, reason in skipped:
            print(f"{path}:{line}: left as it was, because {reason}", file=sys.stderr)
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
