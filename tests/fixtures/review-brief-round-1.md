# Review brief: settle an order, round 1

## Subject and anchors

1. **o/r PR #5**, head `aaaaaaa`, base `bbbbbbb` on `main`. Checkout: `/co` (branch `feat`). Diff: `git diff bbbbbbb aaaaaaa`.

   Changes `order_path.py` and its tests.

Review the head commit named here, not the branch tip, which may move while the round runs.

The path to an irreversible action: none in this subject.

## Facts not to re-derive

- Plain scripts CI runs as `python3 tests/<file>`.
- The owner's login is `owner`.

## Limits for every agent in the round

- Mutate only a copy taken with `git -C /co archive aaaaaaa | tar -x -C <your scratch folder>`.

## Out of scope

- Prose style beyond the clarity of the change.
- Anything the diffs do not touch, except where a change contradicts or duplicates something already there.
- o/r#10 owns the account's lease and how cancels are sent, by the owner's rulings.
- Questions waiting for the owner's ruling: none waiting, after reading o/r#10 and o/r#11.
