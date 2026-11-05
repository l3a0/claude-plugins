#!/usr/bin/env python3
"""Fail on a Markdown table with no title above it.

Markdown has no caption, so a table's title is a line of its own above it,
starting with a bold Table:. Text inside a code fence is skipped, because a
skill's examples can show a table's shape.
"""
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DELIMITER = re.compile(r"^\s*\|(\s*:?-+:?\s*\|)+\s*$")
TITLE = re.compile(r"^\s*\*\*Table:\*\* \S")
FENCE = re.compile(r"^ {0,3}(`{3,}(?=[^`]*$)|~{3,})(.*)$")


def untitled(text):
    """Return the 1-based line of each table header with no title above it.

    The check reads pipe tables with outer pipes, the only form these documents
    use. A table with no outer pipes, or one in a blockquote, goes unread.
    """
    found = []
    opened = None
    lines = text.split("\n")
    for index, line in enumerate(lines):
        fence = FENCE.match(line)
        if opened is None and fence:
            opened = fence.group(1)
            continue
        if opened is not None:
            if (
                fence
                and fence.group(1)[0] == opened[0]
                and len(fence.group(1)) >= len(opened)
                and not fence.group(2).strip()
            ):
                opened = None
            continue
        if index == 0 or not DELIMITER.match(line):
            continue
        above = index - 2
        while above >= 0 and not lines[above].strip():
            above -= 1
        if above < 0 or not TITLE.match(lines[above]):
            found.append(index)
    return found


assert untitled("Prose.\n\n| A |\n| --- |\n") == [3]
assert untitled("**Table:** What A holds\n\n| A |\n| --- |\n") == []
assert untitled("```\n| A |\n| --- |\n```\n") == []
assert untitled("**Table:** One\n\n| A |\n| --- |\n\n| B |\n| --- |\n") == [6]
assert untitled("**Table:** One\n\nProse.\n\n| A |\n| --- |\n") == [5]
assert untitled("**Table:** One\n| A |\n| --- |\n") == []
assert untitled("**Table:**\n\n| A |\n| --- |\n") == [3]
assert untitled("See **Table:** One\n\n| A |\n| --- |\n") == [3]
assert untitled("Prose.\n\n| A | B |\n| :--- | ---: |\n") == [3]
assert untitled("~~~\ntext\n~~~\n\n| A |\n| --- |\n") == [5]
assert untitled("````\n```\n| A |\n| --- |\n````\n") == []
assert untitled("~~~\n| A |\n| --- |\n~~~\n") == []
assert untitled("```\n~~~\n| A |\n| --- |\n```\n") == []
assert untitled("```\n``` x\n| A |\n| --- |\n```\n") == []
assert untitled("    ```\n\n| A |\n| --- |\n") == [3]
assert untitled("```a``` is prose\n\n| A |\n| --- |\n") == [3]

files = subprocess.check_output(["git", "ls-files", "*.md"], cwd=ROOT, text=True).split()
assert files
failures = [
    f"{name}:{line}"
    for name in files
    for line in untitled((ROOT / name).read_text(encoding="utf-8"))
]
for failure in failures:
    print("FAIL table with no title", failure)
print(f"ok {len(files)} files read")
sys.exit(1 if failures else 0)
