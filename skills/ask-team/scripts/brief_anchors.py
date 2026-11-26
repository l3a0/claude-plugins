#!/usr/bin/env python3
"""Print the "Subject and anchors" list of a review brief, or write the next round's brief from the last.

Usage:
    brief_anchors.py OWNER/REPO#N[=CHECKOUT] [OWNER/REPO#N[=CHECKOUT] ...]
    brief_anchors.py --next PREVIOUS_BRIEF --out NEW_BRIEF OWNER/REPO#N=HEAD [OWNER/REPO#N=HEAD ...]
    brief_anchors.py --next PREVIOUS_BRIEF --out NEW_BRIEF HEAD

The first form prints one numbered item per pull request, with its head
commit, the merge base it is diffed against, its branch, its checkout and its
diff command. The merge base comes from GitHub's compare API rather than the
base branch's tip, so a base that moved after the branch was cut adds nothing
to the diff. A checkout whose HEAD is not the pull request's head is flagged,
because a lens reading it would review other code than the anchor. Each item
ends with a placeholder paragraph for what the pull request changes, which the
session writes by hand.

The `--next` form reads a brief this script's items anchor, and writes the
next round's brief to NEW_BRIEF. HEAD is the commit the next round anchors at,
named for every pull request the brief lists, or bare when it lists one. It
changes four things and keeps every other line.

1. The round number at the end of the title goes up by one.
2. Each item's first line is printed again from GitHub, as the first form
   prints it, so a merge of the base moves the merge base too. It stops when
   GitHub's head is not the HEAD given, because the brief would anchor at a
   commit no one pushed. The line's list of earlier rounds' anchors gains
   the round just finished and its head.
3. Every `archive <commit>` that names a pull request's old head names its new
   one. One that names another commit stops the run.
4. The paragraph that starts `This round reads`, with any list right under
   it and the indented lines inside that list, is replaced by a blank, in
   angle brackets, for the session to fill. Each of those list lines is named
   on standard error. A
   brief with no such paragraph gets the blank after its items, which ends at
   the first line that is neither blank nor indented.

It also stops on an item's first line that holds anything it did not print,
such as a description an older version put there, because a reprint would
drop it. It writes nothing when it stops, and refuses a NEW_BRIEF that already exists,
so a rerun cannot overwrite a brief the session has filled. On standard error
it names each other line that still names an old head, for the session to
read.
"""

import json
import os
import re
import subprocess
import sys

SPEC = re.compile(r"^(?P<repo>[\w.-]+/[\w.-]+)#(?P<num>\d+)(?:=(?P<checkout>.+))?$")
NEXT_SPEC = re.compile(r"^(?:(?P<repo>[\w.-]+/[\w.-]+)#(?P<num>\d+)=)?(?P<head>[0-9a-f]{7,40})$")
PLAIN_REF = re.compile(r"^[\w./-]+$")
TITLE = re.compile(r"^(# .*, round )(\d+)\s*$")
ITEM = re.compile(r"^(?P<n>\d+)\. \*\*(?P<repo>[\w.-]+/[\w.-]+) PR #(?P<num>\d+)\*\*, head `(?P<head>[0-9a-f]{7,40})`")
CHECKOUT = re.compile(r" Checkout: `(?P<checkout>[^`]+)` \(branch ")
EARLIER = re.compile(r" Earlier rounds read (?P<list>round \d+ `[0-9a-f]{7,40}`(?:, round \d+ `[0-9a-f]{7,40}`)*)\.\s*$")
EARLIER_ITEM = re.compile(r"round (\d+) `([0-9a-f]{7,40})`")
ARCHIVE = re.compile(r"\barchive\s+([0-9a-f]{7,40})\b")
READS = ("This round reads", "<This round reads", "<From round 2 on,")
LIST_LINE = re.compile(r"^\s*(\d+[.)]|[-*+])\s")
REF_FORM = r"(?:`[\w./-]+`|\*\*unusual branch name .+?\*\*)"
# The whole first line as anchor() prints it, with the list --next adds. Anything else on it is the session's text,
# which a reprint would drop.
PRINTED = re.compile(
    rf"^\d+\. \*\*[\w.-]+/[\w.-]+ PR #\d+\*\*, head `[0-9a-f]{{7}}`, base `[0-9a-f]{{7}}` on {REF_FORM}\."
    rf"(?: Checkout: `[^`]+` \(branch {REF_FORM}\)\.(?: \*\*Checkout HEAD is `[0-9a-f]{{7}}`, not the head\. "
    rf"Update it first\.\*\*)?| Branch {REF_FORM}, no checkout given\.)(?: \*\*State: [A-Z_]+\.\*\*)?"
    rf" Diff: `git diff [0-9a-f]{{7}} [0-9a-f]{{7}}`\."
    rf"(?: Earlier rounds read round \d+ `[0-9a-f]{{7,40}}`(?:, round \d+ `[0-9a-f]{{7,40}}`)*\.)?\s*$")


def ref(name):
    # A fork's author picks its branch name, and git allows backticks in one,
    # so a name outside the plain set is printed flagged rather than in a code span.
    if PLAIN_REF.match(name):
        return f"`{name}`"
    return f"**unusual branch name {name!r}**"


def run(*args):
    done = subprocess.run(args, capture_output=True, text=True)
    if done.returncode:
        sys.exit(f"{' '.join(args)} failed: {done.stderr.strip()}")
    return done.stdout.strip()


def anchor(repo, num, checkout):
    """Return the item's first line, without its number, and the pull request's full head."""
    pr = json.loads(run("gh", "pr", "view", num, "-R", repo,
                        "--json", "headRefOid,headRefName,baseRefName,state"))
    head = pr["headRefOid"]
    base = run("gh", "api", f"repos/{repo}/compare/{pr['baseRefName']}...{head}",
               "--jq", ".merge_base_commit.sha")
    line = (f"**{repo} PR #{num}**, head `{head[:7]}`, base `{base[:7]}` "
            f"on {ref(pr['baseRefName'])}.")
    if checkout:
        line += f" Checkout: `{checkout}` (branch {ref(pr['headRefName'])})."
        local = run("git", "-C", checkout, "rev-parse", "HEAD")
        if local != head:
            line += f" **Checkout HEAD is `{local[:7]}`, not the head. Update it first.**"
    else:
        line += f" Branch {ref(pr['headRefName'])}, no checkout given."
    if pr["state"] != "OPEN":
        line += f" **State: {pr['state']}.**"
    line += f" Diff: `git diff {base[:7]} {head[:7]}`."
    return line, head


def same(a, b):
    return a.startswith(b) or b.startswith(a)


def placeholder(n):
    return " " * len(f"{n}. ") + "<What it changes.>"


def print_anchors(specs):
    for i, spec in enumerate(specs, 1):
        m = SPEC.match(spec)
        if not m:
            sys.exit(f"not OWNER/REPO#N[=CHECKOUT]: {spec}")
        line, _ = anchor(m["repo"], m["num"], m["checkout"])
        if i > 1:
            print()
        print(f"{i}. {line}\n\n{placeholder(i)}")


def paragraph_end(lines, i):
    while i < len(lines) and lines[i].strip():
        i += 1
    return i


def next_brief(previous, out, specs):
    if os.path.exists(out):
        sys.exit(f"{out} already exists. Writing nothing, so a brief already filled is not overwritten")
    with open(previous, encoding="utf-8") as f:
        lines = f.read().split("\n")

    title = next((i for i, line in enumerate(lines) if line.startswith("# ")), None)
    m = TITLE.match(lines[title]) if title is not None else None
    if not m:
        sys.exit(f"{previous}: the title does not end ', round <N>', so the round is unknown")
    finished = int(m[2])
    lines[title] = f"{m[1]}{finished + 1}"

    items = [(i, ITEM.match(line)) for i, line in enumerate(lines) if ITEM.match(line)]
    if not items:
        sys.exit(f"{previous}: no item in the form brief_anchors.py prints, so no head is known")
    names = [f"{it['repo']}#{it['num']}" for _, it in items]
    if len(set(n.lower() for n in names)) != len(names):
        sys.exit(f"{previous}: a pull request is listed twice")

    heads = {}
    for spec in specs:
        s = NEXT_SPEC.match(spec)
        if not s:
            sys.exit(f"not OWNER/REPO#N=HEAD or HEAD: {spec}")
        if s["repo"] is None:
            if len(specs) != 1 or len(names) != 1:
                sys.exit("a bare HEAD works only for a brief that lists one pull request")
            key = names[0].lower()
        else:
            key = f"{s['repo']}#{s['num']}".lower()
        if key not in (n.lower() for n in names):
            sys.exit(f"{spec}: the brief lists no such pull request")
        heads[key] = s["head"]
    missing = [n for n in names if n.lower() not in heads]
    if missing:
        sys.exit(f"name the head for every pull request the brief lists. Missing: {', '.join(missing)}")

    for i, it in items:
        if not PRINTED.match(lines[i]):
            sys.exit(f"{previous}: line {i + 1} holds text the script did not print, such as a description written "
                     f"on {it['repo']} PR #{it['num']}'s first line, which a reprint would drop. Move that text to an "
                     f"indented paragraph under the item, then rerun. Writing nothing")

    moves = []
    for i, it in items:
        old = it["head"]
        earlier = EARLIER.search(lines[i])
        rounds = [(int(r), h) for r, h in EARLIER_ITEM.findall(earlier["list"])] if earlier else []
        expected = list(range(1, finished))
        if [r for r, _ in rounds] != expected:
            have = ", ".join(str(r) for r, _ in rounds) or "none"
            sys.exit(f"{previous}: {it['repo']} PR #{it['num']} lists earlier rounds {have}, but the title says "
                     f"round {finished}, so its anchors are not all known. Fix that line's 'Earlier rounds read' "
                     f"list by hand first")
        checkout = CHECKOUT.search(lines[i])
        line, head = anchor(it["repo"], it["num"], checkout["checkout"] if checkout else None)
        want = heads[f"{it['repo']}#{it['num']}".lower()]
        if not same(head, want):
            sys.exit(f"{it['repo']} PR #{it['num']} is at {head[:7]} on GitHub, not {want[:7]}. Push the fix "
                     f"first, or name the head GitHub shows. Writing nothing")
        rounds.append((finished, old))
        listed = ", ".join(f"round {r} `{h}`" for r, h in rounds)
        lines[i] = f"{it['n']}. {line} Earlier rounds read {listed}."
        moves.append((it, old, head[:7], checkout["checkout"] if checkout else "<checkout>"))

    diffs = "; ".join(f"`git -C {where} diff {old} {new}` on {it['repo']} PR #{it['num']}"
                      for it, old, new, where in moves)
    blank = (f"<This round reads round {finished}'s fixes: {diffs}, leaving out what a merge of the base "
             "brought, and any passage or function that diff touches or that states the same fact. Name those "
             "here, say so where a fix rewrote the subject and the round reads the whole change, and remove the "
             "angle brackets.>")
    start = next((i for i, line in enumerate(lines) if line.startswith(READS)), None)
    if start is not None:
        end = paragraph_end(lines, start)
        # A list right under the paragraph, such as the commits it read, belongs to it, with or without a blank
        # line above it, and so do the indented lines inside that list. Each list line is named on standard error,
        # since it may have been meant to stay.
        first = next((k for k in range(start + 1, end) if LIST_LINE.match(lines[k])), end)
        listed = first < end
        while True:
            after = end
            while after < len(lines) and not lines[after].strip():
                after += 1
            if after < len(lines) and not ITEM.match(lines[after]) and (
                    LIST_LINE.match(lines[after]) or (listed and lines[after][0] in " \t")):
                end, listed = paragraph_end(lines, after), True
            else:
                break
        for line in lines[first:end]:
            if line.strip():
                print(f"replaced with the paragraph on what round {finished} read: {line.strip()}", file=sys.stderr)
        lines[start:end] = [blank]
    else:
        at = items[-1][0] + 1
        while at < len(lines) and (not lines[at].strip() or lines[at][0] in " \t"):
            at += 1
        while at > items[-1][0] + 1 and not lines[at - 1].strip():
            at -= 1
        lines[at:at] = ["", blank]
    reads = lines.index(blank)

    # The old paragraph is gone by now, so an earlier round's commit it named stops nothing.
    def archived(match):
        sha = match[1]
        for _, old, new, _ in moves:
            if same(sha, old):
                return f"archive {new}"
        sys.exit(f"{previous}: an archive line names {sha}, which is no pull request's round {finished} head. "
                 f"Fix it by hand first. Writing nothing")

    lines = [ARCHIVE.sub(archived, line) for line in lines]

    skip = {i for i, _ in items} | {reads}
    for n, line in enumerate(lines, 1):
        if n - 1 in skip:
            continue
        for it, old, new, _ in moves:
            if old != new and re.search(rf"\b{old}", line):
                print(f"line {n} still names round {finished}'s head {old} of {it['repo']} PR #{it['num']}: "
                      f"{line.strip()}", file=sys.stderr)

    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "x", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"wrote round {finished + 1}'s brief to {out}. Fill the blank that starts '<This round reads', and add "
          f"the owner's rulings since round {finished} to the facts", file=sys.stderr)


def main(argv):
    if not argv:
        sys.exit(__doc__)
    if argv[0] != "--next":
        print_anchors(argv)
        return
    if len(argv) < 5 or argv[2] != "--out":
        sys.exit("usage: brief_anchors.py --next PREVIOUS_BRIEF --out NEW_BRIEF OWNER/REPO#N=HEAD [...]")
    next_brief(argv[1], argv[3], argv[4:])


if __name__ == "__main__":
    main(sys.argv[1:])
