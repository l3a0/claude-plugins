#!/usr/bin/env python3
"""Print the latest fills from a saved SnapTrade executed-orders result.

Usage: python3 -I latest_fills.py <saved file> [--since YYYY-MM-DD] [--limit N]

`snaptrade_get_orders` with status `executed` returns an account's whole
history, which is too long to read in a session and so lands in a file. That
file holds either the orders object itself or a wrapper whose `result` field
holds it as a string. This prints one line per fill, newest first, with its
date, action, quantity, symbol and price, and says how many orders the file
held, so a reader knows the list is a slice of all of them.
"""

import argparse
import json
import sys


def orders_in(path):
    with open(path) as f:
        data = json.load(f)
    if isinstance(data, dict) and isinstance(data.get("result"), str):
        data = json.loads(data["result"])
    if not isinstance(data, dict) or not isinstance(data.get("orders"), list):
        sys.exit("the file holds no orders list")
    return data["orders"]


def symbol_of(order):
    option = order.get("option_symbol")
    if isinstance(option, dict) and option.get("ticker"):
        return option["ticker"]
    stock = order.get("universal_symbol")
    if isinstance(stock, dict) and stock.get("symbol"):
        return stock["symbol"]
    return "?"


def quantity_of(order):
    raw = order.get("filled_quantity") or order.get("total_quantity") or "?"
    try:
        return f"{float(raw):g}"
    except ValueError:
        return str(raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("path")
    parser.add_argument("--since", help="keep fills on or after this date, YYYY-MM-DD")
    parser.add_argument("--limit", type=int, default=25)
    args = parser.parse_args()

    orders = orders_in(args.path)
    fills = sorted(orders, key=lambda o: o.get("time_executed") or "", reverse=True)
    if args.since:
        fills = [o for o in fills if (o.get("time_executed") or "")[:10] >= args.since]
    shown = fills[: args.limit]
    print(f"{len(orders)} orders in the file, {len(fills)} kept, {len(shown)} shown, newest first")
    for o in shown:
        price = o.get("execution_price")
        price = f"{float(price):g}" if price not in (None, "") else "?"
        print(
            f"{(o.get('time_executed') or '?')[:10]}  {o.get('action', '?'):<10}"
            f" {quantity_of(o):>10}  {symbol_of(o):<22} at {price}"
        )


if __name__ == "__main__":
    main()
