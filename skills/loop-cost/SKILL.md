---
name: loop-cost
description: Price a finished plan, build or review loop in tokens and dollars from the transcripts of the agents it ran, and name what a skill could save. Use when a decompose loop exits, when a build hands its pull request over, when a review's lenses and verifiers have reported, or whenever asked what a piece of agent work cost.
---

# Price a loop

The owner decides what work is worth by what it costs, so every plan, build and
review loop reports its cost when it finishes. A number in that report has to
be measured, not read off a notice. A loop reported on 2026-10-11 as "about
242k tokens" had processed 18.3M tokens, for at least 5.29 US dollars.

## When to run it

Run it once per loop, after the last agent in that loop has reported.

1. **A plan loop:** a decompose loop exits, including any loops on child issues it spawned.
2. **A build:** the build agent hands its pull request over, after its checks settle.
3. **A review:** every lens and every verifier has reported.

Price each loop on its own, so the report can name what each one cost. When the
owner asks what a stretch of work cost, price all of it together as well.

## Find the transcripts

A loop's cost is the sum over every agent it ran, so collect all of their
transcripts. Each agent's transcript is `agent-<id>.jsonl` under
`~/.claude/projects/<project>/<session>/subagents/`, beside an
`agent-<id>.meta.json` that holds the `description` the agent was spawned
with. The `output_file` path an `Agent` spawn returns links to the transcript.

Count every agent the loop ran, not only the ones that produced its result.

1. **A review loop is its lenses and its verifiers.** The verifiers that tried
   to refute each finding cost as much as the lenses, sometimes more. On
   2026-11-03 seven lenses on one round of pull requests cost 8.79 US dollars,
   and the verifiers ran on top of that.
2. **Reading or preparation agents are a line of their own.** Agents that read
   a book, a spec or a codebase so the loop could start are part of what the
   work cost, but they are not the review or the build. Price them as their
   own group, so the report shows what the preparation cost apart from the
   loop. On 2026-11-03 seven agents that read one book cost 7.33 US dollars.

## Price them

Run the script from the subagents folder, or point `--dir` at it, and name
the agents in any of three ways.

```bash
S=${CLAUDE_SKILL_DIR}/scripts/agent-cost.py
D=~/.claude/projects/<project>/<session>/subagents
$S --dir $D a1b2c3d4e5f600001 a1b2c3d4e5f600002   # by id
$S --dir $D --ids-file ids.txt                     # a file of ids, "-" for stdin
$S --dir $D --match '^Read part'                   # by spawn description
```

1. **By id.** An id can be written `a1b2...`, `agent-a1b2...` or
   `agent-a1b2....jsonl`. An id with no transcript in the folder stops the
   script with an error that names it, so a typo never prices short.
2. **By a file of ids.** One or more ids per line, with `#` starting a comment.
3. **By description.** `--match` takes a Python regular expression and
   selects every agent whose spawn description it matches. It lists the
   agents it matched on standard error, so check that list before reporting.
   This is the way to price a loop after a context compaction has dropped the
   ids, as long as its agents' descriptions share a pattern.

Plain transcript paths work too: `$S <transcript.jsonl> [<transcript.jsonl> ...]`.
A path that does not exist is an error, never looked up by its file name in
the folder.

### Pass a list of ids to the script, not to the shell

zsh does not split a plain variable into words. With `IDS="a1 a2 a3"`,
`ls agent-$IDS.jsonl` passes one argument made of all three ids, and a loop
over `$IDS` runs once. On 2026-11-03 that sent the script no transcripts at
all, and the agent lists had to be rebuilt by hand. The script now splits any
argument that is not an existing file on spaces and commas, so
`$S --dir $D $IDS` works in zsh and bash alike. To build paths in the shell
instead, use a zsh array: `R=(agent-a1 agent-a2); $S ${R/%/.jsonl}`.

### Price several groups at once

`--group NAME=SPEC` prices one group, and repeating it prints one total per
group and then a combined total. SPEC is a list of ids, `@FILE` for a file of
ids, or `match:REGEX` for a description match.

```bash
$S --dir $D \
  --group 'reading=match:^Read part' \
  --group 'lenses=match:lens on PR' \
  --group 'verifiers=@verifier-ids.txt'
```

An agent placed in two groups counts in each group's total and once in the
combined total.

### What the output shows

The script prints one line per model and a total. Each line gives the turns,
the tokens by kind (input, 5-minute cache write, 1-hour cache write, cache
read, output) and the dollars. A message that appears in two transcripts,
such as a forked agent's, counts once.

The script's tests build their own transcripts, so they run anywhere. In a
checkout of l3a0/claude-plugins, `python3 tests/test_agent_cost.py` runs them.

## Report it

Give one line per loop in the report to the owner, as in this example.

> The decompose loop on [l3a0/quantitative-trading#531](https://github.com/l3a0/quantitative-trading/issues/531) cost at least 5.29 US dollars: 18.3M tokens over 107 turns, almost all cache reads.

A review gives its lenses and its verifiers a line each and then their sum,
and any reading agents a line apart, as `--group` prints them.

Name what dominated when one kind of token did, because that is what a cheaper
loop would change. Cache reads usually dominate, and they grow with the number
of turns rather than the size of any one result.

## Post it on the issue

The owner's global `CLAUDE.md` asks for the cost on the issue the work
tracks, as well as in the report (owner directive, 2026-10-12). Post two kinds
of comment.

1. **At handover, a comment that starts with the line `## Cost`.** Post it on
   the issue in the same step as the report. List one line per loop, in the
   form above, and say the figures are to date. A session hands over before
   the owner merges, and the merge is what closes the issue, so waiting for the
   close would usually mean nobody posts at all.

   > ## Cost
   >
   > To date, at list prices, with output a lower bound:
   >
   > 1. Decompose loop: at least 23.45 US dollars, 62.6M tokens over 435 turns.
   > 2. Build: at least 13.37 US dollars, 43.0M tokens over 152 turns.
   > 3. Review, with its fixes: at least 17.58 US dollars, 38.7M tokens over 254 turns.
   >
   > Cache reads made up almost all of the tokens.

2. **Once the issue closes, a comment that starts with the line
   `## Cost total`.** Add up every `## Cost` comment on the issue and on its
   closed sub-issues, list each comment it summed with its link, and name any
   loop known to have run that posted none. Whoever closes the issue by hand
   posts it. When a merge closed the issue, the next status round that finds
   it closed without a total posts it. The total reads comments rather than
   transcripts, so it still works after a worktree and its transcripts are
   gone.

A `## Cost` comment posted after a total gets a new total that covers it.

This command finds the comments to sum on one issue. Run it again on each
closed sub-issue.

```bash
gh issue view <n> --repo <owner>/<repo> --json comments --jq '.comments[] | select(.body | test("\\A## Cost\\r?\\n")) | .url'
```

A pull request on its own, closing no issue, still reports its cost in chat,
and the pull request's own review comment can carry it.

## Name what a skill could save

The owner's global `CLAUDE.md` asks a session to turn a procedure worth keeping
into a skill, so the next session does not pay to work it out again (owner
directive, 2026-11-03). Nothing in a loop's own steps asked for that, so a
session finished, priced its work and named nothing. Run these steps once, at
handover, after the loop's last agent has reported.

1. **Price the loop by step.** Use `--group`, with a group per reading part, per
   build stage or per review round, such as
   `--group 'r3=match:^review 31 r3 '`. Where the session worked a procedure out
   itself, pass its own transcript as a group too, because the agents' figures
   leave out the main thread.
2. **Name the costliest group** in the report, with its share of the total.
3. **Ask what that cost bought.** A skill saves the turns spent working out what
   to do. It does not save a lens's judgment or a reader's reading. So a costly
   group of agents doing the same judged work qualifies only for the parts they
   each worked out by hand, such as a script they all wrote or a search they
   all ran. The fourteen review rounds of *Trading in the Zone* cost at least
   146.87 US dollars with `review-round.md` already written, because the cost
   lay in the number of rounds rather than in working out the steps.
4. **Apply the rule's test.** A procedure qualifies once it has run twice in the
   same shape, or once when working it out cost more than about 10 US dollars.
5. **Read the skills that exist first.** Search the plugin's `skills/` folder,
   its templates and its scripts for the procedure, and extend what covers
   part of it. On 2026-11-04 a report proposed writing down a review brief that
   `ask-team`'s `templates/review-brief.md` already held.
6. **Write the outcome where the cost goes.** Add it to the `## Cost` comment,
   or to the review comment when no issue is tracked.

   > ### Skill proposal
   >
   > Each round of this review edited the pull request's `## Revision` section
   > by hand. Extend `ask-team` with a script that holds the edit, so the next
   > round does not work it out.

   Name the skill, what it would hold, the scripts for its `scripts/` folder and
   what the next run would no longer work out, and copy any scratchpad script
   somewhere that outlives the session. Where nothing qualifies, write one line
   saying so and why, so the check is seen to have run.

Build it in the same change when it is small and inside the work the session was
given. Otherwise it stays a proposal for the owner.

## What the number cannot say

1. **Output is a lower bound.** A subagent transcript often keeps the usage
   from the start of each reply, so a turn that wrote a long tool call can
   record single-digit output tokens. The script takes the larger of that and
   the visible content at four characters a token. Thinking the API omitted
   never reaches the transcript and is not counted. So say "at least".
2. **Dollars are list prices, not a bill.** On a subscription plan nothing is
   charged per token, and the figure measures usage instead.
3. **`subagent_tokens` in a completion notice is not a cost.** It is the size
   of the agent's context at its last turn. Never quote it as what the agent
   spent.
4. **The main thread's own turns are not included unless its transcript is passed.**
   Pricing only the agents is the right boundary when the main thread only
   wrote the prompt and read the result. To price a whole session, also pass
   the session's own transcript, `~/.claude/projects/<project>/<session>.jsonl`.
5. **An agent still running is priced as of now.** Its transcript keeps
   growing, so say the figure is partial.

## Write no dollar sign before a digit in this file

The skill loader treats a dollar sign followed by a digit as an argument slot,
so a price written that way in this file arrives as a word from the request.
Write amounts as "5.29 US dollars" here. Reports to the owner are not affected.

## Keep the prices current

`PRICES` in `scripts/agent-cost.py` holds Anthropic's first-party list prices from the
`claude-api` skill's model table, cached 2026-10-06. A model the table lacks is
reported in tokens and flagged as unpriced, so the total never silently drops
it. When that flag appears, or a new model ships, load the `claude-api` skill.
Never take prices from memory. Add the row with its cache-write and cache-read
rates, because the cache-read ratio differs by model: 0.05 times input on Opus
5.5, 0.1 on Sonnet 5.5, and 0.025 on Fable 5.1.
