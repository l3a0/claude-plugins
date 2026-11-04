#!/usr/bin/env python3
"""Post a review round's comments and edit a pull request's Revision section.

Usage:
    review_post.py revision OWNER/REPO#N --scratch DIR --line TEXT [--replace ITEM] [--dry-run]
    review_post.py comment --round R --heading TEXT OWNER/REPO#N=HEAD=ANCHOR=FILE [...] [--dry-run]

`revision` adds one numbered line to the body's `## Revision` section, or
replaces item ITEM, and adds the section before the closing lines and footer
of a body that has none. The section runs from its heading to its last
numbered item. Each run saves the body as read to a file of its own. It sends
only when every changed line sits inside the section and a second run would
change nothing, and it reads the body back. A line already in the section is
not added twice, so a retry changes nothing.

`comment` refuses a file that does not itself carry the heading, the round, its
anchor and the head, because a retry could not recognise that post. It then
checks every pull request's head, and every earlier comment by the same login,
since anyone can comment on a public pull request, and posts on none of them if
a head differs or an earlier comment has the same key with other text or twice
over. It skips a pull request that already carries this comment, so a retry
posts only what is missing. GitHub takes no key on a comment, so this narrows
the window for a double post rather than closing it.

A write that fails says the outcome is unknown, since the request may have
landed. Rerun the same command, which looks before it writes. The tests run
against a stand-in `gh`, so no test covers what the real one prints.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

SPEC = re.compile(r"^(?P<repo>[\w.-]+/[\w.-]+)#(?P<num>\d+)$")
TARGET = re.compile(r"^(?P<repo>[\w.-]+/[\w.-]+)#(?P<num>\d+)=(?P<head>[0-9a-f]{7,40})=(?P<anchor>[0-9a-f]{7,40})=(?P<file>.+)$")
HEADING = re.compile(r"^ {0,3}#{1,6}(\s|$)")
REVISION = re.compile(r"^ {0,3}#{1,6}\s+Revision\s*$")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
ITEM = re.compile(r"^(\d+)\. (.*)$")
CLOSING = re.compile(r"^(close[sd]?|fix(es|ed)?|resolve[sd]?|part of)\s+(no issue|([\w.-]+/[\w.-]+)?#\d+)", re.IGNORECASE)
SECTION = "## Revision"


def run(*args):
    done = subprocess.run(args, capture_output=True, text=True)
    if done.returncode:
        sys.exit(f"{' '.join(args)} failed: {done.stderr.strip()}")
    return done.stdout


def write(*args, where=""):
    done = subprocess.run(args, capture_output=True, text=True)
    if done.returncode:
        sys.exit(f"{' '.join(args[:3])} exited {done.returncode}, so the outcome is unknown. "
                 f"Rerun this command, which looks before it writes. {where}{done.stderr.strip()}")
    return done.stdout.strip()


def view(repo, num, field):
    # --jq would print one newline more than the string holds, so parse the JSON.
    return json.loads(run("gh", "pr", "view", num, "-R", repo, "--json", field))[field]


def outside_fences(lines):
    fence = None
    for i, line in enumerate(lines):
        m = FENCE.match(line.rstrip("\r"))
        if fence is None:
            if m and not (m[1][0] == "`" and "`" in m[2]):
                fence = m[1]
            else:
                yield i, line
        elif m and m[1][0] == fence[0] and len(m[1]) >= len(fence) and not m[2].strip():
            fence = None


def find_section(lines):
    """Return (heading index, one past the section's last item), or None."""
    visible = list(outside_fences(lines))
    starts = [i for i, line in visible if REVISION.match(line.rstrip("\r"))]
    if len(starts) > 1:
        sys.exit(f"the body has {len(starts)} Revision headings, so the section is ambiguous. Edit it by hand")
    if not starts:
        return None
    if lines[starts[0]].rstrip() != SECTION:
        sys.exit(f"the Revision heading is not written {SECTION!r}. Edit it by hand")
    end = starts[0] + 1
    seen = False
    for i, line in visible:
        if i <= starts[0]:
            continue
        plain = line.rstrip("\r")
        if HEADING.match(plain):
            break
        if ITEM.match(plain):
            end, seen = i + 1, True
        elif plain.strip():
            if not seen or not plain.startswith((" ", "\t")):
                break
            end = i + 1
    return starts[0], end


def items(lines, start, end):
    found = {}
    for i in range(start + 1, end):
        m = ITEM.match(lines[i].rstrip("\r"))
        if m:
            if int(m[1]) in found:
                sys.exit(f"the {SECTION} section numbers two items {m[1]}, so a retry could not find its line. Edit it by hand")
            found[int(m[1])] = (i, m[2])
    return found


def insertion_point(lines):
    def trim(end):
        while end and not lines[end - 1].strip():
            end -= 1
        return end

    end = trim(len(lines))
    if end and lines[end - 1].startswith("🤖"):
        end = trim(end - 1)
    while end and CLOSING.match(lines[end - 1].rstrip("\r")):
        end = trim(end - 1)
    return end


def splice(body, text, replace):
    """Return the new body, or None when there is nothing to do."""
    lines = body.split("\n")
    eol = "\r" if lines and lines[0].endswith("\r") else ""
    found = find_section(lines)
    if found is None:
        if replace is not None:
            sys.exit(f"the body has no {SECTION} section, so item {replace} does not exist")
        at = insertion_point(lines)
        added = ["", SECTION, "", f"1. {text}"]
        if at == len(lines) or lines[at].strip():
            added.append("")
        return "\n".join(lines[:at] + [s + eol for s in added] + lines[at:])
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
        return "\n".join(lines[:i] + [f"{replace}. {text}{eol}"] + lines[stop:])
    if any(existing == text for _, existing in current.values()):
        return None
    added = [f"{max(current, default=0) + 1}. {text}{eol}"]
    if not current:
        added.insert(0, eol)
    return "\n".join(lines[:end] + added + lines[end:])


def changed_outside(old, new):
    """True when new differs from old outside the section. Reads the bounds from old, apart from splice."""
    a, b = old.split("\n"), new.split("\n")
    found = find_section(a)
    first, last = (found[0] + 1, found[1]) if found else (insertion_point(a),) * 2
    if last < len(a) and not a[last].strip():
        last += 1
    shared = min(len(a), len(b))
    head = 0
    while head < shared and a[head] == b[head]:
        head += 1
    tail = 0
    while tail < shared - head and a[-1 - tail] == b[-1 - tail]:
        tail += 1
    return head < first or len(a) - tail > last


def keep(prefix, folder, text):
    fd, path = tempfile.mkstemp(prefix=prefix, suffix=".md", dir=folder)
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    return path


def revision(args):
    m = SPEC.match(args.pull)
    if not m:
        sys.exit(f"not OWNER/REPO#N: {args.pull}")
    repo, num = m["repo"], m["num"]
    text = args.line.strip()
    if not text or "\n" in text or "\r" in text:
        sys.exit("a revision entry is one non-empty line")
    body = view(repo, num, "body")
    os.makedirs(args.scratch, exist_ok=True)
    name = f"body-{repo.replace('/', '-')}-{num}-"
    saved = keep(name, args.scratch, body)
    new = splice(body, text, args.replace)
    if new is None:
        print(f"{repo}#{num}: the section already holds this line, so nothing changed")
        return
    if changed_outside(body, new):
        sys.exit(f"{repo}#{num}: refusing to send, a line changed outside {SECTION}. The body as read is at {saved}")
    if splice(new, text, args.replace) is not None:
        sys.exit(f"{repo}#{num}: refusing to send, a second run would change the body again, so {SECTION} "
                 f"was not found as written. Edit it by hand. The body as read is at {saved}")
    if args.dry_run:
        old = set(body.split("\n"))
        print("".join(f"+{line}\n" for line in new.split("\n") if line not in old))
        return
    sent = keep("sent-" + name, args.scratch, new)
    write("gh", "pr", "edit", num, "-R", repo, "--body-file", sent, where=f"As read: {saved}. As sent: {sent}. ")
    if view(repo, num, "body") != new:
        sys.exit(f"{repo}#{num}: the body read back differs from what was sent, so nothing was resent. "
                 f"As read before the edit: {saved}. As sent: {sent}")
    print(f"{repo}#{num}: {SECTION} updated and read back")


def carries(comment, heading, round_no, anchor):
    lines = comment.splitlines()
    return bool(lines) and lines[0].strip() == heading and anchor[:7] in comment \
        and re.search(rf"\bround {round_no}\b", comment, re.IGNORECASE) is not None


def comment(args):
    targets, seen = [], set()
    for spec in args.targets:
        m = TARGET.match(spec)
        if not m:
            sys.exit(f"not OWNER/REPO#N=HEAD=ANCHOR=FILE: {spec}")
        if not os.path.isfile(m["file"]):
            sys.exit(f"no comment file at {m['file']}")
        with open(m["file"], encoding="utf-8") as f:
            text = f.read()
        if not carries(text, args.heading, args.round, m["anchor"]):
            sys.exit(f"posting nothing, because {m['file']} does not start with {args.heading!r} and name "
                     f"round {args.round} and {m['anchor'][:7]}, so a retry could not recognise it")
        if m["head"][:7] not in text:
            sys.exit(f"posting nothing, because {m['file']} does not name the head {m['head'][:7]}")
        pull = f"{m['repo']}#{m['num']}"
        if pull in seen:
            sys.exit(f"posting nothing, because {pull} is named twice")
        seen.add(pull)
        targets.append((m, text))
    wrong = []
    for m, _ in targets:
        head = view(m["repo"], m["num"], "headRefOid")
        if not head.startswith(m["head"]):
            wrong.append(f"{m['repo']}#{m['num']} is at {head[:7]}, not {m['head'][:7]}")
    if wrong:
        sys.exit("posting nothing, because a head does not match: " + "; ".join(wrong))
    login = run("gh", "api", "user", "--jq", ".login").strip()
    pending = []
    for m, text in targets:
        name = f"{m['repo']}#{m['num']}"
        mine = [c["body"] for c in view(m["repo"], m["num"], "comments")
                if (c.get("author") or {}).get("login") == login
                and carries(c["body"], args.heading, args.round, m["anchor"])]
        if any(body.strip() != text.strip() for body in mine):
            sys.exit(f"posting nothing, because {name} already carries this heading, round and anchor with "
                     "different text. Report it, and post by hand once it is settled")
        if len(mine) > 1:
            sys.exit(f"posting nothing, because {name} already carries this comment {len(mine)} times. Report it")
        if mine:
            print(f"{name}: already carries this comment, so skipped")
        else:
            pending.append((name, m))
    for name, m in pending:
        if args.dry_run:
            print(f"{name}: would post {m['file']}")
        else:
            print(f"{name}: posted {write('gh', 'pr', 'comment', m['num'], '-R', m['repo'], '--body-file', m['file'])}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)

    edit = commands.add_parser("revision")
    edit.add_argument("pull")
    edit.add_argument("--scratch", required=True)
    edit.add_argument("--line", required=True)
    edit.add_argument("--replace", type=int)
    edit.add_argument("--dry-run", action="store_true")
    edit.set_defaults(handler=revision)

    post = commands.add_parser("comment")
    post.add_argument("targets", nargs="+")
    post.add_argument("--round", type=int, required=True)
    post.add_argument("--heading", required=True)
    post.add_argument("--dry-run", action="store_true")
    post.set_defaults(handler=comment)

    args = parser.parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
