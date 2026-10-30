---
name: ask-team
description: Convene a repository's engineering team on a plan, a design, a pull request or a blog post. Separate role agents, one per role, each review the same subject blind to the others, holding only what their role protects and may veto. Verifiers then try to refute each finding by executing code, and only what survives is acted on. Use when asked to "ask the team", "convene the team", "have the team review" an issue, a design doc, a pull request or a blog post, to audit an issue's plan before a build starts, or for the per-role lenses a repository's team charter names for its review step. A pull request review or a post review such as review-post can call it in lens mode, where it returns verified findings to the caller and posts and fixes nothing. Not for owner decisions about money, live trading, contracts or law, which go to the board through /l3a0:ask-board.
---

# Ask the team

A single review blends every concern into one voice and hides where the concerns disagree. A risk engineer who weighs return against risk the way the builder does is a second builder. So this skill splits a review across role agents that cannot see each other. Each one holds the objective its role protects and names the vetoes that role may cast. The disagreement then reaches the owner as a finding with evidence, rather than as a hedge.

The main thread is the delivery lead. It picks the roles, writes their prompts, verifies what they find, and posts the result. It adds no finding of its own, because a coordinator that reviews stops coordinating.

The role agents are not standing agents. Each one runs for one review and ends, so a role is an objective a session takes on for one piece of work rather than a member who remembers the last review. The agents keep no memory between reviews for the same reason.

This skill was drafted for l3a0/ithildin-runtime, a trading platform whose `docs/team-charter.md` at `3c2242c` defines the eight roles. The plugin's defaults generalise each role to the property it guards in any repository, such as one implementation of each behaviour, data that cannot be recaptured, or an outside write that must happen exactly once. Each role then names its trading case as one example, the way the board's seats do. A role whose property a repository does not have is not seated there.

## The roles

Each role is an agent in this plugin, launched with the Agent tool's `subagent_type` set to the name below. The agent file carries the role's default definition and adds the checks that role runs. The defaults are this plugin's own. They generalise ithildin-runtime's charter, whose definitions survive as each role's trading case. When the repository under review has a `docs/team-charter.md`, its section for a role overrides that role's default, and the agent reads it first. That is how ithildin-runtime keeps its trading definitions. `scripts/gen_team.py` generates the eight agent files, so their shared sections are edited there and nowhere else.

| Role | `subagent_type` | Protects | Always asks |
| --- | --- | --- | --- |
| Architect | `l3a0:team-architect` | One implementation of each behaviour, so what is tested is what runs | Does any module behave differently by environment, or exist twice? |
| Quant researcher | `l3a0:team-quant-researcher` | Every claim drawn from data, such as an edge or a number a post quotes | Is this result exploratory or registered, and does the label say so? |
| Data engineer | `l3a0:team-data-engineer` | Data that cannot be recaptured once lost | Can any path overwrite or silently drop a recorded value? |
| Trading systems engineer | `l3a0:team-trading-systems-engineer` | Every write to an outside system happens exactly once, recorded first, such as an order or a posted message | Is every outside write recorded before it is sent, and can a retry double it? |
| Risk engineer | `l3a0:team-risk-engineer` | The worst outcome stays bounded, through one gate every irreversible action passes | Can any irreversible action happen without passing the gate? |
| Test engineer | `l3a0:team-test-engineer` | A test means what it claims | Does a test fail when the code it covers is broken? |
| Operator | `l3a0:team-operator` | The system stops safely and says so | Has each alarm fired in a drill, and does a halt say why? |
| Security reviewer | `l3a0:team-security-reviewer` | Nobody but the owner can act with the owner's credentials | Where does each credential live, and what can it do? |

The owner is not a role agent. The owner rules on what an issue reserves, merges, and switches anything to live.

**The role agents edit nothing.** Each has Read, Grep, Glob and Bash. Bash lets a role run the test suite, a search or a small call that shows its claim, and it could also write a file, so the limit is an instruction in each agent file rather than a hook. Each role writes only to its own scratch folder, and mutates code only in a copy taken with `git archive`. The plugin's `hooks/board-guard.sh` confines only the board's agents, whose names start with `l3a0:board-`, so it neither blocks nor watches a team agent.

## What goes to the board instead

The team reviews how a system is built. Some questions are about money, contracts, law or the owner's time rather than code, and the team has no standing to answer them. These go to the board of directors in this plugin, through `/l3a0:ask-board`, and only when the owner asks for a sitting.

1. Any step toward live trading, such as leaving the paper stage, a capital cap, or a live deployment.
2. Choosing a broker, a data vendor or a host, when the choice carries a cost, a contract or terms of use.
3. Anything with legal or tax exposure, such as committing vendor data to a public repository.
4. Whether a strategy, or the venture itself, is worth the owner's capital and hours at all.

When a finding turns on one of these, the skill does not decide it. It lists the question under `### For the owner` in the posted review, says the board can sit on it, and stops there. The board's seats read only inside the session's working directory, so a sitting about a repository runs from that repository's folder. The owner's ruling then goes on the issue as a dated line. The board's minutes and brief hold personal figures and stay under `~/.config/board/`, never in a repository.

## A review, in six steps

1. Name the subject.
2. Seat the roles.
3. Blind round.
4. Verify.
5. Apply what survives.
6. Post and price.

### 1. Name the subject

The subject is one of five things, and each needs its anchor.

1. **An issue's plan, before a build starts.** The issue number, and the commit of `main` the plan is read against. Where the repository's `CLAUDE.md` asks for a plan audit before work starts, this is that audit, run once per relevant role.
2. **A design doc or a design pull request.** The file, the branch and the commit.
3. **A pull request.** The number and its head commit.
4. **A technical question that crosses modules.** The question, the options, and the files each option would change.
5. **A blog post or other prose that quotes results.** The file and the commit, and the tests or log entries its numbers come from.

Write down what is out of scope, so a role does not review the whole repository. Check whether the repository has a `docs/team-charter.md`, and note its commit, because every role prompt names it.

### 2. Seat the roles

Seat the roles whose objective the subject can hurt, between three and six. Seat a role when the subject touches the thing in its row.

| The subject touches | Seat |
| --- | --- |
| Module interfaces, shared types, a new dependency, the import rule | Architect |
| A research claim, a backtest, a benchmark, a pinned number | Quant researcher |
| A fetch, a capture, a vintage, a snapshot, anything that writes recorded data | Data engineer |
| A write to an outside system through an API, such as an order, a sent message or a GitHub comment, its record, retries, reconciliation | Trading systems engineer |
| An irreversible action, such as an order, a delete, a publish or a deploy, its gate, a limit, the kill switch, a halt | Risk engineer |
| Any code or test change | Test engineer |
| Startup, scheduling, alarms, the dead-man check, deployment | Operator |
| A credential, a permission, a dependency, a workflow, anything public | Security reviewer |
| A blog post or other prose that quotes results | Quant researcher, for exploratory or registered labels and out-of-sample claims. Data engineer, for vintage, vendor and data claims. Test engineer, for every quoted number traced to the test that pins it. For a post this row replaces the others, including the security reviewer's "anything public", so seat any other role only when the post discusses its area |

Three seats are required whatever the count.

1. The test engineer on every pull request that changes code.
2. The risk engineer on anything touching the path to an irreversible action, such as the order path.
3. The security reviewer on anything that adds a credential, a dependency or a GitHub workflow.

A repository whose charter names a required reviewer for some path, as l3a0/ithildin-runtime's names the risk engineer for the order path, adds that seat under its own rule.

A pull request also gets the two lenses the owner's rules give every pull request: completeness, which asks whether the class was fixed rather than one instance, and over-reach, which asks whether the change stayed inside its class. They are not roles, so run them as two more blind agents with those two prompts, using a general-purpose agent.

State in one line the subject, its anchor and the roles seated, then launch.

### 3. Blind round

Launch every seated role in one message, in the background. Each prompt carries six things.

1. The subject and its anchor commit.
2. The path of the repository's `docs/team-charter.md` and its commit, or that it has none.
3. The files and issues to read, with absolute paths for any checkout.
4. What is out of scope.
5. The finding format, which each agent file already carries, so naming it is enough.
6. A scratch folder of its own, such as `<scratchpad>/team-<role>/`, because parallel agents writing to one folder overwrite each other.

No prompt carries another role's findings or the delivery lead's view of the subject. A role that reads "the lead thinks this is fine" reviews that sentence instead of the code.

Each role replies with findings in this shape, and nothing else.

```markdown
### <role>: <one-line claim>

- **Evidence:** <file and symbol at the anchor commit, or a command and its output>
- **Kind:** veto, must fix, should fix, or note
- **Fix:** <the smallest change that resolves it>
```

A veto is allowed only for something in the role's vetoes, as the agent file or the repository's charter states them. Anything else is at most "must fix". A role that finds nothing says so in one line, and that line is a result.

Wait for every notification before reading the findings together. Never predict a finding that has not arrived.

### 4. Verify

A finding is a claim until something executes it. For every veto and every must-fix, launch a verifier whose only job is to refute it. Give it the finding and the anchor, not the role's reasoning. Verify by running, not by reading. A verifier that edits code, such as one that mutates it, runs with `isolation: "worktree"`, so its edits cannot land in the session's checkout.

1. A claim that a test misses a bug: mutate the code with the `fast-mutation` skill where it is installed, or by hand in the verifier's worktree, and see whether the test fails.
2. A claim that a path exists, such as an order reaching a broker around the gate: write the call and run it.
3. A claim about another repository or a vendor: read the file at its commit, or the vendor's own page.

Group findings that rest on the same fact under one verifier. Keep the whole review under ten agent runs where the subject allows, counting the roles, the two lenses and the verifiers.

### 5. Apply what survives

A refuted finding is dropped and listed as refuted. A surviving should-fix or must-fix is applied on the subject's branch, by the session that owns the branch. A surviving veto blocks the pull request until it is fixed, or until the owner overrides it in writing on the pull request. Nothing else lifts a veto, including a majority of the other roles.

For a plan audit, a surviving finding goes on the issue, because the build session reads the issue and none of this conversation. An audit that found nothing writes nothing to the issue.

### 6. Post and price

Post one comment on the pull request or issue whose first line is the review heading the repository's build board reads, which the `update-build-board` skill's moment 5 names. A final pull request comment headed `## Review complete`, posted after the last push, satisfies every board that skill knows. It holds four parts.

1. The roles and lenses seated, the anchor commit, and the charter's commit or its absence.
2. What was found and fixed, one numbered line each.
3. What was refuted or left alone, with the reason.
4. `### For the owner`, listing any question that goes to the board, or saying there is none.

Price the review with the owner's `loop-cost` skill where it is installed, counting every role, lens and verifier transcript. Put the figure at the end of the comment, and post it as a separate comment starting with the line `## Cost` on the issue the subject tracks, in the form the `loop-cost` skill shows, because the status round's cost-total sweep reads only `## Cost` comments on issues.

## Lens mode, inside another review

Another review can call this skill for the team's lenses beside its own, on the owner's ruling of 2026-10-29 UTC that the pull request and blog review skills consult the team for their feedback. The caller owns the branch and the review comment, so in this mode the skill runs steps 1 to 4 and returns, and skips steps 5 and 6. It also skips step 2's two pull request lenses, which the caller runs.

1. **The caller names the subject and its anchor**, as step 1 lists them, and what is out of scope. The skill adds nothing to that scope.
2. **The skill seats the roles the subject touches**, by the table in step 2, and runs them blind, as step 3 says. The caller's own lenses are not shown to the roles, and the roles' findings are not shown to the caller's lenses until both have reported, so neither side anchors on the other.
3. **The skill verifies by executing**, as step 4 says, and drops what is refuted.
4. **It returns the surviving findings to the caller**, in the finding format of step 3, followed by one line per refuted finding with the reason, and any question for the owner under `### For the owner`.
5. **It posts no comment and applies no fix.** The caller applies what it accepts on its own branch and folds the findings into its own review comment, under its own heading, so a board reads one review per round.
6. **Its runs count toward the caller's cost.** The return lists each role and verifier run's `output_file` path or spawn description, so the caller's `loop-cost` run finds their transcripts and its `## Cost` figure covers them. The ten-run bound of step 4 applies to the team's runs alone.

Two callers are meant to use this mode.

1. **A pull request review**, under the owner's rule that every pull request is reviewed by blind lenses before the owner reads it, and under a repository's `## Pull requests` section that carries that rule. The team's roles join the completeness and over-reach lenses there, and the caller runs those two itself rather than asking this skill to.
2. **A review of a blog post before the owner reads it**, such as l3a0/quantitative-trading's `review-post` skill. The subject is the post, seated by the blog-post row of step 2's table.

A caller's own skill should name this mode where it lists its lenses, so a reader of that skill finds it. l3a0/quantitative-trading's `review-post` and `sketch-notes` skills name it, since [l3a0/quantitative-trading PR #783](https://github.com/l3a0/quantitative-trading/pull/783).

## Building is not a review

A build is one session per issue, in its own worktree. This skill does not build. A build session reads the definition of the role that owns its module, in the repository's charter or in that role's agent file, and works to that role's objective. It then runs this skill on its own pull request before handing it over.
