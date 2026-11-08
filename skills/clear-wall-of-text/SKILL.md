---
name: clear-wall-of-text
description: Turn a dense passage in a design doc, architecture doc, charter or README into text a reader follows on one read, with every fact kept. Gives each question a subheading, breaks steps into a numbered list, puts conditions into a titled table, draws a mechanism as a Mermaid diagram or a sketch, and states each cited rule in plain words. Use when asked to make a wall of text easier to understand, to break up a dense paragraph, or to add diagrams or sketch notes to a passage of one of those documents. Not for a blog post, whose review and sketch notes belong to `review-post` and `sketch-notes` in the repository that holds the post.
---

# Clear a wall of text

A dense paragraph hides what a reader came for. A reader of a design doc arrives with one question, and a paragraph that answers five makes them read all five to find it. Rewriting one also risks losing a condition, and a lost condition in a design doc becomes a bug in the build. So this skill changes the shape of a passage and proves it changed nothing else.

On 2026-11-07 UTC two passages of l3a0/ithildin-runtime's architecture doc were rewritten this way, and these steps come from that work.

1. The [loss stop section](https://github.com/l3a0/ithildin-runtime/commit/e1fc401) became five questions, a list, a diagram and a table. Rendering it caught every label parsing as a Markdown list, and a review found a table cell, "Held", that a reader could not tell from "Refused".
2. The [book-and-broker passage](https://github.com/l3a0/ithildin-runtime/commit/cf3a22e) became subheadings and a table. A review found a row that hid a halt, which step 5's third item now guards against.

## The steps

1. Read the passage and what it leans on.
2. Write down the reader's questions.
3. Give each kind of content its form.
4. State each rule it cites.
5. Prove every fact survived.
6. Render it and look.
7. Have a fresh reader check the meaning.

### 1. Read the passage and what it leans on

Open each rule, section and issue the passage cites, because a rewrite can only state what its author understands. Note which sentences carry a "this doc proposes" label, and which are decided. Read the repository's own writing rules, usually `## Writing style` in its `CLAUDE.md`, and its pinned vocabulary if it has one.

### 2. Write down the reader's questions

List what a reader with none of the context would ask, in the order they would ask it. Each question becomes a subheading, phrased so the question can be found in a contents list, such as "Who compares the book with the broker".

Open with why the passage matters, in one or two sentences, and put the claim before the mechanics. Keep sibling headings distinct, and leave existing headings alone so their anchors still resolve. Add each new heading to the document's Contents where it lists that level.

### 3. Give each kind of content its form

Pick the form by what the content is, and use the least that serves.

**Table:** The form each kind of content takes

| The content is | Its form |
| --- | --- |
| Steps in order | A numbered list, each item one step |
| A counted set, such as "two workers" | A numbered list after the sentence that counts it |
| A choice that depends on a condition, or several cases with the same outcomes | A table with a title line, one row per case |
| A mechanism with several actors or steps, such as a flow, a sequence of calls or a set of states | A Mermaid sequence diagram, flowchart or state diagram |
| What boxes and arrows cannot show, such as a level that fills and drains, a quantity drawn to scale, or a physical picture like a bucket of tokens | A sketch, an animated whiteboard GIF |
| A data type | A UML class diagram |
| One claim with its reason | A short paragraph, unchanged in form |

Pick the figure a reader understands fastest, not Mermaid by default. Mermaid suits a flow, a sequence of calls, a set of states or a data type, because its source sits in the document and changes with the text. A sketch suits what boxes and arrows cannot show. So a request for sketch notes on a design doc gets whichever of the two shows the passage's idea. A figure never repeats what a table beside it already says, and the text says what the figure leaves out, such as a resize or a retry.

The rate limit section of l3a0/ithildin-runtime's architecture doc shows the difference. A Mermaid flowchart drafted first showed which request goes to which bucket, which the table beside it already gave, and not the buckets themselves. Sketches of each bucket refilling and holding at most 10 tokens took its place before it was committed.

Draw a sketch in the style of the blog's sketch notes: an animated GIF drawn stroke by stroke as if on a whiteboard. A scene module, a Python module that lists its strokes and labels in drawing order, draws it with the shared whiteboard helpers in l3a0/ithildin-core, and tests pin its words, colours and figures. l3a0/quantitative-trading's `sketch-notes` skill describes the scene, its tests and how to draft one. A sketch sits right after the text it draws, embedded as an image whose alt text says what it draws, and changes in the same commit as that text. A figure drawn to scale reads its numbers from the source the text quotes, never typed twice.

A Mermaid diagram sits beside the list it draws and keeps that list's order. Mermaid's layout reorders nodes to cut crossings, and GitHub's version can differ from a local render. So force the order with `direction TB` and invisible `~~~` links inside a subgraph, draw edges to the subgraph rather than to its nodes, and check the picture on GitHub as well.

The words in a diagram follow the same rules as the prose. A label says what happens, in a phrase with a verb and a clear actor, and one that only names a component or a participant needs no verb. Spell out shorthand, hold one idea in a label, and wrap a long one.

### 4. State each rule it cites

Replace a number chain, such as "case 3 of rule 5 of `### A section`", with what the rule requires, then link the section by name. A link alone is fine where the sentence already says what happens. A list item in view of the sentence naming it needs no statement, and neither does a heading. Two checks keep the statement true.

1. Read the rule before writing the statement. A number in one section can mean a rule in another.
2. Add no condition and drop none that matters at that spot. A proposal stays labelled.

### 5. Prove every fact survived

Change only the shape. New words appear only in the opening, headings, table cells, diagram labels and the plain statement of a cited rule, and each says only what the passage or that rule already says. No number, name, condition or label changes.

1. Keep the old text open and walk it clause by clause, ticking each against the new text. A clause with nowhere to go means the list of questions misses one, so add a heading or a table row rather than dropping the clause.
2. Commit the rewrite, then run `python3 <this plugin>/skills/ask-team/scripts/removed_text.py --min-words 2 CHECKOUT=FROM..TO`. CHECKOUT is the path of the repository holding the passage, FROM is the commit before the rewrite, and TO is the commit holding it. The default of five words skips a shorter condition. Read every run. `still in` at this setting only means two words in a row matched, so read the line it names and confirm the condition stands there.
3. Check each table cell against the rule behind it. A cell shortens a sentence, so it is where a condition goes missing. Write "can go out" where the rule says can, never "goes out", and name a halt in every row that has one, so the row beside it does not read as no halt.
4. Sweep the repository's other surfaces for a statement of the same fact. Where a repository's rules say a change reaches its diagrams and tables in the same commit, follow them.

### 6. Render it and look

A Mermaid diagram that renders can still be wrong, so read what it drew. Three faults pass a render check, and `ask-team`'s `scripts/diagram_words.py` looks for all three.

1. A flowchart, state or class label that starts like a Markdown block, such as "1. Refit" or "- Refit". Mermaid 11.4.1 draws "Unsupported markdown: list" in the box. Start the label with a word, such as "Step 1:".
2. Two statements joined on one line, which still parse because a sequence message runs to the end of its line. The arrow disappears into a label. In a scripted edit, match leading spaces with `[ \t]+`, never `\s+`, which also matches a newline and pulls the next statement onto the line.
3. A hash or a semicolon that ends a label early. A sequence label such as "order #4 is filled" draws "order". Write the entity, `#35;` for a hash or `#59;` for a semicolon.

Run `python3 <this plugin>/skills/ask-team/scripts/diagram_words.py page <repo> <new folder>/out.html`, which prints each fault it finds, serve that folder with `python3 -m http.server <port> --bind 127.0.0.1 --directory <new folder>`, open the page in a browser and read each diagram's listed words. The page needs a connection to the CDN that serves Mermaid. It draws with Mermaid 12.2.0, the version GitHub's viewer held on 2026-11-06, which draws the first fault's words, so the printed list rather than the words names that fault. Where the rewrite rewords an existing diagram, `diagram_words.py compare <repo> <base commit>` checks that its structure did not change. Run the repository's lint and tests too.

A sketch has no parser to name a fault, so draw it with the draft check the `sketch-notes` skill describes, which prints every rule the scene breaks, then look at its last frame. Read every label against the text it draws and against the rules for a diagram's words in step 3, and the embed's alt text against the picture.

### 7. Have a fresh reader check the meaning

Send the diff to a general-purpose agent that has read none of the conversation, with this question: does the new text keep every fact, and would a reader with none of the context follow it on one read? On a design doc, `ask-team`'s reader lens adds the checks on structure. A review of the loss stop section found that "Held" cell, and a diagram label whose "its" did not say whose send it meant. Apply what survives. Where no such reader read the final commit, say so in the pull request comment.
