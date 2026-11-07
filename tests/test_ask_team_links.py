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

for label, text in (("review-round.md", ROUND), ("review-comment.md", TEMPLATE)):
    check(f"{label} names the heading for repeat findings", "### Findings in two rounds" in text)

for label, text in (("SKILL.md", SKILL), ("review-round.md", ROUND), ("review-comment.md", TEMPLATE)):
    check(f"{label} asks a fix that adds a record what it weighed", "which existing records it weighed" in text)

check("each fixed line in the template asks what it weighed", TEMPLATE.count("which existing records it weighed") == 3)
for label, text in (("SKILL.md", SKILL), ("review-comment.md", TEMPLATE)):
    check(f"{label} takes the owner's ruling in place of the weighing", "the owner's ruling or request that asks for it" in text)

step4 = ROUND.split("## 4. Verify")[1].split("## 5. ")[0]
step5 = ROUND.split("## 5. Apply")[1].split("## 6. ")[0]
check("step 5 asks before the fix adds a record", "Before a fix adds a new kind of record or stored state" in step5)
check("step 4 sends a fix changed to read a record to a verifier", "changes to read an existing record goes to a verifier" in step4)
check("that paragraph sits above the one it calls next", 0 <= step4.find("Ask step 5's question") < step4.find("A should-fix whose fix would change"))
check("step 5 ties serving to the roles' vetoes", "the vetoes in the role agent files or the charter" in step5)
ask = step5.find("a record the design or the code already holds serves")
check("step 5 asks whether an existing record serves", ask >= 0)
check(
    "that question sits above the paragraphs it calls below",
    0 <= ask < step5.find("A refuted or lowered finding on a sentence") < step5.find("Where a passage this change adds"),
)
skill4 = SKILL.split("### 4. Verify")[1].split("### 5. ")[0]
skill5 = SKILL.split("### 5. Apply what survives")[1].split("### 6. ")[0]
check("SKILL.md's step 4 names that fix", "whose fix changed to read an existing record" in skill4)
check("SKILL.md's step 5 sends a fix that adds a record to the round", "a fix that adds a new kind of record or stored state" in skill5)

step1 = ROUND.split("## 1. Write the brief")[1].split("## 2. ")[0]
step2 = ROUND.split("## 2. Choose the lenses")[1].split("## 3. ")[0]
step6 = ROUND.split("## 6. Price the round")[1].split("## 7. ")[0]
check("a later round reads the fix", "the diff from the last round's anchor to the fixing commit" in step1)
check("a later round seats by the fix", "as applied to the fix rather than to the change" in step2)
check("a fix of tests or a stated limit starts no round", "adds only tests or only states a limit in prose" in step6)
check("the session shows those tests fail", "fails on the mutant that raised it" in step6)
BRIEF = (ROOT / "skills/ask-team/templates/review-brief.md").read_text()
check("the brief defines the kinds", "## What each kind means" in BRIEF)
kinds = BRIEF.split("## What each kind means")[1].split("## Out of scope")[0]
check("each kind the finding format names is defined", all(f"**{word}:**" in kinds for word in ("Veto", "Must fix", "Should fix", "Note")))
check("the kinds lower no veto or limit", "lowers no veto, no hard limit" in kinds)
check("a surviving mutant may be confirmed by running it", "a veto that names a surviving mutant" in skill4)

subject = re.search(r"^2\. \*\*(.+?)\*\*", SKILL.split("### 1. Name the subject")[1], re.M)
check("step 1's second subject is the design subject", bool(subject) and "design" in subject.group(1))
check("the reader lens names subject 2 in step 1", "subject 2 in step 1" in SKILL)

lens = SKILL.split("also gets a reader lens")[1].split("The reader lens's findings go through step 4")[0]
check("the reader lens counts its questions", "It asks six things." in lens)
check("the reader lens lists that many", re.findall(r"^(\d)\. ", lens.split("Questions 3 and 6")[0], re.M) == list("123456"))
check("the questions it names exist", "Questions 3 and 6 read the words the renderer drew" in lens)
script = ROOT / "skills/ask-team/scripts/diagram_words.py"
check("the script the lens runs exists", script.exists())
for command in ("diagram_words.py page", "diagram_words.py compare"):
    check(f"the lens and the script agree on {command}", command in lens and command.split()[-1] in script.read_text())
check("the lens names the words Mermaid draws in a label's place", "Unsupported markdown: list" in lens and "Unsupported markdown" in script.read_text())
default = re.search(r'^MERMAID = "(.+)"$', script.read_text(), re.M)
clear = (ROOT / "skills/clear-wall-of-text/SKILL.md").read_text()
check("clear-wall-of-text names the page's version", bool(default) and f"Mermaid {default.group(1)}, the version GitHub's viewer held" in clear)
check("clear-wall-of-text sends the page to a new folder", "<new folder>/out.html" in clear)
check("the version the lens calls the page's default is the script's", bool(default) and f"{default.group(1)} that GitHub's viewer held on 2026-11-06, which is the version the page draws with" in lens)

for word in ("recommendation", "metric", "price"):
    step6 = SKILL.split("### 6. Post and price")[1].split("## Lens mode")[0]
    check(f"step 6 asks for the {word}", word in step6)
    check(f"the template asks for the {word}", word in TEMPLATE)

check("the round points at step 6 for the form", "`SKILL.md`'s step 6 gives, with the line" in ROUND)

sys.exit(1 if failures else 0)
