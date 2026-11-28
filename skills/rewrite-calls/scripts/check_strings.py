#!/usr/bin/env python3
"""Check that a rewrite left every string's text as it was.

Usage:
    check_strings.py FILE... [--ref REF]

For each file, the script reads the version at the git commit REF (HEAD by
default) and the version on disk, and compares the strings each one holds. It
reads them with `ast`, so a string split across adjacent literals counts as its
joined text, and an f-string counts as its text with each placeholder's
expression. A docstring is a string too, and a string that appears twice counts
twice.

It prints each string the old version held that the new one lacks, and each one
the new version holds that the old one lacked. A string whose text changed shows
as one of each. It exits 1 when any old string is gone, and 0 otherwise. A
string that only appears, such as one a rewrite template adds, is printed for
review and does not fail the check.

A file is skipped with a note only when git tracks its folder but holds no such
file at REF, which is a file the rewrite created. A ref that does not name a
commit, or a file outside a git work tree, stops the run with exit 2, so the
check never passes on a file it did not compare. A path may be relative or
absolute. The script needs Python 3.12 or later, to parse the syntax ruff
formats.
"""

import argparse
import ast
import collections
import os
import subprocess
import sys


def strings(text):
    """Return a count of every string in the source, each as `ast.unparse` writes it."""
    found = collections.Counter()
    stack = [ast.parse(text)]
    while stack:
        node = stack.pop()
        if isinstance(node, ast.JoinedStr) or (isinstance(node, ast.Constant) and isinstance(node.value, (str, bytes))):
            found[ast.unparse(node)] += 1
            continue
        stack.extend(ast.iter_child_nodes(node))
    return found


def git(folder, *args):
    return subprocess.run(["git", "-C", folder, *args], capture_output=True, text=True)


def at_ref(path, ref):
    """Return the file's text at REF, or None when git holds no such file there."""
    folder, name = os.path.split(os.path.abspath(path))
    if git(folder, "rev-parse", "--show-toplevel").returncode:
        raise ValueError("is not in a git work tree")
    if git(folder, "rev-parse", "--verify", "--quiet", "--end-of-options", f"{ref}^{{commit}}").returncode:
        raise ValueError(f"{ref} does not name a commit")
    if git(folder, "cat-file", "-e", f"{ref}:./{name}").returncode:
        return None
    done = git(folder, "show", f"{ref}:./{name}")
    if done.returncode:
        raise ValueError(f"git show failed: {done.stderr.strip()}")
    return done.stdout


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("files", nargs="+")
    parser.add_argument("--ref", default="HEAD", help="the commit to compare against, HEAD by default")
    args = parser.parse_args(argv)
    if sys.version_info < (3, 12):
        print("check_strings.py needs Python 3.12 or later", file=sys.stderr)
        return 2
    if args.ref.startswith("-"):
        parser.error("--ref takes a commit, not an option")

    lost_any = False
    for path in args.files:
        try:
            old_text = at_ref(path, args.ref)
            if old_text is None:
                print(f"{path}: git holds no such file at {args.ref}, so skipped as new")
                continue
            with open(path, encoding="utf-8") as f:
                new_text = f.read()
            old, new = strings(old_text), strings(new_text)
        except (ValueError, OSError, SyntaxError) as err:
            print(f"{path}: {err}", file=sys.stderr)
            return 2
        lost, gained = old - new, new - old
        for text, count in sorted(lost.items()):
            print(f"{path}: gone {count}x: {text}")
        for text, count in sorted(gained.items()):
            print(f"{path}: new {count}x: {text}")
        if lost:
            lost_any = True
        elif not gained:
            print(f"{path}: every string unchanged")
    return 1 if lost_any else 0


if __name__ == "__main__":
    sys.exit(main())
