#!/usr/bin/env python3
"""List the test functions a fix removes, between the last reviewed head and the commit about to be pushed.

Usage:
    removed_tests.py [--path DIR ...] CHECKOUT=FROM..TO [CHECKOUT=FROM..TO ...]

A fix that deletes a test also deletes the check it made, and a diff of hundreds of lines hides that. So for each
argument the script reads every `.py` file under each DIR, `tests` by default, at FROM and at TO, and prints each
name defined with `def test...` or `async def test...` that FROM holds more often than TO, with the files that held
it at each commit. A test moved to another file, or kept while its body changed, does not show. A test renamed shows
under its old name, and so does a test a merge of the base removed, so each name needs reading: a rename or a merge
into another test keeps its check, and a test cut outright removes one. It reads the commits rather than the working
tree, changes nothing, and exits 0 either way.

It matches the names by pattern, as pytest's default does, so a function a decorator or a conftest hides from pytest
still counts, and a test generated at run time, such as one a parametrize id names, does not. A DIR that FROM does
not hold stops the run, because an empty list would read as no test removed.
"""

import argparse
import collections
import re
import subprocess
import sys

SPEC = re.compile(r"^(?P<checkout>.+)=(?P<base>[^=\s]+?)\.\.(?P<head>[^=\s]+)$")
TEST = re.compile(r"^[ \t]*(?:async[ \t]+)?def[ \t]+(test\w*)[ \t]*\(", re.MULTILINE)


def git(checkout, *args, stdin=None):
    done = subprocess.run(["git", "-C", checkout, *args], input=stdin, capture_output=True)
    if done.returncode:
        sys.exit(f"git {' '.join(args)} failed in {checkout}: {done.stderr.decode(errors='replace').strip()}")
    return done.stdout


def commit(checkout, name):
    done = subprocess.run(["git", "-C", checkout, "rev-parse", "--verify", "--quiet", f"{name}^{{commit}}"],
                          capture_output=True, text=True)
    if done.returncode:
        sys.exit(f"{name} is not a commit in {checkout}")
    return done.stdout.strip()


def files(checkout, commit, paths, required):
    listed = []
    for path in paths:
        found = git(checkout, "ls-tree", "-r", "-z", "--name-only", commit, "--", path).decode().split("\0")
        found = [f for f in found if f]
        if required and not found:
            sys.exit(f"{checkout} holds nothing at {path} in {commit}, so no test could be read there")
        listed += [f for f in found if f.endswith(".py")]
    return sorted(set(listed))


def tests(checkout, commit, paths, required):
    """Return {name: [file, ...]} with a file listed once per definition."""
    names = collections.defaultdict(list)
    listed = files(checkout, commit, paths, required)
    odd = [f for f in listed if "\n" in f]
    if odd:
        sys.exit(f"{checkout} has a file name holding a line break at {commit}, which this script cannot read: {odd[0]!r}")
    if not listed:
        return names
    out = git(checkout, "cat-file", "--batch", stdin="".join(f"{commit}:{f}\n" for f in listed).encode())
    at = 0
    for path in listed:
        header_end = out.index(b"\n", at)
        size = int(out[at:header_end].split()[2])
        body = out[header_end + 1:header_end + 1 + size].decode(errors="replace")
        at = header_end + 1 + size + 1
        for name in TEST.findall(body):
            names[name].append(path)
    return names


def report(spec, paths):
    m = SPEC.match(spec)
    if not m:
        sys.exit(f"not CHECKOUT=FROM..TO: {spec}")
    checkout = m["checkout"]
    base, head = commit(checkout, m["base"]), commit(checkout, m["head"])
    before, after = tests(checkout, base, paths, True), tests(checkout, head, paths, False)
    gone = sorted(name for name in before if len(before[name]) > len(after.get(name, [])))
    print(f"{checkout} {m['base']}..{m['head']}: {len(gone)} test name(s) gone")
    for name in gone:
        was = ", ".join(before[name])
        now = ", ".join(after[name]) if name in after else "no file"
        print(f"- {name}: was in {was}; now in {now}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--path", action="append", help="folder to read, repeatable (default: tests)")
    parser.add_argument("ranges", nargs="+", metavar="CHECKOUT=FROM..TO")
    args = parser.parse_args()
    for spec in args.ranges:
        report(spec, args.path or ["tests"])


if __name__ == "__main__":
    main()
