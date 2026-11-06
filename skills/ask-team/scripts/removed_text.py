#!/usr/bin/env python3
"""List the text a round's fix removes, and where each piece still stands in any companion.

Usage:
    removed_text.py [--min-words N] CHECKOUT=FROM..TO [CHECKOUT=FROM..TO ...]

Each argument names a pull request's checkout and the commits the fix runs between, usually the round's anchor and
the commit about to be pushed. For each one the script takes every run of at least N removed words from git's word
diff, prints it under its file, and searches the tracked text of every checkout at its TO commit for any N words of
the run in a row. So a sentence cut from one pull request and left in its companion shows as `still in`, and the list
of runs is what the round's comment has to describe. A run also shows as `still in` where the fix moved it or kept
its words, so each hit needs reading. It changes nothing, and exits 0 either way.

A file holding a NUL byte counts as binary and is not searched, whatever its name. Matching folds case and joins words across line breaks, so a sentence wrapped differently in each repository still
matches. Only the removed words are searched, so a sentence reworded in a companion does not show.
"""

import argparse
import re
import subprocess
import sys

SPEC = re.compile(r"^(?P<checkout>.+)=(?P<base>[^=\s]+?)\.\.(?P<head>[^=\s]+)$")
TEXT_FILE = re.compile(r"\.(md|py|sh|json|ya?ml|txt)$")


def git(checkout, *args):
    done = subprocess.run(["git", "-C", checkout, *args], capture_output=True)
    if done.returncode:
        sys.exit(f"git {' '.join(args)} failed in {checkout}: {done.stderr.decode(errors='replace').strip()}")
    return done.stdout.decode(errors="replace")


def words(text):
    return re.findall(r"\S+", text.lower())


def removed_runs(diff, min_words):
    """Yield (path, text) for each run of removed words at least min_words long in a porcelain word diff.

    Inside a hunk a line's first character says what it is, so a removed line that reads like a header stays text.
    A `~` only marks a line end, so a run carries across it.
    """
    path, run, in_hunk = None, [], False

    def flush():
        nonlocal run
        text = " ".join(run)
        run = []
        return (path, text) if len(words(text)) >= min_words else None

    for line in diff.splitlines():
        if line.startswith("diff --git a/"):
            found = flush()
            if found:
                yield found
            rest = line[len("diff --git a/"):]
            path, in_hunk = rest[:(len(rest) - len(" b/")) // 2], False
        elif line.startswith("@@"):
            found = flush()
            if found:
                yield found
            in_hunk = True
        elif in_hunk and line.startswith("-"):
            run.append(line[1:].strip())
        elif in_hunk and line.startswith((" ", "+")):
            found = flush()
            if found:
                yield found
    found = flush()
    if found:
        yield found


def tracked_text(checkout, commit):
    """Return {path: [(line number, word), ...]} for the tracked text files at a commit."""
    files = {}
    for path in git(checkout, "ls-tree", "-r", "--name-only", commit).splitlines():
        if not TEXT_FILE.search(path):
            continue
        text, tokens = git(checkout, "show", f"{commit}:{path}"), []
        if "\0" in text:
            continue
        for number, line in enumerate(text.splitlines(), 1):
            tokens.extend((number, word) for word in words(line))
        files[path] = tokens
    return files


def index(tracked, size):
    """Map each run of size words to where it stands in a checkout's tracked text, as {path: first line}."""
    places = {}
    for path, tokens in tracked.items():
        for at in range(len(tokens) - size + 1):
            key = tuple(word for _, word in tokens[at:at + size])
            places.setdefault(key, {}).setdefault(path, tokens[at][0])
    return places


def still_in(text, places, size):
    """Return (path, line) for each file where any size words of the run in a row still stand."""
    run, hits = words(text), {}
    for at in range(len(run) - size + 1):
        for path, line in places.get(tuple(run[at:at + size]), {}).items():
            hits.setdefault(path, line)
    return sorted(hits.items())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--min-words", type=int, default=5)
    parser.add_argument("specs", nargs="+", metavar="CHECKOUT=FROM..TO")
    args = parser.parse_args(argv)
    if args.min_words < 1:
        parser.error("--min-words must be at least 1")
    specs = []
    for spec in args.specs:
        match = SPEC.match(spec)
        if not match or "..." in spec.rpartition("=")[2]:
            parser.error(f"{spec!r} is not CHECKOUT=FROM..TO")
        specs.append(match.groupdict())
    tracked = [(spec["checkout"], index(tracked_text(spec["checkout"], spec["head"]), args.min_words)) for spec in specs]
    for spec in specs:
        diff = git(spec["checkout"], "-c", "core.quotepath=off", "diff", "--no-color", "--no-ext-diff", "--no-renames",
                   "--src-prefix=a/", "--dst-prefix=b/", "--word-diff=porcelain", "-U0", spec["base"], spec["head"], "--")
        runs = list(removed_runs(diff, args.min_words))
        print(f"{spec['checkout']} {spec['base']}..{spec['head']}: {len(runs)} removed run(s)")
        for path, text in runs:
            print(f"- {path}: {text}")
            for checkout, places in tracked:
                for hit_path, line in still_in(text, places, args.min_words):
                    print(f"    still in {checkout}: {hit_path}:{line}")


if __name__ == "__main__":
    main()
