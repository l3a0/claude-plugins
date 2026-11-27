#!/usr/bin/env python3
"""Post a review round's comments and its cost on the issue, check a comment posted by hand, and edit a pull request's Revision section.

Usage:
    review_post.py revision OWNER/REPO#N --scratch DIR --file PATH [--replace ITEM] [--dry-run]
    review_post.py comment --round R OWNER/REPO#N=HEAD=ANCHOR=FILE [...] [--dry-run]
    review_post.py check OWNER/REPO#N=HEAD=ANCHOR=FILE | OWNER/REPO@BRANCH=ANCHOR=FILE [...]
    review_post.py cost --round R OWNER/REPO#ISSUE --pull OWNER/REPO#N --anchor ANCHOR --file PATH [--dry-run]

`revision` adds the one line in PATH to the body's `## Revision` section as a
numbered item, or replaces item ITEM, and adds the section before the closing lines and footer
of a body that has none. The section runs from its heading to its last
numbered item. Each run saves the body as read to a file of its own. It sends
only when every changed line sits inside the section and a second run would
change nothing, and it reads the body back. A line already in the section is
not added twice, so a retry changes nothing. It sends nothing on a body with
two Revision headings, a heading written any other way, or two items with one
number, and says to edit by hand. It refuses a line that starts with a list
number or bullet of its own, such as `1. `, because the script numbers the
item itself and would write `2. 1. `. It refuses rather than strips the mark,
so the line in PATH is the line the section holds, and a retry finds it.

`comment` takes each comment's heading from its file's first line. It refuses a
file that does not start with a heading and name the round, its anchor and the
head, because a retry could not recognise that post, and a pull request named
twice. It then checks every pull request's head, that each anchor is the head
or an ancestor of it on GitHub, and every earlier comment by the same login,
since anyone can comment on a public pull request. It posts on none of them if
a head differs, an anchor is not shown to be the head or an ancestor of it, or
an earlier comment has the same key with other text. The anchor check catches
an anchor copied from another branch or another pull request, and one a force
push dropped, and it cannot tell the two apart, so nothing should post around
it by hand. l3a0/claude-plugins#108 decides what a review does after a force
push drops an anchor. The anchor check does not catch an earlier round's
anchor, which is still an ancestor. It skips a pull request that already
carries this comment, so a retry posts only what is missing. GitHub takes no
key on a comment, so this narrows the window for a double post rather than
closing it. So it counts the copies after posting, and exits non-zero naming
any pull request that does not hold exactly one. Where every copy holds the
same text, it names the one to keep, the lowest comment number, so two
sessions that follow it keep the same one. Where a copy holds other text,
which may be another session's post, it says to delete and edit nothing.
Where the read after posting shows none, it names the link the post returned
and says to rerun nothing.
`cost` does the same. A closing comment posts the
same way, with R the round it closes and ANCHOR the commit that round read. It
refuses a first line that reads `Review complete` and is not exactly
`## Review complete`, such as one with a space before or after it or another
heading level, because a build board counts only that whole line. Where a
comment that opens with `## Review complete` already names the same round,
anchor and head, that comment closes the review, so it posts nothing and says
so. One naming an older head does not count, because a build board counts it
only when posted after the head commit, so a closing comment at the new head
posts.

`check` runs the head and anchor checks of `comment` and posts nothing, for a
comment that names an anchor and goes by hand, such as one on an issue. For
OWNER/REPO#N=HEAD=ANCHOR=FILE it checks that the pull request's head is HEAD,
that ANCHOR is that head or an ancestor of it, and that FILE names both. For
OWNER/REPO@BRANCH=ANCHOR=FILE it reads the branch's tip from GitHub, and checks
that ANCHOR is that tip or an ancestor of it and that FILE names ANCHOR, which
suits a plan read against `main`. It encodes the branch's name in the request
and refuses an answer for any other branch, so a name holding `#` reads that
branch. It stops at the first target it cannot parse or whose file is
missing. Otherwise it exits non-zero naming each file that does not name its
anchor or head, each head and each branch that fails, and when those all
pass, each anchor that fails. It reads no comments, because
each route keys its retry by its own lines. It cannot show that the file it
read is the file then posted, and like `comment` it reads the file for the
anchor and head by substring.

`cost` posts a round's `## Cost` comment on the issue the main pull request
tracks. It refuses a file whose first line is not exactly `## Cost`, which is
the only form the `## Cost total` sweep reads, or whose next non-blank line is
not `Review round R, of ANCHOR, on <the pull request's URL>`, because that line
is how a retry recognises the post. It takes the issue on trust, since a pull
request that is only part of an issue names it only in its body's text, which
the script does not parse. It skips the
post when the issue already carries a comment by the same login with that
heading and line, stops when one carries them with other text, and counts the
copies after posting, as `comment` does. It also stops when the issue carries
a `## Cost` comment by the same login for this round and pull request under
another anchor, because a `## Cost total` would count the round twice. It
runs no check that the anchor is in the pull request's history, because only
`cost` reads that anchor, to recognise a retry. In the usual order the round's
comment posts first, through `comment`, which checks it. Where the round's
comment did not post, such as after a force push dropped the anchor, whether
its figures post and which `## Cost` comment carries them waits on
l3a0/claude-plugins#108.

A write that fails says the outcome is unknown, since the request may have
landed. Rerun the same command, which looks before it writes. A read can lag
behind a write. While it lags, a rerun posts a second copy wherever the read
still hides the first, and the count after posting counts one, so nothing
reports it. A rerun can follow a write that failed or had an unknown outcome,
or a read that failed after a post landed, whose message gives no advice. In a
run over several pull requests, a failed write ends the run with only that
write's message, and drops what the run found on the pull requests before it,
such as one whose read after posting showed none. l3a0/claude-plugins#117
owns reruns that a lagging read cannot double. The tests run
against a stand-in `gh`, so no test covers what the real one prints.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.parse

SPEC = re.compile(r"^(?P<repo>[\w.-]+/[\w.-]+)#(?P<num>\d+)$")
TARGET = re.compile(r"^(?P<repo>[\w.-]+/[\w.-]+)#(?P<num>\d+)=(?P<head>[0-9a-f]{7,40})=(?P<anchor>[0-9a-f]{7,40})=(?P<file>.+)$")
HEADING = re.compile(r"^ {0,3}#{1,6}(\s|$)")
REVISION = re.compile(r"^ {0,3}#{1,6}\s+Revision\s*$")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
ITEM = re.compile(r"^(\d+)\. (.*)$")
LIST_MARK = re.compile(r"^\s*(\d+[.)]|[-*+])(\s|$)")
FINAL = "## Review complete"
NEAR_FINAL = re.compile(r"^#{1,6}\s*Review[\W_]*complete\b", re.IGNORECASE)
CHECK_BRANCH = re.compile(r"^(?P<repo>[\w.-]+/[\w.-]+)@(?P<branch>[^\s=]+)=(?P<anchor>[0-9a-f]{7,40})=(?P<file>.+)$")
COST_HEADING = "## Cost"
COST_LINE = re.compile(r"^Review round (?P<round>\d+), of `?(?P<anchor>[0-9a-f]{7,40})`?, on (?P<link>.+?)\s*$")
PULL_LINK = re.compile(r"^(?:\[[^\]\n]*\]\()?https://github\.com/(?P<repo>[\w.-]+/[\w.-]+)/pull/(?P<num>\d+)(?!\d)", re.IGNORECASE)
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


def view(repo, num, field, kind="pr"):
    # --jq would print one newline more than the string holds, so parse the JSON.
    return json.loads(run("gh", kind, "view", num, "-R", repo, "--json", field))[field]


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
    found = find_section(lines)
    if found is None:
        if replace is not None:
            sys.exit(f"the body has no {SECTION} section, so item {replace} does not exist")
        at = insertion_point(lines)
        added = ["", SECTION, "", f"1. {text}"]
        if at == len(lines) or lines[at].strip():
            added.append("")
        return "\n".join(lines[:at] + added + lines[at:])
    start, end = found
    current = items(lines, start, end)
    if replace is not None:
        if replace not in current:
            sys.exit(f"the {SECTION} section has no item {replace}")
        i = current[replace][0]
        stop = i + 1
        while stop < end and not ITEM.match(lines[stop].rstrip("\r")):
            stop += 1
        if [line.rstrip("\r") for line in lines[i:stop]] == [f"{replace}. {text}"]:
            return None
        return "\n".join(lines[:i] + [f"{replace}. {text}"] + lines[stop:])
    if any(existing == text for _, existing in current.values()):
        return None
    added = [f"{max(current, default=0) + 1}. {text}"]
    if not current:
        added.insert(0, "")
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
    with open(args.file, encoding="utf-8") as f:
        text = f.read().strip()
    if not text or "\n" in text or "\r" in text:
        sys.exit("a revision entry is one non-empty line")
    mark = LIST_MARK.match(text)
    if mark:
        sys.exit(f"the line starts with its own list marker {mark[1]!r}, and the script numbers the item itself, "
                 f"and the item would start '<n>. {mark[1]}'. Remove the marker from {args.file} and rerun")
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
    try:
        back = view(repo, num, "body")
    except SystemExit as failed:
        sys.exit(f"{failed} The edit may have landed, so the outcome is unknown. Rerun this command, which "
                 f"looks before it writes. As read: {saved}. As sent: {sent}")
    if back != new:
        sys.exit(f"{repo}#{num}: the body read back differs from what was sent, so nothing was resent. "
                 f"As read before the edit: {saved}. As sent: {sent}")
    print(f"{repo}#{num}: {SECTION} updated and read back")


def first_line(text):
    return text.split("\n", 1)[0].strip()


def raw_first_line(text):
    # The file is read in text mode, so no carriage return reaches here.
    return text.split("\n", 1)[0]


def same_text(a, b):
    return a.replace("\r\n", "\n").strip() == b.replace("\r\n", "\n").strip()


def carries(comment, heading, round_no, anchor):
    return first_line(comment) == heading and anchor[:7] in comment \
        and re.search(rf"\bround {round_no}\b", comment, re.IGNORECASE) is not None


def copies(m, heading, round_no, login):
    # A closing comment counts only after the head it names, so one naming an older head is
    # not this post, and a later closing comment names the head it is posted at.
    return [c for c in view(m["repo"], m["num"], "comments")
            if (c.get("author") or {}).get("login") == login and carries(c["body"], heading, round_no, m["anchor"])
            and (heading != FINAL or m["head"][:7] in c["body"])]


def comment_number(c):
    found = re.search(r"issuecomment-(\d+)$", c.get("url") or "")
    return int(found[1]) if found else None


def settle(name, found, text, link=None):
    """Say what to do about a post that is not held exactly once, so two sessions that follow it keep one copy."""
    if not found:
        return (f"{name} should hold this comment once, and the read after posting {link} shows none, which GitHub's "
                "read can do for a while. Rerun nothing and post nothing by hand. Read the comments again later, and "
                "report it if it is still missing")
    links = ", ".join(c.get("url") or "(no link)" for c in found)
    if any(not same_text(c["body"], text) for c in found):
        return (f"{name} should hold this comment once and also holds its key with other text, which may be another "
                f"session's post: {links}. Delete and edit nothing, and report these links")
    if any(comment_number(c) is None for c in found):
        return (f"{name} should hold this comment once and holds it {len(found)} times, and GitHub gave no comment "
                f"number to order them by: {links}. Delete nothing, and report it")
    first, *rest = sorted(found, key=comment_number)
    return (f"{name} should hold this comment once and holds it {len(found)} times. Keep {first['url']}, the one with "
            f"the lowest comment number, delete {', '.join(c['url'] for c in rest)}, read the comments again to "
            "confirm one is left, and report it")


def outside_history(repo, anchor, head):
    """Return why the anchor is not the head or an ancestor of it, or None when it is."""
    if head.startswith(anchor):
        return None
    # GitHub's compare API says "ahead" when the second commit descends from the first, and answers 404 for a
    # commit the repository does not hold.
    done = subprocess.run(("gh", "api", f"repos/{repo}/compare/{anchor}...{head}", "--jq", ".status"),
                          capture_output=True, text=True)
    if done.returncode:
        return f"GitHub could not compare {anchor[:7]} with the head {head[:7]}: {done.stderr.strip()}"
    status = done.stdout.strip()
    # Two commits that differ never compare "identical", so only "ahead" passes.
    if status == "ahead":
        return None
    if status == "identical":
        return (f"GitHub answered identical for the anchor {anchor[:7]} and the head {head[:7]}, which it gives only for "
                f"one commit, though the head does not start with the anchor")
    if status not in ("behind", "diverged"):
        return (f"GitHub compared {anchor[:7]} with the head {head[:7]} and answered {status!r}, which is none of "
                f"ahead, behind, diverged, identical")
    return f"the head {head[:7]} is {status} against the anchor {anchor[:7]}, so the anchor is not in its history"


def head_check(repo, num, named):
    """Return the pull request's head on GitHub, and why it is not the head named, or None when it is."""
    head = view(repo, num, "headRefOid")
    if head.startswith(named):
        return head, None
    # Two heads that share their first seven characters are named in full, so the message tells them apart.
    width = 7 if head[:7] != named[:7] else len(head)
    return head, f"{repo}#{num} is at {head[:width]}, not {named[:width]}"


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
        heading = first_line(text)
        if NEAR_FINAL.match(heading) and raw_first_line(text) != FINAL:
            sys.exit(f"posting nothing, because {m['file']} starts {raw_first_line(text)!r}, and a build board counts a "
                     f"closing comment only when its whole first line is {FINAL!r}")
        if not HEADING.match(heading) or not carries(text, heading, args.round, m["anchor"]):
            sys.exit(f"posting nothing, because {m['file']} does not start with a heading and name "
                     f"round {args.round} and {m['anchor'][:7]}, so a retry could not recognise it")
        if m["head"][:7] not in text:
            sys.exit(f"posting nothing, because {m['file']} does not name the head {m['head'][:7]}")
        pull = (m["repo"].lower(), int(m["num"]))
        if pull in seen:
            sys.exit(f"posting nothing, because {m['repo']}#{m['num']} is named twice")
        seen.add(pull)
        targets.append((m, text, heading))
    read = [head_check(m["repo"], m["num"], m["head"]) for m, _, _ in targets]
    heads, wrong = [head for head, _ in read], [why for _, why in read if why]
    if wrong:
        sys.exit("posting nothing, because a head does not match: " + "; ".join(wrong))
    outside = [f"{m['repo']}#{m['num']}: {why}" for (m, _, _), head in zip(targets, heads)
               if (why := outside_history(m["repo"], m["anchor"], head))]
    if outside:
        sys.exit("posting nothing, because an anchor was not shown to be the head or an ancestor of it: " + "; ".join(outside)
                 + ". Check that each anchor is the commit this round's brief anchors at, and post nothing by hand")
    login = run("gh", "api", "user", "--jq", ".login").strip()
    pending, doubled = [], []
    for m, text, heading in targets:
        name = f"{m['repo']}#{m['num']}"
        mine = copies(m, heading, args.round, login)
        if heading == FINAL and any(not same_text(c["body"], text) for c in mine):
            sys.exit(f"posting nothing, because {name} already carries a {FINAL!r} comment on round "
                     f"{args.round} and {m['anchor'][:7]} at the head {m['head'][:7]}, which closes the "
                     "review, whether it is that round's own comment or an earlier closing comment. "
                     "Report it, and post no second one")
        if any(not same_text(c["body"], text) for c in mine):
            sys.exit(f"posting nothing, because {name} already carries this heading, round and anchor with "
                     "different text. Report it, and once it is settled post by hand after the checks review-round.md's step 7 "
                     "gives for a hand post")
        if len(mine) > 1:
            doubled.append(settle(name, mine, text))
        elif mine:
            print(f"{name}: already carries this comment, so skipped")
        else:
            pending.append((name, m, text, heading))
    for name, m, text, heading in pending:
        if args.dry_run:
            print(f"{name}: would post {m['file']}")
            continue
        link = write("gh", "pr", "comment", m["num"], "-R", m["repo"], "--body-file", m["file"])
        print(f"{name}: posted {link}")
        found = copies(m, heading, args.round, login)
        if len(found) != 1:
            doubled.append(settle(name, found, text, link))
    if doubled:
        sys.exit("; ".join(doubled))


def branch_tip(repo, branch):
    """Return the branch's tip on GitHub, and why it could not be read, or None when it could."""
    # A raw "#" or "?" would end the path, and GitHub resolves "..", so the name is encoded and the name
    # GitHub answers for must be the one asked for.
    done = subprocess.run(("gh", "api", f"repos/{repo}/branches/{urllib.parse.quote(branch, safe='/')}",
                           "--jq", ".name, .commit.sha"), capture_output=True, text=True)
    lines = done.stdout.strip().split("\n")
    if done.returncode or len(lines) != 2 or not re.fullmatch(r"[0-9a-f]{40}", lines[1]):
        return None, f"GitHub did not give the tip of {branch} in {repo}: {done.stderr.strip() or done.stdout.strip()!r}"
    if lines[0] != branch:
        return None, f"GitHub answered for the branch {lines[0]!r}, not {branch!r}"
    return lines[1], None


def check(args):
    parsed, tips, wrong = [], [], []
    for spec in args.targets:
        m = TARGET.match(spec) or CHECK_BRANCH.match(spec)
        if not m:
            sys.exit(f"not OWNER/REPO#N=HEAD=ANCHOR=FILE or OWNER/REPO@BRANCH=ANCHOR=FILE: {spec}")
        if not os.path.isfile(m["file"]):
            sys.exit(f"no comment file at {m['file']}")
        parsed.append(m)
    for m in parsed:
        pull = "num" in m.groupdict()
        name = f"{m['repo']}#{m['num']}" if pull else f"{m['repo']}@{m['branch']}"
        with open(m["file"], encoding="utf-8") as f:
            text = f.read()
        missing = [f"the anchor {m['anchor'][:7]}"] if m["anchor"][:7] not in text else []
        if pull and m["head"][:7] not in text:
            missing.append(f"the head {m['head'][:7]}")
        if missing:
            wrong.append(f"{m['file']} does not name {' and '.join(missing)}")
        tip, why = head_check(m["repo"], m["num"], m["head"]) if pull else branch_tip(m["repo"], m["branch"])
        tips.append((name, tip))
        if why:
            wrong.append(why if pull else f"{name}: {why}")
    if wrong:
        sys.exit("post nothing, because a file, a head or a branch does not match: " + "; ".join(wrong))
    outside = [f"{name}: {why}" for m, (name, tip) in zip(parsed, tips)
               if (why := outside_history(m["repo"], m["anchor"], tip))]
    if outside:
        sys.exit("post nothing, because an anchor was not shown to be the head or an ancestor of it: " + "; ".join(outside))
    for m, (name, tip) in zip(parsed, tips):
        where = "is the head" if tip.startswith(m["anchor"]) else "is an ancestor of the head"
        named = "names them" if "num" in m.groupdict() else "names the anchor"
        print(f"{name}: the anchor {m['anchor'][:7]} {where} {tip[:7]}, and {m['file']} {named}, so it may post")


def cost_key(text):
    """Return (round, anchor's first seven, repo, number) from a ## Cost comment, or None."""
    lines = text.replace("\r\n", "\n").split("\n")
    if lines[0] != COST_HEADING:
        return None
    rest = [line for line in lines[1:] if line.strip()]
    m = COST_LINE.match(rest[0]) if rest else None
    link = PULL_LINK.match(m["link"]) if m else None
    if not link:
        return None
    return int(m["round"]), m["anchor"][:7], link["repo"].lower(), int(link["num"])


def cost_copies(repo, num, key, login):
    return [c for c in view(repo, num, "comments", kind="issue")
            if (c.get("author") or {}).get("login") == login and cost_key(c["body"]) == key]


def other_anchors(repo, num, key, login):
    """Return this login's ## Cost comments for the same round and pull request under another anchor."""
    return [c for c in view(repo, num, "comments", kind="issue")
            if (c.get("author") or {}).get("login") == login and (k := cost_key(c["body"]))
            and k[0] == key[0] and k[2:] == key[2:] and k[1] != key[1]]


def cost(args):
    issue, pull = SPEC.match(args.issue), SPEC.match(args.pull)
    if not issue:
        sys.exit(f"not OWNER/REPO#N: {args.issue}")
    if not pull:
        sys.exit(f"not OWNER/REPO#N: {args.pull}")
    if not re.fullmatch(r"[0-9a-f]{7,40}", args.anchor):
        sys.exit(f"not a commit of 7 to 40 hex characters: {args.anchor}")
    if not os.path.isfile(args.file):
        sys.exit(f"no comment file at {args.file}")
    with open(args.file, encoding="utf-8") as f:
        text = f.read()
    key = (args.round, args.anchor[:7], pull["repo"].lower(), int(pull["num"]))
    if cost_key(text) != key:
        sys.exit(f"posting nothing, because {args.file} does not start with the line {COST_HEADING!r} and then "
                 f"'Review round {args.round}, of `{args.anchor[:7]}`, on <the URL of {args.pull}>', "
                 "so a retry could not recognise it")
    repo, num, name = issue["repo"], issue["num"], args.issue
    login = run("gh", "api", "user", "--jq", ".login").strip()
    others = other_anchors(repo, num, key, login)
    if others:
        anchors = ", ".join(sorted({cost_key(c["body"])[1] for c in others}))
        links = ", ".join(c.get("url") or "(no link)" for c in others)
        sys.exit(f"posting nothing, because {name} already carries round {args.round}'s {COST_HEADING} comment for "
                 f"{args.pull} under the anchor {anchors}, not {key[1]}, at {links}, and a {COST_HEADING} total would "
                 "count the round twice. Delete and edit nothing, since either may hold another session's spend, "
                 "and report the links")
    mine = cost_copies(repo, num, key, login)
    if any(not same_text(c["body"], text) for c in mine):
        links = ", ".join(c.get("url") or "(no link)" for c in mine)
        sys.exit(f"posting nothing, because {name} already carries this round's {COST_HEADING} comment with "
                 f"different text at {links}. Where that comment is this file's text plus the build's line this session added at "
                 "the closing comment or the handover, as review-round.md's steps 6 and 7 ask, that is expected, so post nothing "
                 "more. Otherwise edit nothing, since it may hold another session's spend, and report it")
    if len(mine) > 1:
        sys.exit(settle(name, mine, text))
    if mine:
        print(f"{name}: already carries this comment, so skipped")
        return
    if args.dry_run:
        print(f"{name}: would post {args.file}")
        return
    link = write("gh", "issue", "comment", num, "-R", repo, "--body-file", args.file)
    print(f"{name}: posted {link}")
    found = cost_copies(repo, num, key, login)
    if len(found) != 1:
        sys.exit(settle(name, found, text, link))


def round_number(value):
    if not re.fullmatch(r"[0-9]+", value):
        raise argparse.ArgumentTypeError(
            f"{value!r} is not a round's number. Give the number of the round the comment reports, "
            "and for a closing comment the round it closes, as in --round 12")
    return int(value)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)

    edit = commands.add_parser("revision")
    edit.add_argument("pull")
    edit.add_argument("--scratch", required=True)
    edit.add_argument("--file", required=True)
    edit.add_argument("--replace", type=int)
    edit.add_argument("--dry-run", action="store_true")
    edit.set_defaults(handler=revision)

    post = commands.add_parser("comment")
    post.add_argument("targets", nargs="+")
    post.add_argument("--round", type=round_number, required=True)
    post.add_argument("--dry-run", action="store_true")
    post.set_defaults(handler=comment)

    gate = commands.add_parser("check")
    gate.add_argument("targets", nargs="+")
    gate.set_defaults(handler=check)

    price = commands.add_parser("cost")
    price.add_argument("issue")
    price.add_argument("--round", type=round_number, required=True)
    price.add_argument("--pull", required=True)
    price.add_argument("--anchor", required=True)
    price.add_argument("--file", required=True)
    price.add_argument("--dry-run", action="store_true")
    price.set_defaults(handler=cost)

    args = parser.parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
