#!/usr/bin/env python3
"""Cash in a brokerage account that is free to spend without borrowing.

A broker's cash balance counts money already promised elsewhere. An uncovered
short put holds back its strike times 100, a credit spread holds back its width
times 100, and an open buy order holds back its cost. A margin account's
buying power also adds the loan value of marginable holdings, which is
borrowing. This script takes the positions, pairs every short option with the
long option or stock lot that covers it most cheaply, and subtracts what is
left over.

Usage: python3 -I free_cash.py input.json

Input, all money in dollars. The comments explain each field and are not
part of the JSON, so leave them out of the file:

    {
      "cash": 140000.00,                       # broker's cash balance
      "stocks": {"SGOV": 1000},                # shares held, {} for none
      "options": {                             # OCC ticker -> contracts, short < 0
        "QQQ   261120P00700000": -1,           # {} for none
        "QQQ   261120C00745000": -10,
        "QQQ   261120C00746000": 10
      },
      "open_order_reserve": 0,                 # cost of open buy orders
      "broker_buying_power": 140000.00,        # SnapTrade buying_power, optional
      "tos": {                                 # thinkorswim Account Info, optional
        "margin_equity": 240000.00,
        "maintenance_requirement": 20000.00,
        "option_buying_power": 150000.00,
        "long_marginable_value": 100000.00
      },
      "buy": {"price": 100.70, "limit": 100.74},# optional share count
      "working_orders": {                      # working sell orders, optional
        "options": {"QQQ   261120P00680000": -1},# sell to open adds a short
        "stocks": {}                           # shares a working order sells
      }
    }

The first four fields are required, because a field left out would read as
nothing held and overstate the free cash. The script stops with an error on
any of these:

- an unknown or repeated field;
- a contract count that is not a whole number;
- a negative share count or order reserve;
- a working order count of zero or above, or a working sale of more shares
  than are held;
- an uncovered short call, now or once every working sell order fills;
- a negative loan value from thinkorswim's figures.

`working_orders` holds the change each working sell order makes to the
positions if it fills, from the order's `open_quantity`. A sell to open adds
a short, written below zero, and a sell to close of a long or of shares
removes a cover, also written below zero. A working spread is written as its
short leg only, because a buy leg would let a lone buy lower the holds, so
the script holds that leg at its full strike rather than the spread's width.
The free cash is worked out as if every one of them fills, because a fill
after the owner spends the figure would otherwise borrow. A fill can only add
holds, so every order filled is the worst case. The figure with none filled
is printed beside it. When thinkorswim's gap equals exactly what the working
orders add, its Option BP already holds them, so they are not subtracted from
that figure a second time.
"""

import json
import math
import re
import sys
from dataclasses import dataclass

OCC = re.compile(r"^(\S+)\s*(\d{6})([CP])(\d{8})$")
NAKED_CALL = 10**12  # cents; a naked call has no cash bound, so it must lose
NEVER = 10**15  # cents; a pairing the broker would not allow


@dataclass(frozen=True)
class Contract:
    ticker: str
    root: str
    expiry: str  # YYMMDD sorts as a date
    right: str  # "C" or "P", or "S" for a 100-share stock lot
    strike: float


def parse(ticker):
    m = OCC.match(ticker.strip())
    if not m:
        sys.exit(f"not an OCC option ticker: {ticker!r}")
    root, expiry, right, strike = m.groups()
    return Contract(ticker.strip(), root, expiry, right, int(strike) / 1000)


def cost_cents(short, cover):
    """Cash a broker holds for `short` when `cover` (or None) is paired with it."""
    if cover is None:
        if short.right == "P":
            return round(short.strike * 100 * 100)
        return NAKED_CALL
    if cover.root != short.root:
        return NEVER
    if cover.right == "S":
        return 0 if short.right == "C" else NEVER
    if cover.right != short.right or cover.expiry < short.expiry:
        return NEVER
    if short.right == "C":
        width = cover.strike - short.strike
    else:
        width = short.strike - cover.strike
    return round(max(0.0, width) * 100 * 100)


def hungarian(cost):
    """Minimum-cost assignment of every row to a distinct column, rows <= columns."""
    n, m = len(cost), len(cost[0])
    u, v = [0] * (n + 1), [0] * (m + 1)
    p, way = [0] * (m + 1), [0] * (m + 1)
    for i in range(1, n + 1):
        p[0], j0 = i, 0
        minv, used = [math.inf] * (m + 1), [False] * (m + 1)
        while True:
            used[j0] = True
            i0, delta, j1 = p[j0], math.inf, 0
            for j in range(1, m + 1):
                if not used[j]:
                    cur = cost[i0 - 1][j - 1] - u[i0] - v[j]
                    if cur < minv[j]:
                        minv[j], way[j] = cur, j0
                    if minv[j] < delta:
                        delta, j1 = minv[j], j
            for j in range(m + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while j0:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
    return {p[j] - 1: j - 1 for j in range(1, m + 1) if p[j]}


REQUIRED = ("cash", "stocks", "options", "open_order_reserve")
OPTIONAL = ("broker_buying_power", "tos", "buy", "working_orders")
TOS_FIELDS = (
    "margin_equity",
    "maintenance_requirement",
    "option_buying_power",
    "long_marginable_value",
)


def no_repeats(pairs):
    keys = [k for k, _ in pairs]
    repeated = sorted({k for k in keys if keys.count(k) > 1})
    if repeated:
        sys.exit(f"repeated field, which would drop a position: {repeated}")
    return dict(pairs)


def money(value, name, minimum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        sys.exit(f"{name} must be a number, got {value!r}")
    if minimum is not None and value < minimum:
        sys.exit(f"{name} must be at least {minimum}, got {value!r}")
    return value


def load(path):
    """Read the input and refuse anything that would drop or shrink a hold."""
    with open(path) as f:
        data = json.load(f, object_pairs_hook=no_repeats)
    if not isinstance(data, dict):
        sys.exit("input must be a JSON object")
    missing = [k for k in REQUIRED if k not in data]
    if missing:
        sys.exit(f"missing field {missing}; write {{}} or 0 where nothing is held")
    unknown = sorted(set(data) - set(REQUIRED) - set(OPTIONAL))
    if unknown:
        sys.exit(f"unknown field {unknown}")
    money(data["cash"], "cash")
    money(data["open_order_reserve"], "open_order_reserve", 0)
    if "broker_buying_power" in data:
        money(data["broker_buying_power"], "broker_buying_power")
    for name in ("stocks", "options"):
        if not isinstance(data[name], dict):
            sys.exit(f"{name} must be an object, {{}} for none")
    for symbol, shares in data["stocks"].items():
        money(shares, f"shares of {symbol}", 0)
    for ticker, units in data["options"].items():
        money(units, f"contracts of {ticker}")
        if units == 0 or units != int(units):
            sys.exit(f"contracts of {ticker} must be a nonzero whole number, got {units!r}")
    tos = data.get("tos")
    if tos is not None:
        for name in TOS_FIELDS:
            if name not in tos:
                sys.exit(f"tos is missing {name}")
            money(tos[name], f"tos {name}")
    buy = data.get("buy")
    if buy is not None:
        for name, px in buy.items():
            if name not in ("price", "limit"):
                sys.exit(f"unknown buy field {name!r}")
            money(px, f"buy {name}", 0.01)
    working = data.get("working_orders")
    if working is not None:
        if not isinstance(working, dict) or set(working) - {"options", "stocks"}:
            sys.exit("working_orders holds only options and stocks")
        for name in ("options", "stocks"):
            if not isinstance(working.get(name, {}), dict):
                sys.exit(f"working_orders {name} must be an object")
        for ticker, units in working.get("options", {}).items():
            money(units, f"working contracts of {ticker}")
            if units >= 0 or units != int(units):
                sys.exit(
                    f"working contracts of {ticker} must be a whole number below zero,"
                    f" because only a sell order can add a hold, got {units!r}"
                )
        for symbol, shares in working.get("stocks", {}).items():
            money(shares, f"working shares of {symbol}")
            if shares >= 0:
                sys.exit(f"working shares of {symbol} must be below zero, got {shares!r}")
            if data["stocks"].get(symbol, 0) + shares < 0:
                sys.exit(f"working orders sell more {symbol} than is held")
    return data


def filled(data):
    """The positions if every working sell order fills."""
    working = data.get("working_orders", {})
    options = dict(data["options"])
    for ticker, units in working.get("options", {}).items():
        options[ticker] = options.get(ticker, 0) + units
    stocks = dict(data["stocks"])
    for symbol, shares in working.get("stocks", {}).items():
        stocks[symbol] = stocks.get(symbol, 0) + shares
    return {t: u for t, u in options.items() if u}, stocks


def holds(options, stocks):
    """Cents held for short puts and spreads, the naked calls, and one line per pairing."""
    put_reserve = spread_req = 0
    naked_calls = []
    lines = {}
    for short, cover, cents in pair(options, stocks):
        if cents >= NAKED_CALL:
            naked_calls.append(short.ticker)
            continue
        if cover is None:
            put_reserve += cents
            kind = "uncovered short put, strike x 100"
        elif cents:
            spread_req += cents
            kind = f"spread against {cover.ticker}, width x 100"
        else:
            kind = f"covered by {cover.ticker}"
        key = (short.ticker, kind)
        n, total = lines.get(key, (0, 0))
        lines[key] = (n + 1, total + cents)
    return put_reserve, spread_req, naked_calls, lines


def show(lines, naked_calls, when):
    print(f"Short options and what holds them{when}:")
    for (ticker, kind), (n, cents) in sorted(lines.items()):
        print(f"  {n:>3} x {ticker}  {kind}: ${cents / 100:,.2f}")
    if naked_calls:
        print(f"WARNING: uncovered short calls{when}, no cash figure is reliable:")
        for t in sorted(set(naked_calls)):
            print(f"  {naked_calls.count(t)} x {t}")
        # A naked call has no cash limit on its loss, so no figure is printed.
        sys.exit(1)


def pair(options, stocks):
    shorts, covers = [], []
    for ticker, units in options.items():
        c = parse(ticker)
        (shorts if units < 0 else covers).extend([c] * abs(int(units)))
    for symbol, shares in stocks.items():
        lot = Contract(f"{symbol} stock", symbol, "999999", "S", 0.0)
        covers.extend([lot] * (int(shares) // 100))
    if not shorts:
        return []
    # One column per cover, then one "uncovered" column per short.
    matrix = [
        [cost_cents(s, c) for c in covers] + [cost_cents(s, None)] * len(shorts) for s in shorts
    ]
    assigned = hungarian(matrix)
    result = []
    for row, col in sorted(assigned.items()):
        cover = covers[col] if col < len(covers) else None
        result.append((shorts[row], cover, matrix[row][col]))
    return result


def main(path):
    data = load(path)
    put_reserve, spread_req, naked_calls, lines = holds(data["options"], data["stocks"])
    show(lines, naked_calls, "")

    # What working sell orders add to the holds if every one fills.
    extra = 0
    if data.get("working_orders"):
        f_put, f_spread, f_naked, f_lines = holds(*filled(data))
        print()
        show(f_lines, f_naked, " if every working sell order fills")
        extra = f_put + f_spread - put_reserve - spread_req
        if extra < 0:
            # A fill can only add holds, so this means the input carries a
            # working buy, which load() should have refused.
            sys.exit("STOP: working orders would lower the holds, so the input is wrong")

    order_reserve = round(data["open_order_reserve"] * 100)
    held = put_reserve + spread_req + order_reserve
    print(f"\nHeld for short puts:   ${put_reserve / 100:,.2f}")
    print(f"Held for spreads:      ${spread_req / 100:,.2f}")
    print(f"Held for open orders:  ${order_reserve / 100:,.2f}")

    candidates = {}
    cash = round(data["cash"] * 100)
    candidates["broker cash"] = cash - held
    print(
        f"\nBroker cash ${cash / 100:,.2f} - held ${held / 100:,.2f} = ${(cash - held) / 100:,.2f}"
    )

    # A cash account's buying power can count a fill or a sweep that has not
    # reached the cash balance yet. Where buying power equals cash, as at
    # Schwab, it comes out higher and the lower figure below ignores it.
    if "broker_buying_power" in data:
        bbp = round(data["broker_buying_power"] * 100)
        candidates["broker buying power"] = bbp
        gap = bbp - (cash - held)
        print(f"Broker buying power ${bbp / 100:,.2f}, ${gap / 100:+,.2f} against cash - held")
        if gap and bbp < cash:
            print(
                "  GAP: look for a fill or sweep in the last two business days"
                " that explains it, and name it in the report."
            )

    # Candidates whose figure already holds what working sell orders add.
    nets_working = set()
    tos = data.get("tos")
    if tos:
        me = round(tos["margin_equity"] * 100)
        maint = round(tos["maintenance_requirement"] * 100)
        obp = round(tos["option_buying_power"] * 100)
        lmv = round(tos["long_marginable_value"] * 100)
        stock_maint = maint - spread_req
        loan_value = lmv - stock_maint
        residual = me - maint - put_reserve - order_reserve - obp
        if extra and residual == extra:
            # Option BP is net of open orders, and here a gap of exactly what
            # the working sell orders add shows it holds those too. Counting
            # them again would subtract them twice.
            print(
                "\nthinkorswim holds the working sell orders already:"
                f" ${extra / 100:,.2f}, exactly what they add if they fill."
            )
            nets_working.add("thinkorswim")
            residual = 0
        print("\nthinkorswim reconciliation:")
        share = f" ({stock_maint / lmv:.1%} of long marginable value)" if lmv else ""
        print(f"  Stock maintenance = maintenance - spreads = ${stock_maint / 100:,.2f}{share}")
        print(f"  Loan value of holdings = ${loan_value / 100:,.2f} (this is margin)")
        print(
            f"  Margin equity - maintenance - held - option BP = ${residual / 100:,.2f}"
            "  (should be $0.00)"
        )
        if residual:
            print(
                "  MISMATCH: the pairing above does not match how thinkorswim"
                " holds cash. Find the difference before trusting either figure."
            )
        # The check above sees put and order holds only. Spreads sit inside the
        # maintenance figure, so a spread thinkorswim pairs more expensively
        # than the script shows up here instead, as stock maintenance larger
        # than the stocks it is charged on.
        if loan_value < 0:
            sys.exit(
                "  STOP: stock maintenance exceeds long marginable value, so"
                " thinkorswim holds more for spreads than the pairing above."
                " Find the difference before giving a figure."
            )
        # Option buying power is already net of open orders.
        candidates["thinkorswim"] = obp - loan_value
        print(
            f"  Option BP ${obp / 100:,.2f} - loan value ${loan_value / 100:,.2f}"
            f" = ${candidates['thinkorswim'] / 100:,.2f}"
        )
        implied = me - lmv
        if implied != cash:
            print(
                f"  Cash implied by thinkorswim ${implied / 100:,.2f} differs from"
                f" broker cash by ${(cash - implied) / 100:,.2f}"
            )

    if extra:
        unfilled = {k: v + (extra if k in nets_working else 0) for k, v in candidates.items()}
        candidates = {k: v - (0 if k in nets_working else extra) for k, v in candidates.items()}
        print(
            f"\nIf no working sell order fills: ${min(unfilled.values()) / 100:,.2f}."
            f" If every one fills, they hold ${extra / 100:,.2f} more."
        )
    source = min(candidates, key=candidates.get)
    free = candidates[source]
    if extra:
        source += ", with every working sell order filled"
    print(f"\nFREE CASH (lower figure, from {source}): ${free / 100:,.2f}")

    buy = data.get("buy")
    if buy and free > 0:
        # Count at the higher price, so an order at the limit never costs
        # more than the free cash.
        label = max(buy, key=buy.get)
        px = round(buy[label] * 100)
        shares = free // px
        left = free - shares * px
        print(
            f"  At ${px / 100:,.2f} ({label}): {shares:,} shares,"
            f" ${shares * px / 100:,.2f}, ${left / 100:,.2f} left"
        )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
