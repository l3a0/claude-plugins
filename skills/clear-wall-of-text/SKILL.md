---
name: clear-wall-of-text
description: Turn a dense passage in a design doc, architecture doc, charter or README into text a reader follows on one read, with every fact kept. Gives each question a subheading, breaks steps into a numbered list, puts conditions into a titled table, draws a mechanism as a diagram, and states each cited rule in plain words. Use when asked to make a wall of text easier to understand, to break up a dense paragraph, or to add diagrams or sketch notes to a passage. Not for a blog post's own review, which `review-post` runs in the repository that holds the post.
---

# Clear a wall of text

A dense paragraph hides what a reader came for. A reader of a design doc arrives with one question, and a paragraph that answers five makes them read all five to find it. Rewriting one also risks losing a condition, and a lost condition in a design doc becomes a bug in the build. So this skill changes the shape of a passage and proves it changed nothing else.

On 2026-11-06 two passages of l3a0/ithildin-runtime's architecture doc went through these steps. The [loss stop section](https://github.com/l3a0/ithildin-runtime/pull/15) became five questions, a list, a diagram and a table. Rendering it caught every label parsing as a Markdown list, and a review found a table cell, "Held", that a reader could not tell from "Refused".

## The steps

1. Read the passage and what it leans on.
2. Write down the reader's questions.
3. Give each kind of content its form.
4. State each rule it cites.
5. Prove every fact survived.
6. Render it and look.
7. Have a lens check the meaning.

### 1. Read the passage and what it leans on

Open each rule, section and issue the passage cites, because a rewrite can only state what its author understands. Note which sentences carry a "this doc proposes" label, and which are decided. Read the repository's own writing rules, usually `## Writing style` in its `CLAUDE.md`, and its pinned vocabulary if it has one.

### 2. Write down the reader's questions

List what a reader with none of the context would ask, in the order they would ask it. Each question becomes a subheading, phrased so the question can be found in a contents list, such as "Who compares the book with the broker".

Open with why the passage matters, in one or two sentences, and put the claim before the mechanics. Keep sibling headings distinct, and leave existing headings alone so their anchors still resolve.

### 3. Give each kind of content its form

Pick the form by what the content is, and use the least that serves.

**Table:** The form each kind of content takes

| The content is | Its form |
| --- | --- |
| Steps in order | A numbered list, each item one step |
| A counted set, such as "two workers" | A numbered list after the sentence that counts it |
| A choice that depends on a condition, or several cases with the same outcomes | A table with a title line, one row per case |
| A mechanism with several actors or steps | A Mermaid sequence diagram or flowchart |
| A data type | A UML class diagram |
| One claim with its reason | A short paragraph, unchanged in form |

A diagram sits beside the list it draws and keeps that list's order. Show what the diagram leaves out in the text, such as a resize or a retry. Do not draw what a table already says, because two surfaces drift.

A blog post may carry sketch notes, the whiteboard GIFs its repository's `sketch-notes` skill draws. A design doc takes Mermaid, because a Mermaid block lives in the document and moves with its text.

The words in a diagram follow the same rules as the prose. A label says what happens, in a phrase with a verb and a clear actor. Spell out shorthand, hold one idea in a label, and wrap a long one.

### 4. State each rule it cites

Replace a number chain, such as "case 3 of rule 5 of `### A section`", with what the rule requires, then link the section by name. A link alone is fine where the sentence already says what happens. Two checks keep a gloss true.

1. Read the rule before writing the gloss. A number in one section can mean a rule in another.
2. Add no condition and drop none that matters at that spot. A proposal stays labelled.

### 5. Prove every fact survived

Move sentences only. No number, name, condition or label changes, apart from a gloss.

1. Keep the old text open and walk it clause by clause, ticking each against the new text. A clause with nowhere to go is a finding about the plan, not a clause to drop.
2. Run `python3 <this plugin>/skills/ask-team/scripts/removed_text.py CHECKOUT=FROM..TO` to list what the change removed, and read each run.
3. Check each table cell against the rule behind it. A cell shortens a sentence, so it is where a condition goes missing. Write "can go out" where the rule says can, never "goes out".
4. Sweep the repository's other surfaces for a statement of the same fact. Where a repository's rules say a change reaches its diagrams and tables in the same commit, follow them.

### 6. Render it and look

A diagram that renders can still be wrong, so read the picture. Two faults pass a render check, and `ask-team`'s `scripts/diagram_words.py` looks for both where the plugin carries it.

1. A label that starts with a number and a dot, such as "1. Refit", parses as a Markdown list, and the box reads "Unsupported markdown: list". Write "Step 1:" instead.
2. Two statements joined on one line still parse, because a sequence message runs to the end of its line. The arrow disappears into a label. Check the file after any scripted edit, and never let a pattern's leading spaces match a newline.

Render with Mermaid in a browser, take a screenshot, and read every box. Run the repository's lint and tests too.

### 7. Have a lens check the meaning

Send the diff to one blind lens with this question: does the new text keep every fact, and would a reader with none of the context follow it on one read? A review of the ithildin-runtime passages found that table cell, and an "its" that pointed at the wrong noun. Apply what survives, and say in the report that no lens read a commit if none did.
