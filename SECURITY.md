# Security Policy

## Supported Versions

Only the latest release of the `l3a0` plugin is supported. Update with
`claude plugin update l3a0@l3a0` before reporting an issue.

**Table:** Supported versions

| Version | Supported |
| ------- | --------- |
| 0.6.x (latest) | ✅ |
| < 0.6 | ❌ |

## Reporting a Vulnerability

Please report vulnerabilities privately via
[GitHub's private vulnerability reporting](https://github.com/l3a0/claude-plugins/security/advisories/new)
for this repository. If that page is unavailable, open a
[GitHub issue](https://github.com/l3a0/claude-plugins/issues/new) asking for a
private contact channel — do not include exploit details in the public issue.

You can expect an acknowledgement within a week. Please allow a fix to land
before public disclosure.

## Scope

The skills in this repo run locally and drive the user's own logged-in
browser session and local app data (see each skill's README/SKILL.md for its
exact access). Reports of particular interest:

- Anything that could exfiltrate highlight data or credentials off-machine
  (the pipeline is designed to be local-only; the capture receiver binds
  `127.0.0.1`, validates paths, and refuses any request whose `Origin` is not
  `https://read.amazon.com`).
- Path injection or command injection via scraped page content or filenames.
- Prompt-injection vectors in skill instructions that could cause unintended
  actions.
- The `ask-board` agents advise on a venture whose brief and minutes under
  `~/.config/board/` hold personal finances, and some seats search the web.
  The boundary is the PreToolUse hook in `hooks/board-guard.sh`. It limits a
  board agent to a short list of tools, confines its reads to the working
  directory and its own memory folder, excludes secret names from its
  recursive searches, confines its writes to that memory folder, keeps the
  brief's figures out of its web searches, and lets only the counsel and
  accountant seats fetch pages, from a primary-source domain allowlist. In scope are any way past that hook, a fetched page that
  steers an agent, and anything that moves the brief, the minutes, the
  ledgers or a seat's notes off the machine. Out of scope by design: an
  injected line landing in a seat's own `MEMORY.md`, which the minutes list
  under `## Memory changes`, and injected text on a page from an allowed
  domain, since the domain list rather than the page is the boundary.
- The `ask-team` role agents have Read, Grep, Glob and Bash, and no hook
  confines them. That they edit nothing is an instruction in each agent file,
  not an enforced boundary, so a role agent runs with the session's own
  permissions. In scope is any way the plugin itself grants them more than
  that, such as a hook that loosens the session's permissions for them. A
  role agent that ignores its instruction under the session's own
  permissions is out of scope, since the session's permission mode is the
  boundary there.
- `review_post.py`, in `ask-team`, posts review comments and edits pull
  request bodies as the user's `gh` login, sending back a body it read from
  GitHub. In scope is any path where text in a pull request steers what it
  posts, or where it writes outside the body's `## Revision` section.
- `diagram_words.py`, in `ask-team`, writes a local page that draws a
  repository's diagrams, whoever wrote them, with Mermaid loaded from
  `cdn.jsdelivr.net`. A content security policy on the page confines it. In
  scope is any way a diagram runs a script there or sends data off the machine,
  or any way the script reads a file outside the repository.
- `update-build-board` and `sync-prune-next` act on GitHub as the user's
  `gh` login, setting labels, posting comments, dispatching a workflow, and
  deleting local worktrees and branches. In scope is any path where text in
  an issue, a comment or a page steers one of those actions, or where the
  pruning loop calls unpushed work safe.
- `book-text` reads a book PDF the user supplies with poppler's command-line
  tools and Apple Vision, and its scripts make no network call. Its output
  is a copyrighted book's full text, and each script refuses an output
  folder inside a git repository. In scope is any way its scripts send that
  text off the machine, or write it outside the folders they are given.
- `loop-cost` reads Claude Code session transcripts under
  `~/.claude/projects`, which hold anything a session read or wrote, and
  prints only token counts and dollars. Its skill then posts those figures as
  a `## Cost` comment through the user's `gh` login, with a skill proposal in
  the session's own words. In scope is any path that puts transcript content,
  rather than its totals, into the output or a comment.
- `book-to-rules` reads a copyrighted book's full text, which is untrusted
  input, and opens pull requests and posts comments on public repositories
  as the user's `gh` login. The book's text, its OCR output and the reader
  notes belong only in the run directory, `~/Documents/Claude/kindle/<book>/`.
  Its `book-reader` agents have Read, Grep, Glob and Write and no shell, so
  a line of the book cannot run a command. That they write only their notes
  file is an instruction, not an enforced boundary. In scope are any path
  where book text or a reader's notes steer a `gh` action, and any path that
  carries more than a short phrase of the book into a tracked file or a
  comment. `scripts/overlap.py` is the check for the second.
- `find-free-cash` reads the user's brokerage balances, positions and orders
  through the SnapTrade tools, which expose reads only, and writes them to an
  input file in the session's scratchpad. Its scripts make no network call
  and place no order. In scope is any path that carries an account's figures
  into a tracked file, an issue or a comment, and any way the skill could
  lead a session to place, change or cancel an order.
