---
name: ask-board
description: Convene a board of directors on a strategic decision for a one-person venture. Separate advisor agents, each with its own objective, write blind memos and cross-examine. A secretary agent drafts the synthesis without knowing the CEO's view, and the main thread chairs and keeps the minutes. Use when the user asks to "ask the board", "what would my board say", "convene the board", "give me board feedback on" a plan, or asks a strategic question as the CEO or sole operator of their own venture, such as "should I do X first", "what should I focus on first", or "is my plan right or wrong".
---

# Board of directors

A single answer to a strategic question blends every concern into one voice and hides where the concerns disagree. This skill splits the answer across separate agents that cannot see each other. Each one holds one objective and names what it would sacrifice for it, so the disagreement reaches the CEO as a choice with a deciding metric rather than as a hedge.

The user is the CEO: the sole operator of a venture funded with their own money and hours. The main thread is the chair. It runs the procedure, checks facts, and keeps the minutes. A separate secretary agent drafts the synthesis, because the chair knows which answer the CEO favors and the secretary does not. The chair holds the pen, not a vote, and adds no opinion of its own.

Invoke it as `/l3a0:ask-board`, or let it start on its own when a request matches the description above.

## The seats

Each seat is a plugin agent, launched with the Agent tool's `subagent_type` set to the name below. All nine run on the same model, so each seat's charter names what it optimizes, what it will sacrifice, and the question it always asks. A charter that named only a domain would produce nine copies of one answer.

| Seat | `subagent_type` | Optimizes | Always asks |
| --- | --- | --- | --- |
| Chief Financial Officer | `l3a0:board-cfo` | Return on capital and on the CEO's hours | Does this beat an index fund after costs and the CEO's time? |
| Chief Risk Officer | `l3a0:board-risk` | Probability of ruin stays near zero | What is the maximum loss, and what stops trading when it hits? |
| Chief Scientist | `l3a0:board-scientist` | Evidence that the edge is real | What out-of-sample evidence exists, and how many variants were tried? |
| Chief Technology Officer | `l3a0:board-cto` | Backtest and live run the same code on the same data | Does the live path reproduce the backtest number? |
| Chief Operating Officer | `l3a0:board-coo` | Fewest operator hours, no single point of failure | What happens when the CEO is sick for a week, or the broker API is down? |
| Chief Information Security Officer | `l3a0:board-ciso` | Nobody else can move the money | Where do the broker keys live, and who can withdraw? |
| General Counsel and Tax | `l3a0:board-counsel` | Nothing done that is expensive to undo | Which rules does this touch, in which jurisdiction, and which has a deadline? |
| Strategist | `l3a0:board-strategist` | A durable edge in a market with capacity | Who is on the other side, and why do they lose to you? |
| Independent Director | `l3a0:board-independent` | Finding why the hypothesis or the consensus is wrong | What would have to be true for the opposite plan to win? |

Trading is the worked example in every charter, and the seats apply the same questions to any one-person venture.

The secretary, `l3a0:board-secretary`, holds no seat. It reads the memos without the CEO's hypothesis and drafts the synthesis.

## Limits

The board advises on how the venture is built and run: sequencing, risk rules, process and structure. It does not recommend specific securities, position sizes or allocations. When the CEO asks for one, say so and return that decision to the CEO. The counsel seat gives no legal or tax advice. It names the rules a decision touches and says when the CEO needs a licensed professional.

The price of a sitting is between five and ten agent runs on the session's model. A question with one obvious answer does not need a board, so answer it directly and offer a sitting only if the CEO wants one.

## Where the brief and the minutes live

The brief describes the venture and the CEO's finances, hours and constraints. The minutes record each sitting. Both hold personal financial details, so both live outside every repository.

- Brief: `~/.config/board/brief.md`
- Minutes: `~/.config/board/minutes/YYYY-MM-DD-<slug>.md`

Never write either into a repository, an issue or a pull request, and never quote the brief's figures into one.

## What the directors remember

Every agent has `memory: user` in its frontmatter, so Claude Code gives it a memory directory that lasts across sittings, at `~/.claude/agent-memory/l3a0-board-<seat>/`. The first 200 lines of its `MEMORY.md` load when it starts. Each seat records the positions it took, the predictions it made with a date to check them, and the decisions the CEO took against its advice. The secretary records only notes on its own drafting, so it carries no lean toward past winners into the next draft.

Every agent has Read, Grep and Glob, so a seat can search the minutes itself rather than see only what the chair passes in. No agent has Bash, because a shell can read environment variables and key files. The minutes and each agent's memory are the record of past sittings. Raw session transcripts are not, since Claude Code deletes them after a set number of days.

## A sitting, in seven steps

1. Intake.
2. Seat the board.
3. Blind round.
4. Cross-examination on a split, or a rival plan on agreement.
5. Fact check.
6. Blind draft of the synthesis.
7. Verdict and minutes.

Cap a whole sitting at ten agent runs. The blind round, the callbacks in step 4 and the secretary in step 6 all count, and so does a continued agent. With six seats in the blind round and one secretary, that leaves three callbacks.

### 1. Intake

Rewrite the CEO's message as one decision, in the form "Decide whether to X before Y" or "Decide which of X, Y and Z comes first". Split off the CEO's own hypothesis, meaning the answer the message already leans toward, such as "I think an MVP strategy comes first". Record it word for word. It stays with the chair until step 4, and the secretary never sees it.

Load the brief from `~/.config/board/brief.md`. If it is missing, create `~/.config/board/` and copy [templates/brief.md](templates/brief.md) there. Then ask the CEO only what this sitting needs, which is at most these four, and fill them into the brief.

1. Capital at risk: the amount the CEO can lose without changing their life.
2. Hours per week the CEO can give the venture.
3. The goal, with a horizon.
4. Hard constraints, such as a day job, a jurisdiction or a household need.

Continue the sitting once those are answered. The rest of the template fills in over later sittings.

Load past decisions. Every minutes file in `~/.config/board/minutes/` ends with a `## Decision` section naming a decision and its status: adopted, rejected or deferred. Read that section from every file, and read in full the three most recent minutes plus any whose title touches this decision. When this decision brings back a plan the CEO rejected, tell the seats so, and require any memo that backs it to name the evidence that is new since the rejection. A rejected plan does not return on the same evidence.

If the decision concerns a repository, note its absolute path for the seats to read. Otherwise pass none.

### 2. Seat the board

Pick the four to six seats the decision needs. board-independent sits every time. State in one line which seats sit and why, and move on without waiting for approval.

Typical sittings, as a starting point rather than a rule:

- What to build or do first: CFO, Risk, Scientist, CTO, Strategist, Independent.
- Going live with real money: Risk, CTO, COO, CISO, Independent.
- Structure, entity or tax: Counsel, CFO, Risk, Independent.
- Whether to keep a strategy or kill it: Scientist, Strategist, CFO, Independent.

### 3. Blind round

Launch every seated agent in one message, so they run in parallel and in the background. Each prompt carries these four things.

1. The decision, as rewritten at intake.
2. The full text of the brief.
3. The past decisions and relevant minutes, or a line saying there are none.
4. The repository path, when the decision concerns one.

Leave the CEO's hypothesis out of every prompt. A seat that reads "I think X is right" anchors on X, and the blind round exists to find out what each seat says without that anchor. Each seat replies with a memo of about 300 words, in the eight parts its charter lists: first move, reasoning, failure, pre-mortem, base rate, what would change its mind, questions for the CEO, and confidence. Every factual claim in it is tagged VERIFIED with a source, or ASSUMED.

Wait for every notification before reading the memos together. Do not predict a memo that has not arrived.

Score each memo against the hypothesis as its blind verdict. It agrees when its first move is the hypothesis, disagrees when it puts something else ahead of it, and is conditional when it accepts the hypothesis only after a precondition.

### 4. Cross-examination on a split, or a rival plan on agreement

Read each memo's first move and group the memos by what they put first. Two first moves that differ only in wording are one position. A split means at least two positions.

**On a split,** call back the seats on each side plus board-independent. Each prompt carries the decision, the brief, the CEO's hypothesis, the seat's own memo and every other memo. Each seat replies with one rebuttal, a verdict on the hypothesis, and the reason for any change of position. A seat may change position only by naming a new fact or a flaw in its own memo. Headcount and confidence are not reasons, because agents on one model drift toward the majority and a correct minority is lost that way. When the split holds more seats than the cap leaves room for, keep board-independent and the most confident seat on each side.

**On agreement,** do not end the sitting. A unanimous blind round from agents on one model is weak evidence, since they share one set of blind spots. Call back board-independent alone, with the hypothesis and every memo, and ask for the strongest rival plan to the consensus and what it believes the consensus missed.

Continue a seat's blind-round agent with SendMessage when that tool is available, or launch the seat again with its own memo in the prompt.

A seat's final verdict is its rebuttal verdict when it was called back, and its blind verdict otherwise.

### 5. Fact check

Check claims against a primary source with WebSearch or WebFetch before the CEO sees them, and prefer the regulator's, tax authority's or vendor's own page. Work in this order.

1. Every base rate a memo cites.
2. Every claim tagged ASSUMED that an argument rests on, such as a regulatory threshold, a tax rule, a fee or a deadline.
3. Any claim tagged VERIFIED whose source looks weak or secondhand.

Record each result. A claim that turns out false is struck, and the result names the seat whose argument it weakens. A claim that could not be checked stays ASSUMED.

### 6. Blind draft of the synthesis

Launch `l3a0:board-secretary` with these six things, and nothing that reveals the CEO's hypothesis.

1. The decision.
2. The brief.
3. The past decisions, without the hypotheses of past sittings.
4. Every blind memo.
5. Every rebuttal or rival plan, with verdict lines removed, and with any mention of the plan the CEO favors replaced by "a plan under discussion".
6. The fact-check results.

The secretary weighs each split by the argument on each side and never by how many seats hold it. It returns the agreements, the splits with their deciding metrics, the questions only the CEO can answer, and a recommended decision with its first three actions, or no recommendation when the split is too close to call. The chair does not rewrite that draft. The draft exists because a writer who knows which answer the reader wants bends toward it.

### 7. Verdict and minutes

Compare the secretary's draft against the hypothesis, then wrap the draft in the minutes below and show them to the CEO. The verdict count describes the board. It does not decide a split, and the recommended decision stays the secretary's.

```markdown
# Board sitting: <the decision>

Date: YYYY-MM-DD. Seated: <seats>. Hypothesis: "<the CEO's words>".

## Verdict on the hypothesis

Agree N, conditional N, disagree N, by final verdict.

| Seat | Blind verdict | Final verdict | Reason for any change |
| --- | --- | --- | --- |
| <seat> | <agree, conditional or disagree> | <same or new> | <new fact, flaw in own memo, or "NO REASON GIVEN"> |

<The secretary's draft, as written.>

## Facts checked

- <Claim>: <source and date checked>, struck, or still ASSUMED.

## Memos

<Each seat's memo, rebuttal or rival plan, as written.>

## Decision

Decision: <the recommended decision, or the CEO's own decision when it differs>.
Status: <adopted, rejected or deferred>.
Evidence that would reopen it: <for a rejected plan, what new evidence would justify bringing it back>.
```

Flag every row whose verdict changed without a new fact or a flaw in the seat's own memo as "NO REASON GIVEN". Such a change is a sign of drift toward the majority, and the CEO should read that seat's blind memo rather than its rebuttal.

Save the minutes to `~/.config/board/minutes/YYYY-MM-DD-<slug>.md`, where the slug is three to five words of the decision in kebab case. Save them only after every agent in the sitting has finished, because the seats can search the minutes and the file holds this sitting's hypothesis. The status starts as deferred. When the CEO adopts or rejects the decision later in the conversation, update the `## Decision` section, so the next sitting holds the CEO to it.

## Why the procedure looks like this

Each rule above answers a failure that research or practice has named. Keep these in mind before removing one.

- **Verdicts change only for a reason, and splits are weighed by argument.** Agents on one model adopt the majority answer and voting discards correct minority answers. Bertalanič and Fortuna, "The Cost of Consensus", CAIS 2026. Wynn, Satija and Hadfield, arXiv 2509.05396. Choi, Zhu and Li, arXiv 2508.17536.
- **The secretary drafts without the hypothesis.** Assistants bend toward a view the user stated. Sharma et al., "Towards Understanding Sycophancy in Language Models", arXiv 2310.13548.
- **Every memo carries a pre-mortem.** Klein, "Performing a Project Premortem", Harvard Business Review, 2007.
- **Every memo names a base rate, and the fact check starts there.** The Mediating Assessments Protocol in Kahneman, Sibony and Sunstein, *Noise*, 2021. The book asserts its benefit rather than measuring it.
- **A unanimous round calls the independent director for a rival plan, and its dissent must be what it believes.** Nemeth, Brown and Rogers, 2001, found authentic dissent outperformed assigned devil's advocacy. Schweiger, Sandberg and Rechner, 1989, on dialectical inquiry.
- **Claims are tagged VERIFIED or ASSUMED, and decisions carry forward with a status.** The board-meeting skill in alirezarezvani/claude-skills, which asserts the practice rather than measuring it.
