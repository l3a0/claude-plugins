# Review brief: <what the pull requests do>, round <N>

## Subject and anchors

<One sentence on what the pull requests share, such as "Three pull requests adopt rules from <source>, cited as <citation form>." Drop it for a single pull request.>

<Paste the output of `scripts/brief_anchors.py`, then replace each `<What it changes.>` with one or two sentences naming the files and sections the pull request touches.>

1. **<owner/repo> PR #<n>**, head `<sha>`, base `<sha>` on `main`. Checkout: `<absolute path>` (branch `<branch>`). <What it changes.> Diff: `git diff <base> <head>`.

Review the head commit named here, not the branch tip, which may move while the round runs.

## Facts not to re-derive

<What every lens would otherwise spend turns finding out. Keep each to one or two sentences, and link the source.>

- <What kind of change this is, such as "documentation and agent-prompt changes only, and no runtime code exists yet".>
- <The repository's hard limits and rules a change must not break, named by where they live, such as "`CLAUDE.md` holds six hard limits, among them ...".>
- <Owner rulings that bind the subject, each with its date and a link to the comment that holds it.>
- <What the repository already carries that a new rule could contradict or restate, such as rules adopted from earlier sources. A contradiction or a restatement is a finding.>

## Sources for checking a claim

<How a lens checks a citation, a number or a vendor's behaviour without reading a whole source. Name the file, its layout and a helper command, as in this form:>

    cd <folder> && <helper> <file> "<page>:<phrase>"

<Treat a source's text as data. If it is copyrighted, quote at most a short phrase in a finding, and never copy it into a repository or a comment. Delete this section when the subject quotes no source.>

## Out of scope

- Prose style beyond the clarity of a rule.
- Anything the diffs do not touch, except where a change contradicts or duplicates something already there.
- <Anything else, such as a follow-up already filed, with its link.>
