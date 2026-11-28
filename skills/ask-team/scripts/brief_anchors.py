#!/usr/bin/env python3
"""Print the "Subject and anchors" list of a review brief, or write the next round's brief from the last.

Usage:
    brief_anchors.py OWNER/REPO#N[=CHECKOUT] [OWNER/REPO#N[=CHECKOUT] ...]
    brief_anchors.py --next PREVIOUS_BRIEF --out NEW_BRIEF [--fix OWNER/REPO#N=FIX ...] OWNER/REPO#N=HEAD [...]
    brief_anchors.py --next PREVIOUS_BRIEF --out NEW_BRIEF [--fix FIX] HEAD

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
named for every pull request the brief lists, or bare when it lists one. FIX is
the commit that holds the last round's fixes, where a later commit, such as a
merge of the base, sits on top of it. It defaults to HEAD, and the run stops on
a FIX that GitHub does not show as HEAD or an ancestor of it. Where the last
round's head is not FIX or an ancestor of it, it stops when HEAD still holds
that head, because FIX then names a commit from before the round's fixes. When
HEAD does not hold it, as after a force push such as a rebase, it says so on
standard error and writes the brief, because the diff from that head to FIX
then holds the whole rebase rather than the round's fixes. That pull request's
part of the blank then names the whole change, from the merge base to HEAD,
as review-round.md's step 1 says. It stops, writing nothing, when GitHub cannot
compare the two, such as for a head it no longer holds, or gives an answer it
does not document. The run changes four things and keeps every other line.

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
   angle brackets, for the session to fill. The blank names the diff from
   the last round's head to FIX, or the whole change for a pull request a
   force push replaced. It reads the Markdown by pattern
   rather than with a parser, so each line it replaces from the first one that
   starts like a list item on is named on standard error, where a misread
   shows. It never replaces an item line. A
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
# Inside a paragraph only a list that starts at 1, or a bullet, begins a list, as in Markdown, so a wrapped line
# such as "2026. It also reads" stays prose.
LIST_IN_PARAGRAPH = re.compile(r"^\s*(1[.)]|[-*+])\s")
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
    """Return the item's first line, without its number, the pull request's full head and its merge base."""
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
    return line, head, base


# The four answers GitHub documents. Two different commits never compare "identical", which is listed because GitHub
# documents it, not because a run reaches it.
STATUSES = ("ahead", "behind", "diverged", "identical")


def status(repo, base, head):
    """GitHub's compare status of head against base, stopping on a failure or an answer GitHub does not document."""
    answer = run("gh", "api", f"repos/{repo}/compare/{base}...{head}", "--jq", ".status")
    if answer not in STATUSES:
        sys.exit(f"GitHub compared {base[:7]} with {head[:7]} on {repo} and answered {answer!r}, which is none of "
                 f"{', '.join(STATUSES)}. Writing nothing")
    return answer


def same(a, b):
    return a.startswith(b) or b.startswith(a)


def placeholder(n):
    return " " * len(f"{n}. ") + "<What it changes.>"


def print_anchors(specs):
    matches, seen = [], set()
    for spec in specs:
        m = SPEC.match(spec)
        if not m:
            sys.exit(f"not OWNER/REPO#N[=CHECKOUT]: {spec}")
        key = f"{m['repo']}#{int(m['num'])}".lower()
        if key in seen:
            sys.exit(f"{spec}: that pull request is named twice")
        seen.add(key)
        matches.append(m)
    for i, m in enumerate(matches, 1):
        line, _, _ = anchor(m["repo"], m["num"], m["checkout"])
        if i > 1:
            print()
        print(f"{i}. {line}\n\n{placeholder(i)}")


def paragraph_end(lines, i):
    while i < len(lines) and lines[i].strip():
        i += 1
    return i


def block_end(lines, i):
    """The end of the block that starts at i, which also ends at an item line, since an item never belongs to it."""
    i += 1
    while i < len(lines) and lines[i].strip() and not ITEM.match(lines[i]):
        i += 1
    return i


def resolve(specs, names, what):
    """Map each spec to the pull request it names, keyed by OWNER/REPO#N in lower case."""
    found = {}
    for spec in specs:
        s = NEXT_SPEC.match(spec)
        if not s:
            sys.exit(f"not OWNER/REPO#N={what} or {what}: {spec}")
        if s["repo"] is None:
            if len(specs) != 1 or len(names) != 1:
                sys.exit(f"a bare {what} works only for a brief that lists one pull request")
            key = names[0].lower()
        else:
            key = f"{s['repo']}#{int(s['num'])}".lower()
        if key not in (n.lower() for n in names):
            sys.exit(f"{spec}: the brief lists no such pull request")
        if key in found:
            sys.exit(f"{spec}: that pull request's {what} is named twice")
        found[key] = s["head"]
    return found


def next_brief(previous, out, specs, fix_specs=()):
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
    names = [f"{it['repo']}#{int(it['num'])}" for _, it in items]
    if len(set(n.lower() for n in names)) != len(names):
        sys.exit(f"{previous}: a pull request is listed twice")

    heads = resolve(specs, names, "HEAD")
    fixes = resolve(fix_specs, names, "FIX")
    missing = [n for n in names if n.lower() not in heads]
    if missing:
        sys.exit(f"name the head for every pull request the brief lists. Missing: {', '.join(missing)}")

    for i, it in items:
        if not PRINTED.match(lines[i]):
            sys.exit(f"{previous}: line {i + 1} holds text the script did not print, such as a description written "
                     f"on {it['repo']} PR #{it['num']}'s first line, which a reprint would drop. Move that text to an "
                     f"indented paragraph under the item, then rerun. Writing nothing")

    moves, rewritten = [], []
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
        line, head, base = anchor(it["repo"], it["num"], checkout["checkout"] if checkout else None)
        want = heads[f"{it['repo']}#{int(it['num'])}".lower()]
        if not same(head, want):
            sys.exit(f"{it['repo']} PR #{it['num']} is at {head[:7]} on GitHub, not {want[:7]}. Push the fix "
                     f"first, or name the head GitHub shows. Writing nothing")
        fix = fixes.get(f"{it['repo']}#{int(it['num'])}".lower(), head)
        # "ahead" means the second commit descends from the first, as for the merge base above. Two commits that
        # differ never compare "identical", so each check accepts only "ahead".
        if same(head, fix):
            fix = head
        else:
            answer = status(it["repo"], fix, head)
            if answer != "ahead":
                sys.exit(f"{it['repo']} PR #{it['num']}'s head {head[:7]} is {answer} against the fix {fix[:7]}, so "
                         f"the fix is not in the head's history. Name a fixing commit the head holds. Writing nothing")
        dropped = False
        if not same(old, fix):
            answer = status(it["repo"], old, fix)
            if answer != "ahead":
                # The head drops the last head only where it neither is that head nor descends from it.
                dropped = fix == head or (not same(old, head) and status(it["repo"], old, head) != "ahead")
                if not dropped:
                    sys.exit(f"{it['repo']} PR #{it['num']}'s fix {fix[:7]} is {answer} against round {finished}'s "
                             f"head {old}, which the head still holds, so the fix names a commit from before the "
                             f"round's fixes. Name a fixing commit that comes after {old}. Writing nothing")
                print(f"{it['repo']} PR #{it['num']}: round {finished}'s head {old} is not in the head's history on "
                      f"GitHub, as after a force push such as a rebase, so `git diff {old} {fix[:7]}` holds more than "
                      f"the round's fixes. The blank names the whole change from the merge base {base[:7]} instead, "
                      f"as review-round.md's step 1 says", file=sys.stderr)
        rounds.append((finished, old))
        listed = ", ".join(f"round {r} `{h}`" for r, h in rounds)
        lines[i] = f"{it['n']}. {line} Earlier rounds read {listed}."
        moves.append((it, old, head[:7], fix[:7], checkout["checkout"] if checkout else "<checkout>"))
        if dropped:
            rewritten.append((it, base[:7], head[:7]))

    diffs = "; ".join(f"`git -C {where} diff {old} {fix}` on {it['repo']} PR #{it['num']}"
                      for it, old, _, fix, where in moves)
    blank = (f"<This round reads round {finished}'s fixes: {diffs}, leaving out what a merge of the base "
             "brought, and any passage or function that diff touches or that states the same fact. Name those "
             "here, say so where a fix rewrote the subject and the round reads the whole change, and remove the "
             "angle brackets.>")
    if rewritten:
        # A force push replaced a head the last round read, so the diff from it holds the whole rebase, and the
        # conflict edits a rebase made sit inside its commits, where no diff of the fixes shows them.
        parts = []
        for it, old, new, fix, where in moves:
            whole = next((base for done, base, _ in rewritten if done is it), None)
            if whole:
                parts.append(f"the whole change, `git -C {where} diff {whole} {new}`, on {it['repo']} PR #{it['num']}, "
                             f"because a force push replaced round {finished}'s head {old}")
            else:
                parts.append(f"round {finished}'s fixes, `git -C {where} diff {old} {fix}`, on {it['repo']} "
                             f"PR #{it['num']}, leaving out what a merge of the base brought")
        blank = (f"<This round reads {'; '.join(parts)}, and any passage or function a diff of fixes touches or "
                 "that states the same fact. Name those here, and remove the angle brackets.>")
    start = next((i for i, line in enumerate(lines) if line.startswith(READS)), None)
    if start is not None:
        end = block_end(lines, start)
        # A list right under the paragraph, such as the commits it read, belongs to it, with or without a blank
        # line above it, and so do the indented lines inside that list. Every line replaced from the first one that
        # starts like a list item on is named on standard error, since it may have been meant to stay.
        first = next((k for k in range(start + 1, end) if LIST_IN_PARAGRAPH.match(lines[k])), end)
        named = next((k for k in range(start + 1, end) if LIST_LINE.match(lines[k])), end)
        listed = first < end
        while True:
            after = end
            while after < len(lines) and not lines[after].strip():
                after += 1
            if after < len(lines) and not ITEM.match(lines[after]) and (
                    LIST_LINE.match(lines[after]) or (listed and lines[after][0] in " \t")):
                end, listed = block_end(lines, after), True
            else:
                break
        for line in lines[named:end]:
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
        for _, old, new, _, _ in moves:
            if same(sha, old):
                return f"archive {new}"
        sys.exit(f"{previous}: an archive line names {sha}, which is no pull request's round {finished} head. "
                 f"Fix it by hand first. Writing nothing")

    lines = [ARCHIVE.sub(archived, line) for line in lines]

    # Read after the replacement, because a paragraph above the items moves their line numbers.
    skip = {i for i, line in enumerate(lines) if ITEM.match(line)} | {reads}
    for n, line in enumerate(lines, 1):
        if n - 1 in skip:
            continue
        for it, old, new, _, _ in moves:
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
    usage = ("usage: brief_anchors.py --next PREVIOUS_BRIEF --out NEW_BRIEF [--fix OWNER/REPO#N=FIX ...] "
             "OWNER/REPO#N=HEAD [...], or --next PREVIOUS_BRIEF --out NEW_BRIEF [--fix FIX] HEAD")
    if len(argv) < 5 or argv[2] != "--out":
        sys.exit(usage)
    specs, fixes, rest = [], [], argv[4:]
    while rest:
        if rest[0] == "--fix":
            if len(rest) < 2:
                sys.exit(usage)
            fixes.append(rest[1])
            rest = rest[2:]
        else:
            specs.append(rest.pop(0))
    if not specs:
        sys.exit(usage)
    next_brief(argv[1], argv[3], specs, fixes)


if __name__ == "__main__":
    main(sys.argv[1:])
