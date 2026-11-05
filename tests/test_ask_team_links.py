#!/usr/bin/env python3
"""Hold the links between ask-team's Markdown files that a test can check.

The checks in the role files and the reader lens are text a model reads, so
review alone covers what they mean. These links are different: a heading or a
step that one file names and another renames breaks without any file looking
wrong.
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SKILL = (ROOT / "skills/ask-team/SKILL.md").read_text()
ROUND = (ROOT / "skills/ask-team/review-round.md").read_text()
TEMPLATE = (ROOT / "skills/ask-team/templates/review-comment.md").read_text()

failures = []


def check(name, ok):
    print(("ok " if ok else "FAIL ") + name)
    if not ok:
        failures.append(name)


for label, text in (("SKILL.md", SKILL), ("review-round.md", ROUND), ("review-comment.md", TEMPLATE)):
    check(f"{label} names the owner's heading", "### For the owner" in text)

subject = re.search(r"^2\. \*\*(.+?)\*\*", SKILL.split("### 1. Name the subject")[1], re.M)
check("step 1's second subject is the design subject", bool(subject) and "design" in subject.group(1))
check("the reader lens names subject 2 in step 1", "subject 2 in step 1" in SKILL)

for word in ("recommendation", "metric", "price"):
    step6 = SKILL.split("### 6. Post and price")[1].split("## Lens mode")[0]
    check(f"step 6 asks for the {word}", word in step6)
    check(f"the template asks for the {word}", word in TEMPLATE)

check("the round points at step 6 for the form", "`SKILL.md`'s step 6 gives, with the line" in ROUND)

sys.exit(1 if failures else 0)
