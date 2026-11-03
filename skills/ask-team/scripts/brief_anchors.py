#!/usr/bin/env python3
"""Print the "Subject and anchors" list of a review brief.

Usage:
    brief_anchors.py OWNER/REPO#N[=CHECKOUT] [OWNER/REPO#N[=CHECKOUT] ...]

One numbered item per pull request, with its head commit, the merge base it
is diffed against, its branch, its checkout and its diff command. The merge
base comes from GitHub's compare API rather than the base branch's tip, so a
base that moved after the branch was cut adds nothing to the diff. A checkout
whose HEAD is not the pull request's head is flagged, because a lens reading
it would review other code than the anchor.

Each item ends with a placeholder for what the pull request changes, which
the session writes by hand.
"""

import json
import re
import subprocess
import sys

SPEC = re.compile(r"^(?P<repo>[\w.-]+/[\w.-]+)#(?P<num>\d+)(?:=(?P<checkout>.+))?$")
PLAIN_REF = re.compile(r"^[\w./-]+$")


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


def anchor(spec):
    m = SPEC.match(spec)
    if not m:
        sys.exit(f"not OWNER/REPO#N[=CHECKOUT]: {spec}")
    repo, num, checkout = m["repo"], m["num"], m["checkout"]
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
    line += f" <What it changes.> Diff: `git diff {base[:7]} {head[:7]}`."
    return line


def main(argv):
    if not argv:
        sys.exit(__doc__)
    for i, spec in enumerate(argv, 1):
        print(f"{i}. {anchor(spec)}")


if __name__ == "__main__":
    main(sys.argv[1:])
