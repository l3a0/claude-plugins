---
name: ask-board
description: Convene a board of directors on a strategic decision for a one-person venture. Separate advisor agents, each with its own objective, write blind memos, cross-examine on a split, and the main thread chairs and writes the minutes. Use when the user asks to "ask the board", "what would my board say", "convene the board", "give me board feedback on" a plan, or asks a strategic question as the CEO or sole operator of their own venture, such as "should I do X first", "what should I focus on first", or "is my plan right or wrong".
---

# Board of directors

A single answer to a strategic question blends every concern into one voice and hides where the concerns disagree. This skill splits the answer across separate agents that cannot see each other. Each one holds one objective and names what it would sacrifice for it, so the disagreement reaches the CEO as a choice with a deciding metric rather than as a hedge.

The user is the CEO: the sole operator of a venture funded with their own money and hours. The main thread is the chair and the secretary. It runs the procedure, checks facts, and writes the synthesis and the minutes. It holds the pen, not a vote, and adds no opinion of its own.

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

## Limits

The board advises on how the venture is built and run: sequencing, risk rules, process and structure. It does not recommend specific securities, position sizes or allocations. When the CEO asks for one, say so and return that decision to the CEO. The counsel seat gives no legal or tax advice. It names the rules a decision touches and says when the CEO needs a licensed professional.

The price of a sitting is between four and ten agent runs on the session's model. A question with one obvious answer does not need a board, so answer it directly and offer a sitting only if the CEO wants one.

## Where the brief and the minutes live

The brief describes the venture and the CEO's finances, hours and constraints. The minutes record each sitting. Both hold personal financial details, so both live outside every repository.

- Brief: `~/.config/board/brief.md`
- Minutes: `~/.config/board/minutes/YYYY-MM-DD-<slug>.md`

Never write either into a repository, an issue or a pull request, and never quote the brief's figures into one.

## A sitting, in six steps

1. Intake.
2. Seat the board.
3. Blind round.
4. Cross-examination, only on a split.
5. Fact check.
6. Minutes.

### 1. Intake

Rewrite the CEO's message as one decision, in the form "Decide whether to X before Y" or "Decide which of X, Y and Z comes first". Split off the CEO's own hypothesis, meaning the answer the message already leans toward, such as "I think an MVP strategy comes first". Record it word for word. It stays with the chair until cross-examination.

Load the brief from `~/.config/board/brief.md`. If it is missing, create `~/.config/board/` and copy [templates/brief.md](templates/brief.md) there. Then ask the CEO only what this sitting needs, which is at most these four, and fill them into the brief.

1. Capital at risk: the amount the CEO can lose without changing their life.
2. Hours per week the CEO can give the venture.
3. The goal, with a horizon.
4. Hard constraints, such as a day job, a jurisdiction or a household need.

Continue the sitting once those are answered. The rest of the template fills in over later sittings.

List `~/.config/board/minutes/` and read the three most recent minutes, plus any whose title touches this decision. They let the board hold the CEO to past decisions.

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
3. The relevant minutes, or a line saying there are none.
4. The repository path, when the decision concerns one.

Leave the CEO's hypothesis out of every prompt. A seat that reads "I think X is right" anchors on X, and the blind round exists to find out what each seat says without that anchor. Each seat replies with a memo of about 250 words, in the six parts its charter lists.

Wait for every notification before reading the memos together. Do not predict a memo that has not arrived.

### 4. Cross-examination, only on a split

Read each memo's first move and group the memos by what they put first. Two first moves that differ only in wording are one position. A split means at least two positions.

With no split, skip this step. The chair then scores each blind memo against the hypothesis for the verdict count: agree when its first move is the hypothesis, disagree when it puts something else ahead of it, and conditional when it accepts the hypothesis only after a precondition. Label that count as scored by the chair.

On a split, call back the seats on each side plus board-independent. Each prompt carries the decision, the brief, the CEO's hypothesis, the seat's own memo and every other memo. Each seat replies with one rebuttal and a verdict on the hypothesis: agree, conditional or disagree. Continue a seat's blind-round agent with SendMessage when that tool is available, or launch the seat again with its own memo in the prompt.

Cap a whole sitting at ten agent runs, blind round and cross-examination together, counting a continued agent as a run. When the split holds more seats than the cap leaves room for, keep board-independent and the most confident seat on each side.

### 5. Fact check

List every factual claim the recommendation rests on, such as a regulatory threshold, a tax rule, a fee or a deadline. Seats mark these with a source or with "unverified". Check each one against a primary source with WebSearch or WebFetch before the CEO sees it, and prefer the regulator's, tax authority's or vendor's own page. Mark anything that could not be checked as unverified in the synthesis. A claim that turns out false is struck, and the synthesis says which seat's argument it weakens.

### 6. Minutes and synthesis

Write the synthesis in this shape and show it to the CEO.

```markdown
# Board sitting: <the decision>

Date: YYYY-MM-DD. Seated: <seats>. Hypothesis: "<the CEO's words>".

## Verdict on the hypothesis

Agree N, conditional N, disagree N, from cross-examination or scored by the chair.

## Where the board agrees

## Where the board splits

- <Position A> against <position B>. Decided by: <the metric or fact that settles it>.

## Questions only the CEO can answer

## Recommended decision

<The decision>. First three actions:

1.
2.
3.

## Facts checked

- <Claim>: <source and date checked>, or unverified.

## Memos

<Each seat's memo and rebuttal, as written.>

## CEO's decision

Pending.
```

The recommended decision follows the board rather than the chair. Take the position most seats hold after cross-examination, carrying the conditions that conditional verdicts attached. When the board is evenly split, recommend no side. Present both positions with the metric that decides between them, and leave the choice to the CEO. Every split names its deciding metric, such as "out-of-sample Sharpe ratio after costs above the index fund's" or "hours per week the routine needs against the brief's figure", rather than a gesture at tradeoffs.

Save the minutes to `~/.config/board/minutes/YYYY-MM-DD-<slug>.md`, where the slug is three to five words of the decision in kebab case. When the CEO states a decision later in the conversation, replace "Pending." with it, so the next sitting can hold the CEO to it.
