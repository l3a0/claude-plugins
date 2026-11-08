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
check("only tests or statements end the rounds", "every veto and must-fix it confirmed claims only a missing test or only a false or missing statement" in step6)
check("every fix must be of that kind", "every fix for them only adds that test or corrects that statement" in step6)
check("the session shows those tests fail", "failing on the mutant that raised it" in step6)
exception = step6.split("The exception never covers")[1].split("The first round that confirms neither")[0]
for clause in ("a wrong result or a weakened guarantee", "any other veto", "any rule the subject writes"):
    check(f"the exception leaves out {clause}", clause in exception)
check("the exception turns on the vetoes and must-fixes confirmed", "every veto and must-fix it confirmed" in step6)
check("the exception needs a subject with no irreversible path", "applies only where the brief says the subject has no path to an irreversible action" in step6)
check("the risk engineer confirms the brief's line", "the risk engineer confirms that line in round 1" in step1)
check("the risk engineer sits unless the line says none", "in every later round unless that line says none" in step2)
check("the risk engineer sits in round 1", "sits in round 1 to confirm the brief's line" in step2)
check("a later round rereads a rewrite", "rewrites the subject rather than patching it, the round reads the whole change again" in step1)
check("a later round reads an irreversible path whole", "reads it from its entry to the action in every round" in step1)
check("a required seat still sits", "Any other required seat sits when the fix touches its path" in step2)
check("a later round keeps the reader lens", "on a design the reader lens" in step2)
step3 = ROUND.split("## 3. Run the blind round")[1].split("## 4. ")[0]
check("the limits do not bind an irreversible path", "Neither limit binds the path to an irreversible action" in step3)
check("a session reads the state before pushing", "--json state` before pushing" in step5)
check("a session names the cause", "name the cause, and fix that" in step5)
check("the paragraph step 5 points at sits above it", 0 <= step5.find("Where a passage this change adds") < step5.find("the first sentence of the paragraph above"))
between = step5.split("Where a passage this change adds")[1].split("the first sentence of the paragraph above")[0]
check("nothing sits between them", between.count("\n\n") == 1)
BRIEF = (ROOT / "skills/ask-team/templates/review-brief.md").read_text()
check("the brief defines the kinds", "## What each kind means" in BRIEF)
kinds = BRIEF.split("## What each kind means")[1].split("## Out of scope")[0]
format_line = re.search(r"\*\*Kind:\*\* (.+)", SKILL).group(1)
named = [word.strip().rstrip(".") for word in re.split(r",| or ", format_line) if word.strip()]
check("each kind the finding format names is defined", bool(named) and all(f"**{word.capitalize()}:**" in kinds for word in named))
check("the kinds lower no veto or limit", "lowers no veto, no hard limit" in kinds)
check("a rare fault on something protected stays a must fix", "however rare" in kinds and "reaches nothing a role protects" in kinds)
outside = BRIEF.split("\n## Out of scope")[1]
check("a limit on what a role protects stays in review", "A limit on anything a role protects stays in review" in outside)
step3skill = SKILL.split("### 3. Blind round")[1].split("### 4. ")[0]
check("every prompt gets the kinds", "`## What each kind means`" in step3skill)
slot = BRIEF.split("From round 2 on, what this round reads")[1].split("Delete this line in round 1")[0]
for phrase in ("states the same fact", "from its entry to the action", "whole change"):
    check(f"the brief's later round line says {phrase}", phrase in slot)
check("the brief names the path's files, tests and calls", "with their tests and helpers, and the calls that perform the action" in BRIEF)
check("a verifier gets the kinds", "A verifier's prompt carries" in skill4)
check("step 5 keeps a limit on what a role protects in review", "A limit on anything a role protects stays in review" in step5)
check("a surviving mutant may be confirmed by running it", "a veto that names a surviving mutant" in skill4)
check("a mutant that dies goes to a verifier", "A run where the mutant dies goes to a verifier" in skill4)
check("the comment names roles that sat out and fixes that start no round", "Roles that sat out" in TEMPLATE and "starts no round for" in TEMPLATE)

subject = re.search(r"^2\. \*\*(.+?)\*\*", SKILL.split("### 1. Name the subject")[1], re.M)
check("step 1's second subject is the design subject", bool(subject) and "design" in subject.group(1))
check("the reader lens names subject 2 in step 1", "subject 2 in step 1" in SKILL)

lens = SKILL.split("also gets a reader lens")[1].split("The reader lens's findings go through step 4")[0]
check("the reader lens counts its questions", "It asks six things." in lens)
check("the reader lens lists that many", re.findall(r"^(\d)\. ", lens.split("Questions 3 and 6")[0], re.M) == list("123456"))
check("the questions it names exist", "Questions 3 and 6 read the words the renderer drew" in lens)
check("a label that only names something needs no verb", "only names a component or a participant needs no verb" in lens)
script = ROOT / "skills/ask-team/scripts/diagram_words.py"
check("the script the lens runs exists", script.exists())
for command in ("diagram_words.py page", "diagram_words.py compare"):
    check(f"the lens and the script agree on {command}", command in lens and command.split()[-1] in script.read_text())
check("the lens names the words Mermaid draws in a label's place", "Unsupported markdown: list" in lens and "Unsupported markdown" in script.read_text())
default = re.search(r'^MERMAID = "(.+)"$', script.read_text(), re.M)
clear = (ROOT / "skills/clear-wall-of-text/SKILL.md").read_text()
check("clear-wall-of-text names the page's version", bool(default) and f"Mermaid {default.group(1)}, the version GitHub's viewer held" in clear)
check("clear-wall-of-text sends the page to a new folder", "<new folder>/out.html" in clear)
check("clear-wall-of-text and the lens count the same faults", "Three faults pass a render check" in clear and "Three faults pass a render check" in lens)
check("the version the lens calls the page's default is the script's", bool(default) and f"{default.group(1)} that GitHub's viewer held on 2026-11-06, which is the version the page draws with" in lens)

step3 = clear.split("### 3. Give each kind of content its form")[1].split("### 4.")[0]
step6c = clear.split("### 6. Render it and look")[1].split("### 7.")[0]
check("the lens points at clear-wall-of-text's step 3 for the form of a figure", "Step 3 of `clear-wall-of-text` says which form suits what" in lens and "Pick the figure a reader understands fastest" in step3)
check("the lens points at clear-wall-of-text's step 6 for checking a sketch", "as step 6 of `clear-wall-of-text` says" in lens and "A sketch has no parser" in step6c)
check("the lens reads a sketch's labels by the rules for a diagram's words", "A sketch's labels meet the same rules" in lens and "The words in a diagram follow the same rules as the prose" in step3)
check("clear-wall-of-text no longer sends every sketch note to Mermaid", "gets a Mermaid diagram, because" not in clear)

for word in ("recommendation", "metric", "price"):
    step6 = SKILL.split("### 6. Post and price")[1].split("## Lens mode")[0]
    check(f"step 6 asks for the {word}", word in step6)
    check(f"the template asks for the {word}", word in TEMPLATE)

check("the round points at step 6 for the form", "`SKILL.md`'s step 6 gives, with the line" in ROUND)

sys.exit(1 if failures else 0)
