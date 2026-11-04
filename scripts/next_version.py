#!/usr/bin/env python3
"""Say which plugin version an open pull request should claim.

Usage:
    next_version.py [--repo OWNER/REPO] [--pr N]

Every pull request that bumps the plugin picks a patch version above main's and
above every other open pull request's, so a merge can leave a claim at or below
main, or two claims on one number. This reads main's version and each open pull
request's, prints them, and prints the next free version. With --pr it says
whether that pull request keeps its claim or moves. It changes nothing, and it
stops rather than print a list with a pull request missing, because a short
list is how two pull requests end up on one number.
"""

import argparse
import base64
import json
import re
import subprocess
import sys

MANIFEST = ".claude-plugin/plugin.json"
TITLE_VERSION = re.compile(r"\(v(\d+\.\d+\.\d+)\)\s*$")


def gh(*args):
    done = subprocess.run(("gh", *args), capture_output=True, text=True)
    if done.returncode:
        sys.exit(f"gh {' '.join(args)} failed: {done.stderr.strip()}")
    return done.stdout


def version_at(repo, ref):
    raw = gh("api", f"repos/{repo}/contents/{MANIFEST}?ref={ref}", "--jq", ".content")
    return json.loads(base64.b64decode(raw))["version"]


def parts(version):
    return tuple(int(n) for n in version.split("."))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", default="l3a0/claude-plugins")
    parser.add_argument("--pr", type=int)
    args = parser.parse_args()

    main_version = version_at(args.repo, "main")
    pulls = json.loads(gh("pr", "list", "-R", args.repo, "--state", "open", "--limit", "1000",
                          "--json", "number,title,headRefOid"))
    claims = {}
    for pull in sorted(pulls, key=lambda p: p["number"]):
        version = version_at(args.repo, pull["headRefOid"])
        if parts(version) > parts(main_version):
            claims[pull["number"]] = version
            print(f"PR {pull['number']} claims {version}")
            named = TITLE_VERSION.search(pull["title"])
            if named and named[1] != version:
                print(f"PR {pull['number']}'s title says {named[1]}, not {version}")
    print(f"main is at {main_version}")

    top = max([main_version, *claims.values()], key=parts)
    major, minor, patch = parts(top)
    free = f"{major}.{minor}.{patch + 1}"
    print(f"next free version is {free}")

    if args.pr is not None:
        if args.pr not in {p["number"] for p in pulls}:
            sys.exit(f"PR {args.pr} is not open")
        mine = claims.get(args.pr)
        shared = [n for n, v in claims.items() if v == mine and n != args.pr]
        if mine is None:
            print(f"PR {args.pr} claims nothing above main, so it takes {free}, in {MANIFEST} and in its title")
        elif shared:
            print(f"PR {args.pr} shares {mine} with PR {shared[0]}, so the later one to arrive takes {free}, "
                  f"in {MANIFEST} and in its title")
        else:
            print(f"PR {args.pr} keeps {mine}")


if __name__ == "__main__":
    main()
