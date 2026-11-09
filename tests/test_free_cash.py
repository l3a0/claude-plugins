#!/usr/bin/env python3
"""Tests for skills/find-free-cash/scripts/free_cash.py on hand-worked inputs.

    python3 tests/test_free_cash.py

The script's output is the cash the owner spends without margin, so a figure
that comes out too high means borrowing. Each expected value below follows
from the rules the skill states, not from the script's own printout:

- An uncovered short put holds its strike times 100.
- A credit spread holds its width times 100.
- A short is covered only by a long of the same underlying and right with the
  same or a later expiry, or a short call by 100 shares.
- The lowest of the figures is the one reported.
- A working sell order counts as filled.

Every account, balance and trade here is invented.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "skills", "find-free-cash", "scripts", "free_cash.py")


def run(data):
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "input.json")
        with open(path, "w") as f:
            f.write(data if isinstance(data, str) else json.dumps(data))
        proc = subprocess.run(
            [sys.executable, "-I", SCRIPT, path], capture_output=True, text=True, check=False
        )
    return proc.returncode, proc.stdout + proc.stderr


def account(**fields):
    data = {"cash": 100000.00, "stocks": {}, "options": {}, "open_order_reserve": 0}
    data.update(fields)
    return data


class Figures(unittest.TestCase):
    def ok(self, data):
        code, out = run(data)
        self.assertEqual(code, 0, out)
        return out

    def test_skill_example_reconciles_and_counts_at_the_limit(self):
        # The skill's opening example: $140,000 cash, one short $700 put and
        # ten $1-wide call spreads, against thinkorswim's Account Info.
        out = self.ok(
            account(
                cash=140000.00,
                stocks={"SGOV": 1000},
                options={
                    "QQQ   261120P00700000": -1,
                    "QQQ   261120C00745000": -10,
                    "QQQ   261120C00746000": 10,
                },
                tos={
                    "margin_equity": 240000.00,
                    "maintenance_requirement": 20000.00,
                    "option_buying_power": 150000.00,
                    "long_marginable_value": 100000.00,
                },
                buy={"price": 100.70, "limit": 100.74},
            )
        )
        self.assertIn("Held for short puts:   $70,000.00", out)
        self.assertIn("Held for spreads:      $1,000.00", out)
        self.assertIn("Broker cash $140,000.00 - held $71,000.00 = $69,000.00", out)
        self.assertIn("Loan value of holdings = $81,000.00", out)
        self.assertIn("option BP = $0.00", out)
        self.assertNotIn("MISMATCH", out)
        self.assertIn("Option BP $150,000.00 - loan value $81,000.00 = $69,000.00", out)
        self.assertIn("FREE CASH (lower figure, from broker cash): $69,000.00", out)
        # 685 shares at the $100.74 limit would cost $69,006.90.
        self.assertIn("At $100.74 (limit): 684 shares, $68,906.16, $93.84 left", out)
        self.assertNotIn("(price)", out)

    def test_lower_buying_power_is_reported(self):
        out = self.ok(account(cash=10000.00, broker_buying_power=9000.00))
        self.assertIn("FREE CASH (lower figure, from broker buying power): $9,000.00", out)

    def test_lower_thinkorswim_figure_is_reported(self):
        # thinkorswim implies $99,000 of cash against the broker's $100,000.
        out = self.ok(
            account(
                open_order_reserve=5000.00,
                tos={
                    "margin_equity": 99000.00,
                    "maintenance_requirement": 0,
                    "option_buying_power": 94000.00,
                    "long_marginable_value": 0,
                },
            )
        )
        self.assertIn("Broker cash $100,000.00 - held $5,000.00 = $95,000.00", out)
        self.assertIn("Option BP $94,000.00 - loan value $0.00 = $94,000.00", out)
        self.assertIn("FREE CASH (lower figure, from thinkorswim): $94,000.00", out)

    def test_reconciliation_flags_a_put_thinkorswim_does_not_hold(self):
        _, out = run(
            account(
                options={"QQQ   261120P00600000": -1},
                tos={
                    "margin_equity": 100000.00,
                    "maintenance_requirement": 0,
                    "option_buying_power": 100000.00,
                    "long_marginable_value": 0,
                },
            )
        )
        self.assertIn("option BP = $-60,000.00", out)
        self.assertIn("MISMATCH", out)

    def test_cheapest_pairing_beats_pairing_in_order(self):
        # Pairing the October short with its cheapest cover, the November 699,
        # leaves the November short uncovered and holds $70,100. The cheapest
        # assignment pairs October 700/698 and November 700/699 and holds $300.
        out = self.ok(
            account(
                options={
                    "QQQ   261016P00700000": -1,
                    "QQQ   261120P00700000": -1,
                    "QQQ   261016P00698000": 1,
                    "QQQ   261120P00699000": 1,
                }
            )
        )
        self.assertIn("Held for short puts:   $0.00", out)
        self.assertIn("Held for spreads:      $300.00", out)
        self.assertIn("FREE CASH (lower figure, from broker cash): $99,700.00", out)

    def test_call_spread_holds_its_width(self):
        out = self.ok(account(options={"QQQ   261120C00700000": -2, "QQQ   261120C00705000": 2}))
        self.assertIn("Held for spreads:      $1,000.00", out)

    def test_a_cover_the_broker_refuses_leaves_the_call_naked(self):
        for cover in (
            "SPY   261120C00600000",  # another underlying
            "QQQ   261016C00600000",  # expires before the short
            "QQQ   261120P00600000",  # a put cannot cover a call
        ):
            with self.subTest(cover=cover):
                code, out = run(account(options={"QQQ   261120C00700000": -1, cover: 1}))
                self.assertEqual(code, 1)
                self.assertIn("WARNING: uncovered short calls", out)
                self.assertNotIn("FREE CASH", out)

    def test_shares_cover_a_call_but_never_a_put(self):
        out = self.ok(
            account(
                stocks={"QQQ": 200},
                options={"QQQ   261120C00700000": -1, "QQQ   261120P00600000": -1},
            )
        )
        self.assertIn("covered by QQQ stock: $0.00", out)
        self.assertIn("Held for short puts:   $60,000.00", out)

    def test_open_orders_are_subtracted(self):
        out = self.ok(account(cash=10000.00, open_order_reserve=2500.00))
        self.assertIn("FREE CASH (lower figure, from broker cash): $7,500.00", out)

    def test_share_count_rounds_down(self):
        _, out = run(account(cash=1000.00, buy={"price": 100.01}))
        self.assertIn("At $100.01 (price): 9 shares", out)

    def test_no_share_count_when_nothing_is_free(self):
        _, out = run(
            account(cash=1000.00, options={"QQQ   261120P00600000": -1}, buy={"price": 100.00})
        )
        self.assertIn("FREE CASH (lower figure, from broker cash): $-59,000.00", out)
        self.assertNotIn("shares", out)

    def test_thinkorswim_holding_more_for_spreads_stops(self):
        # thinkorswim pairs the four calls as 700/720 and holds $2,000, while
        # the cheapest pairing holds $1,500. The put check still reads $0.00,
        # so only the impossible negative loan value shows the difference.
        code, out = run(
            account(
                options={
                    "QQQ   261120C00700000": -1,
                    "QQQ   261120C00710000": -1,
                    "QQQ   261120C00705000": 1,
                    "QQQ   261120C00720000": 1,
                },
                tos={
                    "margin_equity": 100000.00,
                    "maintenance_requirement": 2000.00,
                    "option_buying_power": 98000.00,
                    "long_marginable_value": 0,
                },
            )
        )
        self.assertNotEqual(code, 0)
        self.assertIn("STOP", out)
        self.assertNotIn("FREE CASH", out)


class WorkingOrders(unittest.TestCase):
    def test_a_working_put_sale_counts_as_filled(self):
        # A $1,000 spread now. A working sale of the long 590 put and a
        # working sale of a 650 put to open would leave two uncovered puts,
        # $125,000, which is $124,000 more than the spread.
        code, out = run(
            account(
                options={"QQQ   261120P00600000": -1, "QQQ   261120P00590000": 1},
                working_orders={
                    "options": {"QQQ   261120P00650000": -1, "QQQ   261120P00590000": -1}
                },
                buy={"price": 100.00},
            )
        )
        self.assertEqual(code, 0, out)
        self.assertIn("If no working sell order fills: $99,000.00", out)
        self.assertIn("they hold $124,000.00 more", out)
        self.assertIn(
            "FREE CASH (lower figure, from broker cash, with every working sell order filled):"
            " $-25,000.00",
            out,
        )
        self.assertNotIn("shares", out)

    def test_a_working_share_sale_that_uncovers_a_call_stops(self):
        code, out = run(
            account(
                stocks={"QQQ": 100},
                options={"QQQ   261120C00700000": -1},
                working_orders={"stocks": {"QQQ": -100}},
            )
        )
        self.assertEqual(code, 1)
        self.assertIn("uncovered short calls if every working sell order fills", out)
        self.assertNotIn("FREE CASH", out)

    def test_no_working_orders_changes_nothing(self):
        code, out = run(account(working_orders={}))
        self.assertEqual(code, 0, out)
        self.assertNotIn("working", out)
        self.assertIn("FREE CASH (lower figure, from broker cash): $100,000.00", out)


class Refusals(unittest.TestCase):
    CASES = [
        ("positions left out", {"cash": 140000.00}, "missing field"),
        ("misspelled field", {**account(), "option": {}}, "unknown field ['option']"),
        (
            "repeated ticker",
            '{"cash": 200000, "stocks": {}, "open_order_reserve": 0, "options":'
            ' {"QQQ   261120P00600000": -1, "QQQ   261120P00600000": -1}}',
            "repeated field",
        ),
        (
            "half a contract",
            account(options={"QQQ   261120P00700000": -0.5}),
            "nonzero whole number",
        ),
        ("negative shares", account(stocks={"QQQ": -100}), "shares of QQQ"),
        ("negative order reserve", account(open_order_reserve=-5000), "open_order_reserve"),
        ("no cash figure", account(cash=None), "cash must be a number"),
        ("zero price", account(buy={"price": 0}), "buy price"),
        ("partial thinkorswim", account(tos={"margin_equity": 1}), "tos is missing"),
        (
            "working buy order",
            account(working_orders={"options": {"QQQ   261120P00600000": 1}}),
            "below zero",
        ),
        (
            "working sale of shares not held",
            account(working_orders={"stocks": {"QQQ": -100}}),
            "sell more QQQ than is held",
        ),
        (
            "unknown working field",
            account(working_orders={"option": {}}),
            "working_orders holds only",
        ),
    ]

    def test_input_that_would_drop_a_hold_is_refused(self):
        for name, data, reason in self.CASES:
            with self.subTest(name):
                code, out = run(data)
                self.assertNotEqual(code, 0)
                self.assertIn(reason, out)
                self.assertNotIn("FREE CASH", out)


FILLS = os.path.join(HERE, "..", "skills", "find-free-cash", "scripts", "latest_fills.py")


class LatestFills(unittest.TestCase):
    ORDERS = {
        "orders": [
            {
                "time_executed": "2026-01-05T00:00:00Z",
                "action": "BUY",
                "filled_quantity": "10.000",
                "universal_symbol": {"symbol": "SGOV"},
                "execution_price": "100.5000",
            },
            {
                "time_executed": "2026-01-07T00:00:00Z",
                "action": "SELL_OPEN",
                "filled_quantity": "1.000",
                "option_symbol": {"ticker": "QQQ   260116P00600000"},
                "execution_price": "2.5000",
            },
            {"time_executed": None, "action": "BUY", "universal_symbol": {"symbol": "XLF"}},
        ]
    }

    def fills(self, wrap, *args):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "orders.txt")
            body = {"result": json.dumps(self.ORDERS)} if wrap else self.ORDERS
            with open(path, "w") as f:
                json.dump(body, f)
            proc = subprocess.run(
                [sys.executable, "-I", FILLS, path, *args], capture_output=True, text=True
            )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout.splitlines()

    def test_newest_first_from_the_wrapped_result(self):
        lines = self.fills(True)
        self.assertEqual(lines[0], "3 orders in the file, 3 kept, 3 shown, newest first")
        self.assertIn("2026-01-07  SELL_OPEN", lines[1])
        self.assertIn("QQQ   260116P00600000", lines[1])
        self.assertIn("at 2.5", lines[1])
        self.assertIn("2026-01-05  BUY", lines[2])
        self.assertIn("10  SGOV", lines[2])

    def test_since_keeps_the_later_fills(self):
        lines = self.fills(False, "--since", "2026-01-06")
        self.assertEqual(lines[0], "3 orders in the file, 1 kept, 1 shown, newest first")
        self.assertEqual(len(lines), 2)


if __name__ == "__main__":
    unittest.main()
