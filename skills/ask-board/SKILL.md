---
name: ask-board
description: Convene a board of directors on a strategic decision for a one-person venture. Separate advisor agents, each with its own objective, write blind memos and cross-examine. A secretary agent drafts the synthesis without knowing the CEO's view, and the main thread chairs and keeps the minutes. Use when the user asks to "ask the board", "what would my board say", "convene the board", "give me board feedback on" a plan, or asks a strategic question as the CEO or sole operator of their own venture, such as "should I do X first", "what should I focus on first", or "is my plan right or wrong".
---

# Board of directors

A single answer to a strategic question blends every concern into one voice and hides where the concerns disagree. This skill splits the answer across separate agents that cannot see each other. Each one holds one objective and names what it would sacrifice for it, so the disagreement reaches the CEO as a choice with a deciding metric rather than as a hedge.

The user is the CEO: the sole operator of a venture funded with their own money and hours. The main thread is the chair. It runs the procedure, checks facts, and keeps the minutes and each seat's record. A separate secretary agent drafts the synthesis, because the chair knows which answer the CEO favors and the secretary does not. The chair holds the pen, not a vote, and adds no opinion of its own.

Invoke it as `/l3a0:ask-board`, or let it start on its own when a request matches the description above. When it starts on its own, without "ask the board" or the slash command, ask once before launching any agent. Step 2 says how.

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

The secretary, `l3a0:board-secretary`, holds no seat and has no tools. It reads the memos without knowing which option the CEO favors and drafts the synthesis.

## Limits

The board advises on how the venture is built and run: sequencing, risk rules, process and structure. It does not recommend specific securities, position sizes or allocations. When the CEO asks for one, say so and return that decision to the CEO. The counsel seat gives no legal or tax advice. It names the rules a decision touches and says when the CEO needs a licensed professional.

The price of a sitting is between six and ten agent runs on the session's model. A question with one obvious answer does not need a board, so answer it directly and offer a sitting only if the CEO wants one.

## Where the files live

Four kinds of file hold personal financial details, so all of them live outside every repository.

1. The brief describes the venture and the CEO's finances, hours and constraints: `~/.config/board/brief.md`.
2. The minutes record each sitting: `~/.config/board/minutes/YYYY-MM-DD-<slug>.md`.
3. Each seat's record lists its past positions and predictions: `~/.config/board/memory/<seat>.md`, such as `memory/board-cfo.md`.
4. The chair-only hypothesis file names the option the CEO favors: `~/.config/board/hypotheses/YYYY-MM-DD-<slug>.md`.

Never write any of them into a repository, an issue or a pull request, and never quote the brief's figures into one. Never name the hypotheses folder or one of its files in any agent's prompt.

## What the directors remember

No agent can write a file. Every seat has Read, Grep and Glob, and the CFO, scientist, counsel and strategist seats also have WebSearch. The secretary has no tools at all. No agent has Bash, because a shell can read environment variables, run any program and send data over the network. Read and Grep can still open any file the user can, so staying inside the brief and the minutes is an instruction, not a tool limit.

So the chair keeps each seat's memory. One record per seat lives at `~/.config/board/memory/<seat>.md`. The chair pastes it into that seat's blind-round prompt, and after each sitting the chair alone appends one entry per seat that sat, in this shape.

```markdown
## YYYY-MM-DD <decision slug>

- Position: <the seat's blind first move, by option label and wording>
- Prediction: <a claim it can be held to>, check by YYYY-MM-DD. Or "none".
- Outcome: pending
```

When the CEO decides, the chair replaces "pending" with the decision and its status, and later with whether the prediction came true. A record never holds the hypothesis, any preference the CEO stated, account numbers, credentials, balances, or figures that would let net worth be worked out.

The minutes and the records are the history of past sittings. Raw session transcripts are not, because Claude Code deletes them after a set number of days. Every agent also inherits CLAUDE.md and auto-memory from the session, and a plugin cannot turn that off. So every charter says that CLAUDE.md, auto-memory and the brief's Goal are context, and none of them is the CEO's answer to the decision.

## A sitting, in seven steps

1. Intake.
2. Seat the board.
3. Blind round.
4. Cross-examination on a split, or a rival plan on agreement.
5. Fact check.
6. Blind draft of the synthesis.
7. Verdict, minutes and records.

Cap a whole sitting at ten agent runs. The blind round, the callbacks in step 4 and the secretary in step 6 all count, and so does a continued agent. Reserve one run for the secretary from the start.

### 1. Intake

**Split the hypothesis off.** The hypothesis is the answer the CEO's message already leans toward, such as "I think an MVP strategy comes first". Write it word for word to `~/.config/board/hypotheses/YYYY-MM-DD-<slug>.md`, where the slug is three to five words of the decision in kebab case. If the message leans toward nothing, write "none".

**Frame the decision as an open choice.** Write it as "Decide which of A, B and C comes first toward <goal>". Build the options so that at least two of them are not the hypothesis, and add a fourth when the CEO's message names one. Sort them alphabetically by their wording and label them in that order, so the hypothesis lands wherever the alphabet puts it. Fix the labels before any memo arrives. Record in the hypothesis file which label is the hypothesis. A short question with no hypothesis takes the same form.

From here on, every surface an agent sees refers to plans by label only. That covers memos, callbacks, the secretary's input and the minutes. Only the hypothesis file maps a label to the CEO's preference.

**Load the brief** from `~/.config/board/brief.md`. If it is missing, create `~/.config/board/` and copy [templates/brief.md](templates/brief.md) there. If any of these four fields is blank, ask the CEO for just the blank ones and fill them in.

1. Capital at risk: the amount the CEO can lose without changing their life.
2. Hours per week the CEO can give the venture.
3. The goal, as an outcome with a horizon.
4. Hard constraints, such as a day job, a jurisdiction or a household need.

Record a field the CEO declines as "not given", and continue. The Goal must name an outcome, not a means. When the CEO states a plan as the goal, such as "build a trading bot", move that plan into the hypothesis file and ask what outcome it serves.

**Load past decisions.** Every minutes file in `~/.config/board/minutes/` ends with a `## Decision` section naming a decision and its status: adopted, rejected or deferred. Read that section from every file, and read in full the three most recent minutes plus any whose title touches this decision. For each past decision still marked deferred, ask the CEO whether it was settled, and update that file and the matching seat records. When an option brings back a plan the CEO rejected, tell the seats so, and require any memo that backs it to name the evidence that is new since the rejection.

If the decision concerns a repository, note its absolute path for the seats to read. Otherwise pass none.

### 2. Seat the board

Pick the four to six seats the decision needs. board-independent sits every time. Read the record of each seat that sits from `~/.config/board/memory/<seat>.md`, or note that it has none yet.

Typical sittings, as a starting point rather than a rule:

- What to build or do first: CFO, Risk, Scientist, CTO, Strategist, Independent.
- Going live with real money: Risk, CTO, COO, CISO, Independent.
- Structure, entity or tax: Counsel, CFO, Risk, Independent.
- Whether to keep a strategy or kill it: Scientist, Strategist, CFO, Independent.

When the CEO asked for the board or used the slash command, state in one line the decision with its options and the seats that sit, then continue. When the skill started on its own, state that same line and ask once whether to convene. Launch nothing until the CEO says yes.

### 3. Blind round

Launch every seated agent in one message, so they run in parallel and in the background. Each prompt carries these five things.

1. The decision, with its labelled options.
2. The full text of the brief.
3. The past decisions and relevant minutes, each without its `## Verdicts` section, or a line saying there are none.
4. The repository path, when the decision concerns one.
5. The seat's record from `~/.config/board/memory/<seat>.md`, or a line saying it has none.

No prompt says which option the CEO favors. A seat that reads "I think X is right" anchors on X, and the blind round exists to find out what each seat says without that anchor. The past minutes go in without their verdicts because those show which option the CEO favored in earlier sittings. Each seat replies with a memo of about 300 words, in the eight parts its charter lists: first move by option label, reasoning, failure, pre-mortem, base rate, what would change its mind, questions for the CEO, and confidence. Every factual claim in it is tagged VERIFIED with a source, or ASSUMED.

Wait for every notification before reading the memos together. Do not predict a memo that has not arrived. A seat that fails, returns nothing, or returns more than twice its word limit is recorded as "no memo". Relaunch it once only if the cap still leaves room after the secretary and the callbacks step 4 will need. Otherwise the sitting continues without it.

When there is a hypothesis, score each memo against it as the seat's blind verdict. It agrees when its first move is the hypothesis's label, disagrees when it puts another option first, and is conditional when it accepts the hypothesis only after a precondition. When there is no hypothesis, skip this scoring.

### 4. Cross-examination on a split, or a rival plan on agreement

Group the memos by the option they put first. A new option that only rewords a listed one belongs to that option. A split means at least two positions.

**On a split,** call back the seats on each side plus board-independent. Each prompt carries the decision, the brief, the seat's own memo and every other memo, and names one option to judge. With a hypothesis, the prompt says "the CEO favors option B", using its label, and that sentence appears nowhere else in the sitting. With no hypothesis, the prompt names the option the most seats chose, with ties broken by label order. Each seat replies with a rebuttal, its own blind verdict and its final verdict on that option, and a Change line giving the reason for any difference. A verdict may move only on a new fact or a flaw in the seat's own memo. Headcount and confidence are not reasons.

The callbacks get whatever runs remain after the blind round and the reserved secretary run. When more seats hold a position than there are callbacks, board-independent takes one. Then one seat from each position takes the rest, starting with the position held by the most seats. Break a tie between positions by option label order, and pick the seat within a position by its order in the seat table. A position whose only holder is board-independent is already covered.

**On agreement,** do not end the sitting. A unanimous blind round from agents on one model shares one set of blind spots. Call back board-independent alone, with every memo, and name the option to judge in the same way. It replies in about 300 words with four parts: a rival first move, what the consensus missed, how likely the rival is to win, and a verdict on the named option.

Continue a seat's blind-round agent with SendMessage when that tool is available, or launch the seat again with its own memo in the prompt.

A seat's final verdict is its own final verdict when it was called back, and the chair's blind score otherwise.

### 5. Fact check

Check claims against a primary source with WebSearch or WebFetch before the CEO sees them, and prefer the regulator's, tax authority's or vendor's own page. Spend at most about ten lookups, in this order.

1. Every base rate a memo cites.
2. Every claim tagged ASSUMED that an argument rests on, such as a regulatory threshold, a tax rule, a fee or a deadline.
3. Any claim tagged VERIFIED whose source looks weak or secondhand.

Anything left when the lookups run out stays ASSUMED. Never put a figure from the brief into a search query or a URL. Record each result. A claim that turns out false is struck, and the result names the seat whose argument it weakens.

### 6. Blind draft of the synthesis

Launch `l3a0:board-secretary` with these six things.

1. The decision, with its labelled options.
2. The brief.
3. The past decisions.
4. Every blind memo, with "no memo" for a seat that failed.
5. Any rebuttals or rival plan, without their verdict lines.
6. The fact-check results.

The secretary weighs each split by the argument on each side and never by how many seats hold it. It returns the agreements, the splits with their deciding metrics, the rival plan when there is one, the questions only the CEO can answer, and a recommended decision with its first three actions, or no recommendation when the split is too close to call. The chair does not rewrite that draft. The draft exists because a writer who knows which answer the reader wants bends toward it.

### 7. Verdict, minutes and records

Compare the secretary's draft against the hypothesis file, then wrap the draft in the minutes below and show them to the CEO. The verdict count describes the board. It does not decide a split, and the recommended decision stays the secretary's.

```markdown
# Board sitting: <the decision>

Date: YYYY-MM-DD. Seated: <seats>.

## Options

- A: <wording>
- B: <wording>
- C: <wording>

## Verdicts

Count: agree N, conditional N, disagree N, by final verdict on the judged option. Or "No hypothesis: verdicts not scored."
Draft against hypothesis: <the draft recommends the judged option, another option, or none>.

| Seat | Blind verdict | Final verdict | Change |
| --- | --- | --- | --- |
| <seat> | <agree, conditional or disagree> | <same or new> | <None, a new fact, a flaw in own memo, or NO REASON GIVEN> |

<The secretary's draft, as written.>

## Facts checked

- <Claim>: <source and date checked>, struck, or still ASSUMED.

## Memos

<Each seat's memo, rebuttal or rival plan, as written, or "no memo". Leave out the verdict lines of rebuttals and the rival plan, since the table above holds them.>

## Decision

Decision: <the recommended decision, or "None recommended. Open: <the split>.">
Status: deferred.
Evidence that would reopen it: <for a rejected plan, what new evidence would justify bringing it back>.
```

For a seat that was called back, both verdicts in its row are the seat's own labels. Write "NO REASON GIVEN" only when those two labels differ and its Change line is "None". Such a change is a sign of drift toward the majority, and the CEO should read that seat's blind memo rather than its rebuttal. For a seat that was not called back, the row shows the chair's blind score twice. When there is no hypothesis, the count reads "No hypothesis: verdicts not scored", the draft line reads "none stated", and the table lists only the seats called back, with their verdicts on the option most seats chose.

Save the minutes to `~/.config/board/minutes/YYYY-MM-DD-<slug>.md` only after every agent in the sitting has finished. Then do three more things.

1. Append one entry to the record of each seat that sat, in the shape under "What the directors remember".
2. Append the draft's questions for the CEO to the Open questions section of the brief.
3. When the CEO adopts or rejects the decision later in the conversation, update the `## Decision` section and the Outcome line of every seat record from this sitting.

## Why the procedure looks like this

Each rule above answers a failure that research or practice has named. Keep these in mind before removing one.

- **Verdicts change only for a reason, splits are weighed by argument, and the count stays beside it.** Same-model agents adopted the majority answer up to 85.5% of the time, and plurality voting discarded correct answers already in the pool. That study used 7 to 8B models without structured roles. Bertalanič and Fortuna, "The Cost of Consensus", CAIS 2026. Agents often dropped correct answers to agree with peers. Wynn, Satija and Hadfield, arXiv 2509.05396. Choi, Zhu and Li, arXiv 2508.17536, found the reverse on voting. Majority voting carried most of the gain, and debate alone did not raise expected correctness. That is why the chair keeps the verdict count beside the argument.
- **No agent learns the CEO's preference before cross-examination, and the secretary never does.** Assistants bend toward a view the user stated. Sharma et al., "Towards Understanding Sycophancy in Language Models", arXiv 2310.13548.
- **Every memo carries a pre-mortem.** Klein, "Performing a Project Premortem", Harvard Business Review, 2007.
- **Every memo names a base rate, and the fact check starts there.** The Mediating Assessments Protocol in Kahneman, Sibony and Sunstein, *Noise*, 2021. The book asserts its benefit rather than measuring it.
- **A unanimous round calls the independent director for a rival plan.** Schweiger, Sandberg and Rechner, 1989, found a rival plan beat consensus, though no better than devil's advocacy.
- **The independent director reports what it believes, not assigned dissent.** Nemeth, Brown and Rogers, 2001, found assigned devil's advocacy weaker than authentic dissent. A seat told always to disagree runs that risk, so its charter asks for what it believes and lets it say the plan held up.
- **Claims are tagged VERIFIED or ASSUMED, and decisions carry forward with a status.** The board-meeting skill in alirezarezvani/claude-skills at commit `aecfb8e`, which asserts the practice rather than measuring it.
