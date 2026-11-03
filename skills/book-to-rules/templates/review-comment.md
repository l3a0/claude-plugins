## Review

<!-- Template from the l3a0 book-to-rules skill: the comment format for the project pull request, which carries
     the full review and the cost. Each companion pull request gets the short form at the end. Leave out any
     section with nothing in it, except Refuted, which says "Nothing" when nothing was refuted. Delete these
     comments before posting. -->

Round {{ROUND}}, of `{{REVIEWED_SHA}}`. {{LENS_COUNT}} lenses ran blind to each other: completeness, over-reach, and through `/l3a0:ask-team` in lens mode the {{ROLES}}. {{VERIFIER_COUNT}} verifiers then tried to refute every veto and must-fix by executing, with scripts written outside the repository. `{{FIX_SHA}}` applies what survived.

### Veto, confirmed and fixed

- **{{VETO_CLAIM}} ({{ROLE}}).** What the rule allowed, and what the verifier executed to show it. Verified: the evidence. Fixed: what the rule now says.

### Must fix, confirmed and fixed

1. **{{FINDING}} ({{LENSES_THAT_RAISED_IT}}).** What was wrong, with the verifier's evidence. Fixed: what changed.

### Should fix and notes, applied

- One line per finding, naming the lens. Where a verifier downgraded a must-fix, say so and give its reason.

### Citations corrected

Every citation was rechecked with `pg.py` against the book's text. {{MISS_COUNT}} missed: list each old and new page, and each rule whose wording claimed more than its page and what it says now.

### Refuted

- Each finding a verifier refuted, and what refuted it. A refuted finding that turns on an owner decision moves to the section below.

### Yield per lens

Surviving vetoes and must-fixes, by the lens that raised them, with the overlaps counted for each lens that found them.

### For the owner

1. **{{QUESTION}}** Why it is the owner's call, and the dated line on which issue that settles it.

### Cost

At list prices, with output a lower bound, from the `loop-cost` skill:

1. Reading the book in {{PART_COUNT}} parts: at least {{READ_USD}} US dollars, {{READ_TOKENS}} tokens over {{READ_TURNS}} turns.
2. {{LENS_COUNT}} review lenses: at least {{LENS_USD}} US dollars, {{LENS_TOKENS}} tokens over {{LENS_TURNS}} turns.
3. {{VERIFIER_COUNT}} verifiers: at least {{VERIFY_USD}} US dollars, {{VERIFY_TOKENS}} tokens over {{VERIFY_TURNS}} turns.

The figures cover all three companion pull requests, {{COMPANION_PRS}} included. Cache reads made up almost all of the tokens.

<!-- Companion pull request, short form:

## Review

Round {{ROUND}}, of `{{REVIEWED_SHA}}`, shared with {{PROJECT_REPO}}#{{PROJECT_PR}}, where the full review and its cost are posted.

### Confirmed and fixed here

1. One line per finding that touched this pull request, naming the lens.

### Checks

What ran on this branch, such as `python3 scripts/gen_team.py --check` or the template's test count.
-->
