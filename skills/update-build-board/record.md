# What goes wrong on the board's page, from the record

This file belongs to the `update-build-board` skill. Every defect below shipped on l3a0/quantitative-trading's page, or was caught there at the last moment, and the shared page in l3a0/repo-template descends from that page with each fix carried over. The function names are the page's own, so a defect found on either page is read against the same code. They are written down because the next one will be a variant rather than something new.

## The defects

1. **A sentence outliving its data.** A hardcoded "everything in the third column
   waits on the same two issues" survived the column emptying. Compute the
   sentence from the array, including the branch where the array is empty.
2. **A fixed list of reasons.** The note offered three reasons a card might not
   be free, for one card that was simply deferred. Build the list from the cards
   actually present.
3. **Hardcoded indices.** The in-flight note read positions three and two, so
   reversing the columns silently swapped what it said. Walk the columns.
4. **Counting something twice.** A card carrying an open pull request was listed
   as free to pick up, two sentences before the page said nobody should start
   it. Subtract everything already carried, not only the case you remembered.
5. **Two sorts that agree today.** The grid sorted by issue number while the
   ranking sorted by a measured argument, so the page put [issue 2](https://github.com/l3a0/quantitative-trading/issues/2) ahead of
   [issue 41](https://github.com/l3a0/quantitative-trading/issues/41) in one place and behind it in another. There is now one `cardOrder`
   comparator, and every column that draws cards calls it. Keep it that way.
   The ranking section itself is gone, which is defect 9.
6. **A legend describing cards that are not under it.** It began as a fixed list
   advertising states that had moved to another section. Computing it was not
   enough either: after defect 11 landed, the in-flight legend still offered
   "ready to hand to a builder" for a card whose pull request had retired that
   marker.

   The first correction was wrong and is worth recording as wrong, because it
   nearly became a rule. It said a legend reads the render rather than the data,
   which implies the render outranks the data. It does not. The data is the
   source of truth and the marker is a function of the data plus one suppression
   rule, and the defect was that the rule existed in two places. There is now one
   `planMarker` that both the card and the legend call. **A legend calls whatever
   decides the marker, never a second copy of the rule.** That is defect 5 in a
   second place rather than a new kind of failure.

   The inverse shipped too, and it is one rule read the other way. The in-flight
   legend explained a plan marker and a pull request while saying nothing about
   the session marker, which every card in that render was drawing. A legend accounts
   for each marker its own cards drew, and for no marker they did not.
7. **Declaration order.** `planOf` was read by a sort that ran before its
   declaration, which throws on load rather than degrading quietly. The stub
   catches this immediately.
8. **Pluralisation.** `plu` appended a bare letter s, giving a count of passes
   that read "19 passs". It now handles a word already ending in one.

The rows from here on, apart from 13 and 14, were each caught by the owner
reading the published page rather than by a check. That is what they have in
common. Most had been on the page for a while, and two were made and found
inside one session, kept anyway because what produced each was two rules
meeting rather than one careless edit. They are the failures this page invites
and the ones a harness cannot see.

9. **A second list of the same cards.** The page carried a ranking section
   listing nine cards the build order already drew, so every card had two homes.
   The one recorded consequence is defect 5, where the two sections ordered one
   pair differently. The section is gone and its order drives the grid instead.
   Do not add a list that restates the cards.
10. **Reasoning duplicated onto a card that links to the issue holding it.**
    When the ranking section went, its argument for each position was moved onto
    the cards, and the longest one rendered several times the height of its
    neighbours for text that was already one click away. The argument belongs on
    the issue, and the card carries the position as a number.
11. **A plan line under work already under way.** A card with an open branch
    said its plan was ready to be written, directly above a line saying it was
    written. The owner later made the same call about a build session, which is
    the same handover before a branch exists, so the marker now goes for either.
    The sort still reads `PLANNED`, so the card keeps its position whether or not
    the marker is drawn.

    The suppression is two measured states rather than a licence to hide
    others, and the original wording of this row said so before the second state
    was added. The principle that looks like it generates them, whether the card
    can still be handed to a builder, reaches further than the evidence does. It
    covers a decompose loop as well, which keeps its marker because it revises
    the plan rather than carrying it out. A rule needing an exception written in
    by hand to reach the two known cases is doing more than the evidence asks.
    That carve-out is why `WORKING` carries `kind`.

    A suppression rule is also a second consumer of the field, so it goes in one
    function every reader calls rather than being written out wherever it is
    needed. Writing it twice is what made the legend wrong, which is the second
    half of defect 6.
12. **Two fixes that each worked, contradicting each other.** A priority chip
    was added to the cards when the ranking section was deleted, and separately
    the sort was changed to force a deferred card last because one had been
    sitting fourth in a column of twenty-five. Together they gave [issue 10](https://github.com/l3a0/quantitative-trading/issues/10) a
    chip reading 6 above a position reading last, which is two answers to one
    question. The chip is dropped on a deferred card, because the ranking holds
    one only to record that it is deliberately not being done, and the dashed
    border and the kind word already say that. The shape is not rare: the card
    renderer carries two other comments reasoning about giving one card two
    answers to one question. Check 6 in page.md is what catches the next one, so a
    rule added to a card is read against the card's own position rather than
    only against the data it came from.

Defects 13 and 14 are a third kind. Both were made and caught inside one session
rather than by the owner reading the page. Defect 14 came from the harness
output. Defect 13 could not, for the reason it records, and came from reading
the script beside it. Each row after them says how it was found.

13. **Bindings left behind when the sentence they fed moved.** The board note
    once described the cards a session was on. That sentence moved to the
    in-flight note, and nine bindings that computed it stayed, one of them
    building the whole paragraph and assigning it to a variable nothing reads.
    The harness cannot see this, because it prints what the page rendered and
    dead code renders nothing. So when a sentence is deleted or moved, grep the
    script for the names that fed it. A leftover here costs more than ordinary
    dead code, because it is not inert. It is a finished sentence about live
    data, sitting beside a surface that would print it, under a rule that has
    since changed.
14. **A set of alternatives joined with "and".** The board note lists the reasons
    a first-column card is not free, and `andlist` joined them, so it read that a
    card can need a decision rather than a session and be deferred on purpose.
    The reasons are collected from different cards, which is what defect 2 is
    about, so joining them with "and" hands all of them to one card. The join
    now takes its conjunction as an argument, and
    `andlist` and `orlist` are two names for it. Check 5 in page.md used to look only for a
    conjunction whose other half had dropped out. This one had its other half
    and was the wrong word, so that check now covers both.

15. **A column test reading half of what its heading claims.** Caught by the
    owner reading the page. "Waiting on your review" asked only whether a review
    had been posted, so a branch with two
    checks still running sat under a heading saying the next move was the
    owner's. `CLAUDE.md` is explicit that a pull request is not handed over until
    its checks have settled, so the heading was making a promise the test did not
    check, and the page invited a merge of a branch that could still go red.

    The first attempt was worse than the defect. It kept the card in the owner's
    column and added a clause to the note saying its checks had not settled,
    which is the note working around a wrong test rather than the test being
    fixed, and it put the rule in a second place. That is defect 5 again. One
    `handedOver` came to decide it, the card stayed on the reviewer's side until
    both halves were done, and the note went back to one sentence. Defect 17
    later added a third condition.

    Three states stay on the reviewer's side and the third is the one to
    remember: a check still running, a check that failed, and no checks reported
    at all. A conflicting pull request gets no run created, so an empty rollup is
    a branch nothing built rather than a branch with nothing wrong.
16. **A heading that named one kind of session for two.** Found while publishing
    the fix above, which is the only reason it was not shipped. Adding decompose
    loops to `WORKING` put five cards under a column reading "Building", which is
    what a loop is not. A loop ends in a sharper plan and a builder ends in a branch,
    so they are different states and now have different columns. `kind` was
    already the field that told them apart, and the column test reads it.
17. **A column test that could not see the session still working.** Caught by
    the owner, after a session had recommended a merge from the column. On
    2026-10-05
    [issue 340](https://github.com/l3a0/quantitative-trading/issues/340) sat
    under "Waiting on your review". Its
    [pull request 383](https://github.com/l3a0/quantitative-trading/pull/383)
    had a review comment posted at 05:02Z and six green checks at `81b4e28`, so
    both halves defect 15 asks for were done. Its session was not. At 05:15Z it
    pushed a merge of `main`, moving the head to `125b5a6`, and it was then
    rewriting the post, the README and Entry 21. `handedOver` read the review
    and the checks and nothing about the session. The page's own comment said
    an entry owes its removal when its pull request opens, so the card carried
    no `WORKING` entry and no signal was left to read.

    This is defect 15 on the other half of the same heading. That one read a
    review and not the checks, and this one read both and not the session. The
    fix reuses `WORKING` rather than adding a field. A build session's entry
    now stays until it hands the pull request over, and comes out at the
    hand-over. Since
    [issue 533](https://github.com/l3a0/quantitative-trading/issues/533) the
    entry is a `working:build` label. The page's `owed` returns the first
    thing a branch still owes, which is a review, its session or its
    checks. The column test and the flow note both call it, so the reason a
    card gives for sitting on the reviewer's side is the rule that put it
    there, which is defect 5's lesson.

    The price is a card left under "Waiting on my review" when its session
    ends without taking its entry out. That fails safe, because it delays a
    merge rather than inviting one too early.
18. **A merged pull request read as a branch.** Found on 2026-10-10 by reading
    the Show all view.
    [Issue 431](https://github.com/l3a0/quantitative-trading/issues/431) and
    [issue 432](https://github.com/l3a0/quantitative-trading/issues/432) each
    had a pull request merged as `Part of`, with the issue left open for a link
    and a reference. The board note left both out of the free list and gave
    as its reason that a card can "already be written and waiting on a review",
    which neither was. The note asked whether `PRS` held any entry for the
    card, while the In flight section asked whether it held an open one, so
    the two sections disagreed about one card. That is defect 5 again. The same
    bare test also hid the plan marker, the kind word and the accent border on
    such a card, and put "a pull request carries it" in the legend. One
    function, `openBranches`, now answers the question for every reader.

    Freeing every merged entry would have gone past the defect. A pull request
    merged with no `Part of` was meant to close its issue, so the owner ruled
    on 2026-10-10 that its card is held back as needing only closing by hand,
    and `closesByHand` decides that for the free list, the plan marker, the
    kind word, the "Planned, no builder" column and the chain bar. The same
    reading found a closed entry's line repeating its old review text and,
    with no closing link, saying what merging would do. It now says closed.
19. **One sentence carrying two facts.** Caught by the owner reading the
    published page. On 2026-10-11
    [issue 303](https://github.com/l3a0/quantitative-trading/issues/303)
    gained `needs` of 249 and 510, both open and neither waiting on anything.
    The board note's branch for a graph with no third column was fixed text
    saying nothing sat "behind more than one thing", which meant no chain ran
    two steps and read as no card waiting on two issues. The second column's
    subtitle, "one thing has to land first", made the same claim about the card
    under it. That is defect 1 surviving inside a computed sentence, because
    only its other branch read the data. The deep branch had its own version,
    calling two steps "the deepest the graph goes" without measuring it.

    The note now reads the longest chain from the depth map, names any card
    waiting on several open issues in a clause of its own, and says nothing
    about depth when no card waits on anything. The columns are headed by steps
    along a chain rather than by things to land, and the note counts in the
    same steps. The review of that fix found the class in two more places. The
    shallow branch never said when it was counting cards the short view hid,
    which the deep branch already did. The chain bar said "waits on 2" for a
    card whose own line named one issue, because it counted the whole chain.
    So when a phrase can be read as either of two quantities, check it against
    data where the two differ.
20. **A free claim that read only the links.** Caught by the completeness lens
    of the review of
    [pull request 518](https://github.com/l3a0/quantitative-trading/pull/518),
    and filed as
    [issue 521](https://github.com/l3a0/quantitative-trading/issues/521).
    Picking a card with no open `needs` either way gave fixed text saying it
    could be taken on its own. That read only `needs`. So the bar called a
    card free whose kind word said not to start it, or whose session or open
    branch said somebody was carrying it. The board note's free list held
    those cards back, so the bar and the note answered one question in two
    places. That is defect 5 again. A card whose `after` line tied it to
    another issue was also called linked to nothing.

    One table, `HOLDS`, now lists the reasons a card is not free, and
    `takeable` passes ordinary work that no row of it holds. The free list and
    the bar both read them. The bar names the reasons a card is held, says
    only what the links show for a card blocked on data, and names an `after`
    tie in either direction. The review of that fix found two more places the
    bar disagreed with the card. A kind reason ignored the open branch that
    hides the card's kind word, so `kindShown` now decides both. A plan whose
    one open question is the owner's was called free while the In flight note
    said it waited on the owner. A row for it now reads `planMarker`, so it
    fires only where the card draws that marker.

    The completeness lens of that review found a third place, filed as
    [issue 573](https://github.com/l3a0/quantitative-trading/issues/573). The
    In flight note's sentence for "Planned, no builder" asked only whether a
    plan waited on the owner. So a deferred, decision, parent or data card with
    a finished plan was "planned and free for anyone to pick up" there while
    the bar said it was not free to take. That sentence now reads `takeable`
    and gives the reasons `HOLDS` names, in the bar's words. No row names data,
    so a card blocked on data is told only that it is not free, as the bar
    tells it only what its links show. The column's own test
    still reads no kind, so such a card stays under that heading, and the note
    beside it is what says the card is held.
21. **Two pointers reading a list that ties at zero.** Found by the over-reach
    lens of the review of
    [pull request 518](https://github.com/l3a0/quantitative-trading/pull/518),
    and `main`'s page before that pull request did the same.
    [Issue 523](https://github.com/l3a0/quantitative-trading/issues/523)
    recorded it. `most` is the largest number of cards any one card frees, and
    `unblocks` held every card that freed that many. When nothing waits on
    anything, `most` is 0 and every card ties at it, so the list held the whole
    board. The freeing clause read `most` and said nothing was freed by landing
    anything. The two pointers after it, `flownTop` and `hiddenNamed`, took
    their cards from the list. So the note named every card in flight, and in
    the short view every hidden card, as though each one freed the most.

    That is defect 1's lesson in a list of maxima. Such a list is never empty
    while the board holds a card, so the branch to compute is the one where it
    ties at zero. `unblocks` is now empty when `most` is 0. The cards waiting
    on several open issues still feed the hidden pointer, so the guard sits on
    the list rather than on the whole pointer.

22. **Two more places deciding on their own whether a card is free.** Caught by
    the completeness lens of the review of
    [pull request 580](https://github.com/l3a0/quantitative-trading/pull/580),
    which fixed the In flight note's planned sentence under defect 20. Two
    places still read less than `takeable` does.

    1. [Issue 583](https://github.com/l3a0/quantitative-trading/issues/583)
       recorded the first. The plan marker's suffix, its label sentence and
       the legend's gloss read only `needs`. So a deferred card with a `build`
       verdict read "deferred on purpose" directly above "ready to build", and
       the legend offered it to a builder. `buildable` now asks `takeable` and
       an open `needs` together, and all three call it. When a free and a held
       card share a column, the legend sends the reader to each card's own
       line rather than giving one answer for both.
    2. [Issue 584](https://github.com/l3a0/quantitative-trading/issues/584)
       recorded the second. The "Waiting on your review" sentence was fixed
       text ending "waiting on nothing else", read beside a card whose own line
       said "waits on" an open issue. The sentence now names what the card's
       `needs` and `after` name, in the card's words.

    Both cards keep their columns. A held card with a finished plan still sits
    under "Planned, no builder", because both halves of that heading are true
    of it and the note beside it says why it is held. A reviewed, green card
    that waits on an open issue still sits under "Waiting on your review",
    because nothing is left for a session and waiting is the owner's call.

The four figures that argued for deleting the footer were a count of planned
cards, a count of finished plans, an interpolated test total that made an old
pull request look like it shipped a number it did not, and an issue count
attributed to the wrong work. They are named here because they are what a
hand-written surface costs, and because the fix was to remove the surface rather
than to keep checking it.

Most of these share one shape: a rule written in two places, which drift apart. Before adding a rule to the page, find the function that already decides it and call that.

## Offering a task per idle card was tried and withdrawn

For part of 2026-09-18 l3a0/quantitative-trading's copy of this skill told a session to offer a build task for every
card left in "Planned, no builder" and a decompose task for every card in the
Build order's first column that nothing blocked, that no session or branch
carried, and that was neither deferred nor waiting on an owner decision. The
owner withdrew both the same day. It is written down so the next session reading
an idle column does not re-invent it.

Two things went wrong, and neither depends on how large the queue is, which
matters because nobody has established that.

1. **The offer is larger than the queue.** That column held 27 such cards on
   2026-09-18, so one update offered 28 tasks, one per card plus a build task for
   the single planned card. The owner started six while the offers were still
   being made, which took those six out of the queue, and two of the rest were
   dropped to make room.
2. **A drop is not always reported.** The tool named one of the two. The other
   was visible only by diffing the pending list across two calls, and a diff
   cannot tell an eviction from a task somebody started, so the identity of the
   second is inferred rather than read.

The second is the reason to withdraw rather than to shrink the batch, and it is
a judgement rather than a measurement, because nothing here priced what a silent
drop costs a reader. The argument is that a queue looks like a list, so a reader
who takes it for one is misled by exactly the entries nobody is told about, and
that does not improve at five cards.

**Do not write a capacity into this skill**, because
[issue 117](https://github.com/l3a0/quantitative-trading/issues/117) is open
against the sentence that did. A tool result named twenty while a session
measured a first eviction at six pending, and the same session then watched
chips leave with no offer and no dismissal to explain it, so neither number is
settled and the pending list may be a window rather than the queue. That issue
says how to measure it. Until somebody does, the account above is written so it
holds at any size.

Which card is dropped is worth stating carefully, because the first draft of
this record got it wrong. The queue drops the oldest still pending, which is the
front of whatever the owner has not started, not the front of the priority
order. Offering in priority order and starting from the top leaves the
highest-ranked card the owner declined as the one at risk.

So an update reports what it found in those two states and stops. What to start,
and how many at once, is the owner's call. Their ceiling is eight running at
once, set the same day and not withdrawn, and what argued for a ceiling was
measured: three concurrent sessions produced two publish refusals inside one
board update, and each refusal cost a full read of the live page and a merge
decided part by part. Moving the data into the database on 2026-10-02 removed
that cost for data updates, so the ceiling now rests on the owner's attention
rather than on refusals. Nothing in this skill starts anything, so the number is
recorded here rather than enforced.

One fact from the withdrawn text is about the page rather than about offering,
so it stays, corrected. The "Planned, no builder" test in `FLOW` asks five
things of the state `flightCols` builds for a card.

1. `s.plan`: a `PLANNED` entry exists.
2. `!s.pr`: no open pull request carries the card.
3. `!s.busy`: no session is on it.
4. `!s.blocked`: nothing in its `needs` is still open.
5. `!s.landed`: no pull request merged against it with no `Part of`.

The withdrawn text said the test never read `needs`, so a plan-complete card
behind an open blocker would land in that column too.
[Issue 138](https://github.com/l3a0/quantitative-trading/issues/138) was the
first card to reach that state, and the fourth condition was added for it, so
such a card stays on the depth board under its own "waits on" line. The fifth
came with the owner's ruling of 2026-10-10, under defect 18, because a card
whose pull request merged with no `Part of` has no builder to wait for.
