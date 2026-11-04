#!/usr/bin/env python3
"""Post a review round's comments and edit a pull request's Revision section.

Usage:
    review_post.py revision OWNER/REPO#N --scratch DIR (--line TEXT | --file PATH) [--replace ITEM] [--dry-run]
    review_post.py comment --round R --anchor SHA --heading TEXT OWNER/REPO#N=HEAD=FILE [...] [--dry-run]

`revision` adds one numbered line to the body's `## Revision` section, or
replaces item ITEM. It adds the section before the closing line and footer of
a body that has none. It saves the body as read, sends only when every changed
line sits inside the section, and reads the body back. A line already in the
section is not added twice, so a retry changes nothing.

`comment` checks every pull request's head first, and posts on none of them if
any differs. It then skips a pull request that already carries this heading,
round and anchor, so a retry posts only what is missing.

review-round.md's steps 7 and 8 say why each check is here.
"""

import argparse
import difflib
import json
import os
import re
import subprocess
import sys
import tempfile

SPEC = re.compile(r"^(?P<repo>[\w.-]+/[\w.-]+)#(?P<num>\d+)$")
TARGET = re.compile(r"^(?P<repo>[\w.-]+/[\w.-]+)#(?P<num>\d+)=(?P<head>[0-9a-f]{7,40})=(?P<file>.+)$")
HEADING = re.compile(r"^#{1,6} ")
FENCE = re.compile(r"^ {0,3}(```|~~~)")
ITEM = re.compile(r"^(\d+)\. (.*)$")
CLOSING = re.compile(r"^(closes|fixes|resolves|part of)\b", re.IGNORECASE)
SECTION = "## Revision"
SECTION_END = "The review comments list each finding and what was refuted."


def run(*args):
    done = subprocess.run(args, capture_output=True, text=True)
    if done.returncode:
        sys.exit(f"{' '.join(args)} failed: {done.stderr.strip()}")
    return done.stdout


def view(repo, num, field):
    # --jq would print one newline more than the string holds, so parse the JSON.
    return json.loads(run("gh", "pr", "view", num, "-R", repo, "--json", field))[field]


def outside_fences(lines):
    fenced = False
    for i, line in enumerate(lines):
        if FENCE.match(line):
            fenced = not fenced
        elif not fenced:
            yield i, line


def find_section(lines):
    """Return (heading index, one past the section's last item), or None."""
    visible = list(outside_fences(lines))
    starts = [i for i, line in visible if line.rstrip("\r") == SECTION]
    if len(starts) > 1:
        sys.exit(f"the body has {len(starts)} {SECTION} headings, so the section is ambiguous")
    if not starts:
        return None
    end = starts[0] + 1
    for i, line in visible:
        if i <= starts[0]:
            continue
        if HEADING.match(line):
            break
        if ITEM.match(line.rstrip("\r")):
            end = i + 1
            while end < len(lines) and lines[end].startswith((" ", "\t")) and lines[end].strip():
                end += 1
    return starts[0], end


def items(lines, start, end):
    found = {}
    for i in range(start + 1, end):
        m = ITEM.match(lines[i].rstrip("\r"))
        if m:
            found[int(m[1])] = (i, m[2])
    return found


def insertion_point(lines):
    end = len(lines)
    while end and not lines[end - 1].strip():
        end -= 1
    if end and lines[end - 1].startswith("🤖"):
        end -= 1
        while end and not lines[end - 1].strip():
            end -= 1
        if end and CLOSING.match(lines[end - 1]):
            end -= 1
            while end and not lines[end - 1].strip():
                end -= 1
    return end


def splice(body, text, replace):
    """Return (new body, first changed line, one past the last), or None when there is nothing to do."""
    lines = body.split("\n")
    eol = "\r" if lines and lines[0].endswith("\r") else ""
    found = find_section(lines)
    if found is None:
        if replace is not None:
            sys.exit(f"the body has no {SECTION} section, so item {replace} does not exist")
        at = insertion_point(lines)
        added = ["", SECTION, "", f"1. {text}", "", SECTION_END]
        if at == len(lines):
            added.append("")
        return "\n".join(lines[:at] + [s + eol for s in added] + lines[at:]), at, at
    start, end = found
    current = items(lines, start, end)
    if replace is not None:
        if replace not in current:
            sys.exit(f"the {SECTION} section has no item {replace}")
        i = current[replace][0]
        stop = i + 1
        while stop < end and not ITEM.match(lines[stop].rstrip("\r")):
            stop += 1
        if lines[i:stop] == [f"{replace}. {text}{eol}"]:
            return None
        return "\n".join(lines[:i] + [f"{replace}. {text}{eol}"] + lines[stop:]), i, stop
    if any(existing == text for _, existing in current.values()):
        return None
    number = max(current, default=0) + 1
    added = [f"{number}. {text}{eol}"]
    if not current:
        added.insert(0, eol)
    return "\n".join(lines[:end] + added + lines[end:]), end, end


def changed_outside(old, new, first, last):
    """Lines of the old body a diff changed outside [first, last]. Runs apart from splice, as a second check."""
    a, b = old.split("\n"), new.split("\n")
    matcher = difflib.SequenceMatcher(None, a, b, autojunk=False)
    # An inserted block starts or ends with a blank line, and a diff may place it either side of the blank beside it.
    return [(i1, i2) for tag, i1, i2, _, _ in matcher.get_opcodes()
            if tag != "equal" and not (tag == "insert" and first - 1 <= i1 <= last + 1)
            and (i1 < first or i2 > last)]


def revision(args):
    m = SPEC.match(args.pull)
    if not m:
        sys.exit(f"not OWNER/REPO#N: {args.pull}")
    repo, num = m["repo"], m["num"]
    if args.file:
        with open(args.file, encoding="utf-8") as f:
            text = f.read().strip()
    else:
        text = args.line.strip()
    if not text or "\n" in text:
        sys.exit("a revision entry is one non-empty line")
    body = view(repo, num, "body")
    os.makedirs(args.scratch, exist_ok=True)
    saved = os.path.join(args.scratch, f"body-{repo.replace('/', '-')}-{num}.md")
    with open(saved, "w", encoding="utf-8", newline="") as f:
        f.write(body)
    done = splice(body, text, args.replace)
    if done is None:
        print(f"{repo}#{num}: the section already holds this line, so nothing changed")
        return
    new, first, last = done
    outside = changed_outside(body, new, first, last)
    if outside:
        sys.exit(f"{repo}#{num}: refusing to send, lines {outside} changed outside {SECTION}. The body as read is at {saved}")
    if args.dry_run:
        print("".join(difflib.unified_diff(body.splitlines(True), new.splitlines(True), "as read", "to send")))
        return
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", suffix=".md", dir=args.scratch, delete=False) as f:
        f.write(new)
        sent = f.name
    run("gh", "pr", "edit", num, "-R", repo, "--body-file", sent)
    back = view(repo, num, "body")
    if back != new:
        sys.exit(f"{repo}#{num}: the body read back differs from what was sent, so nothing was resent. "
                 f"As read before the edit: {saved}. As sent: {sent}")
    print(f"{repo}#{num}: {SECTION} updated and read back")


def carries(comment, heading, round_no, anchor):
    lines = comment.splitlines()
    return bool(lines) and lines[0].strip() == heading and anchor[:7] in comment \
        and re.search(rf"\bround {round_no}\b", comment, re.IGNORECASE) is not None


def comment(args):
    targets = []
    for spec in args.targets:
        m = TARGET.match(spec)
        if not m:
            sys.exit(f"not OWNER/REPO#N=HEAD=FILE: {spec}")
        if not os.path.isfile(m["file"]):
            sys.exit(f"no comment file at {m['file']}")
        targets.append(m)
    wrong = []
    for m in targets:
        head = view(m["repo"], m["num"], "headRefOid")
        if not head.startswith(m["head"]):
            wrong.append(f"{m['repo']}#{m['num']} is at {head[:7]}, not {m['head'][:7]}")
    if wrong:
        sys.exit("posting nothing, because a head does not match: " + "; ".join(wrong))
    for m in targets:
        name = f"{m['repo']}#{m['num']}"
        if any(carries(c["body"], args.heading, args.round, args.anchor) for c in view(m["repo"], m["num"], "comments")):
            print(f"{name}: already carries this heading, round and anchor, so skipped")
        elif args.dry_run:
            print(f"{name}: would post {m['file']}")
        else:
            run("gh", "pr", "comment", m["num"], "-R", m["repo"], "--body-file", m["file"])
            print(f"{name}: posted")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)

    edit = commands.add_parser("revision")
    edit.add_argument("pull")
    edit.add_argument("--scratch", required=True)
    entry = edit.add_mutually_exclusive_group(required=True)
    entry.add_argument("--line")
    entry.add_argument("--file")
    edit.add_argument("--replace", type=int)
    edit.add_argument("--dry-run", action="store_true")
    edit.set_defaults(handler=revision)

    post = commands.add_parser("comment")
    post.add_argument("targets", nargs="+")
    post.add_argument("--round", type=int, required=True)
    post.add_argument("--anchor", required=True)
    post.add_argument("--heading", required=True)
    post.add_argument("--dry-run", action="store_true")
    post.set_defaults(handler=comment)

    args = parser.parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
