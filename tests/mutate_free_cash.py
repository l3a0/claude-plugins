#!/usr/bin/env python3
"""Break the find-free-cash scripts one way at a time and check a test fails.

    python3 tests/mutate_free_cash.py <copy of the repository>

Run it on a copy, such as one made with `git archive HEAD | tar -x -C <folder>`,
because it rewrites each script in place while it runs. Each mutant is one
edit that would make a figure wrong, a refusal lapse or a printout mislead.
It prints "caught" or "SURVIVED" for each and a total. A survivor names a
behaviour that tests/test_free_cash.py does not hold.
"""

import pathlib
import subprocess
import sys

if len(sys.argv) != 2:
    sys.exit(__doc__)
repo = pathlib.Path(sys.argv[1])
FC = "skills/find-free-cash/scripts/free_cash.py"; LF = "skills/find-free-cash/scripts/latest_fills.py"
M = [
 (FC, "control", "def main(path):\n", "def main(path):\n    raise SystemExit(0)\n"),
 (FC, "max not min", "source = min(candidates", "source = max(candidates"),
 (FC, "put x1", "return round(short.strike * 100 * 100)", "return round(short.strike * 100)"),
 (FC, "call width sign", "width = cover.strike - short.strike", "width = short.strike - cover.strike"),
 (FC, "any root covers", "if cover.root != short.root:\n        return NEVER", "if False:\n        return NEVER"),
 (FC, "earlier expiry ok", "or cover.expiry < short.expiry", "or False"),
 (FC, "stock covers put", "return 0 if short.right == \"C\" else NEVER", "return 0"),
 (FC, "greedy", "assigned = hungarian(matrix)", "assigned = {i: min(range(len(r)), key=lambda j, r=r: r[j]) for i, r in enumerate(matrix)}"),
 (FC, "orders not held", "held = put_reserve + spread_req + order_reserve", "held = put_reserve + spread_req"),
 (FC, "round shares", "shares = free // px", "shares = round(free / px)"),
 (FC, "residual no puts", "residual = me - maint - put_reserve - order_reserve - obp", "residual = me - maint - order_reserve - obp"),
 (FC, "loan uses maint", "loan_value = lmv - stock_maint", "loan_value = lmv - maint"),
 (FC, "naked continues", "        # A naked call has no cash limit on its loss, so no figure is printed.\n        sys.exit(1)", "        pass"),
 (FC, "no required check", "    if missing:\n", "    if False:\n"),
 (FC, "no unknown check", "    if unknown:\n", "    if False:\n"),
 (FC, "repeats allowed", "    if repeated:\n", "    if False:\n"),
 (FC, "fraction allowed", "units == 0 or units != int(units)", "units == 0"),
 (FC, "negative reserve ok", "money(data[\"open_order_reserve\"], \"open_order_reserve\", 0)", "money(data[\"open_order_reserve\"], \"open_order_reserve\")"),
 (FC, "negative shares ok", "money(shares, f\"shares of {symbol}\", 0)", "money(shares, f\"shares of {symbol}\")"),
 (FC, "no loan stop", "if loan_value < 0:", "if False:"),
 (FC, "count at price", "label = max(buy, key=buy.get)", "label = min(buy, key=buy.get)"),
 (FC, "count when negative", "if buy and free > 0:", "if buy:"),
 (FC, "bbp ignored", "candidates[\"broker buying power\"] = bbp", "pass"),
 (FC, "tos ignored", "candidates[\"thinkorswim\"] = obp - loan_value", "candidates[\"thinkorswim\"] = 10**15"),
 (FC, "working ignored", "    if data.get(\"working_orders\"):", "    if False:"),
 (FC, "extra drops spread", "extra = f_put + f_spread - put_reserve - spread_req", "extra = f_put - put_reserve - spread_req"),
 (FC, "extra not taken", "candidates = {k: v - (0 if k in nets_working else extra)", "candidates = {k: v - 0 * (0 if k in nets_working else extra)"),
 (FC, "shares from unfilled", "shares = free // px", "shares = (free + extra) // px"),
 (FC, "working buys ok", "if units >= 0 or units != int(units):", "if units != int(units):"),
 (FC, "working zero ok", "if units >= 0 or units != int(units):", "if units > 0 or units != int(units):"),
 (FC, "working fraction ok", "if units >= 0 or units != int(units):", "if units >= 0:"),
 (FC, "working share buy ok", "            if shares >= 0:\n", "            if False:\n"),
 (FC, "oversell ok", "if data[\"stocks\"].get(symbol, 0) + shares < 0:", "if False:"),
 (FC, "working not object ok", "            if not isinstance(working.get(name, {}), dict):\n", "            if False:\n"),
 (FC, "filled skips stocks", "        stocks[symbol] = stocks.get(symbol, 0) + shares", "        pass"),
 (FC, "never nets", "if extra and residual == extra:", "if False:"),
 (FC, "always nets", "if extra and residual == extra:", "if extra:"),
 (FC, "unfilled ignores netting", "unfilled = {k: v + (extra if k in nets_working else 0)", "unfilled = {k: v + 0 * (extra if k in nets_working else 0)"),
 (LF, "control", "def main():\n", "def main():\n    raise SystemExit(0)\n"),
 (LF, "since strict", "[:10] >= args.since]", "[:10] > args.since]"),
 (LF, "limit ignored", "shown = fills[: args.limit]", "shown = fills"),
 (LF, "limit one short", "shown = fills[: args.limit]", "shown = fills[: args.limit - 1]"),
 (LF, "total first", "raw = order.get(\"filled_quantity\") or order.get(\"total_quantity\")", "raw = order.get(\"total_quantity\") or order.get(\"filled_quantity\")"),
 (LF, "raw price", "price = f\"{float(price):g}\" if", "price = str(price) if"),
 (LF, "oldest first", "reverse=True)", "reverse=False)"),
 (LF, "no unwrap", "        data = json.loads(data[\"result\"])", "        pass"),
]
caught = 0
for f, name, a, b in M:
    p = repo / f; orig = p.read_text()
    assert orig.count(a) >= 1, name
    try:
        p.write_text(orig.replace(a, b, 1))
        r = subprocess.run(["python3", "tests/test_free_cash.py"], cwd=repo, capture_output=True, text=True)
    finally:
        p.write_text(orig)
    ok = r.returncode != 0; caught += ok
    print(("caught  " if ok else "SURVIVED"), f.split("/")[-1], name)
print(f"applied {len(M)} caught {caught}")
