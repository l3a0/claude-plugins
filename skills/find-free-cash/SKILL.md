---
name: find-free-cash
description: Work out how much cash in a brokerage account is free to spend without margin, after what short puts, spreads and open orders hold back, and how many shares of something it buys. Use when asked how much cash is in Schwab, Fidelity or another linked account, how many shares of SGOV or anything else the cash buys, what buying power is without margin, or to check a cash figure against a thinkorswim screenshot.
---

# Find the free cash in a brokerage account

The cash balance a broker reports is not what can be spent. Take a margin account where SnapTrade shows $140,000.00 of cash, and its "buying power" reads the same. That cash looks like 1,390 shares of SGOV at $100.70. The free cash is $69,000.00, enough for 684 shares at a $100.74 limit, because three things the balance does not show have claims on it.

1. **An uncovered short put holds back its strike times 100.** One short $700 put holds $70,000.
2. **A credit spread holds back its width times 100 per contract.** Ten call spreads $1 wide hold $1,000.
3. **A margin account's buying power adds the loan value of marginable holdings.** thinkorswim's $150,000.00 Option Buying Power includes $81,000.00 of borrowing against 1,000 shares of SGOV.

A short call covered by a long call with the same or a lower strike and the same or a later expiry holds nothing. So does one covered by 100 shares.

The examples in this skill use invented balances and trades. The repository is public, so no figure here comes from a real account.

## Gather the account

Use the SnapTrade tools, which are read-only. Load them in one `ToolSearch` call.

1. **Ask which account is in question,** unless the request names one or asks for all of them. `snaptrade_list_accounts` names the accounts, so match the answer by the last digits in an account's name.
2. `snaptrade_get_balance` gives the cash and the broker's buying power.
3. `snaptrade_get_positions` gives the stock holdings and a current price for any of them.
4. `snaptrade_get_option_positions` gives every option as an OCC ticker with signed contracts, short below zero.
5. `snaptrade_get_orders` with status `open` gives working orders. Put the cost of open buy orders in `open_order_reserve`. Put every working sell order in `working_orders`, as the change it makes to the positions if it fills. A sale to open a put or a spread adds a short, and a sale to close a long option or shares removes a cover. The script works out the free cash as if every one fills, because a fill after the owner spends the figure would borrow. It prints the figure with none filled beside it, so name both in the report.

### Judge how fresh each account is

SnapTrade's sync time does not say how fresh the data is, so judge each account by its prices. One account's `last_successful_sync` has stayed put while its positions, cash and quotes all changed, and the same sync time on other accounts has come with data frozen overnight.

1. **Compare the quotes.** When one symbol carries different prices across accounts, compare each with the last daily close from the Massive tools. `/v2/aggs/ticker/<SYMBOL>/range/1/day/<from>/<to>` works and has no bar for the current session, while the snapshot endpoint answers 403. A price equal to the last close, on a trading day, means that account's data is frozen.
2. **Never call an intraday price wrong because it misses the daily bars.** A report once called one account's QQQ quote wrong because it sat below the last seven daily lows. It was the live price. The frozen figure was another account's quote, which equalled the previous close, so the report also misjudged how far the short options stood from their strikes. Check a doubtful quote against the account's own option prices and its fills today.
3. **Say which accounts look frozen.** A frozen account may be missing today's trades. An option still listed after its expiry is another sign. Frozen data can show a put that expired in the money on Friday as still open on Monday, before the assignment that spends its hold.
4. **Give no spendable figure for a frozen account.** A put sold today and missing from frozen data overstates free cash by its strike times 100. So report a frozen account's figure as unconfirmed until the broker's site or a thinkorswim screenshot confirms it.

Pull everything again on every run, because the owner trades between runs. Free cash can move by thousands of dollars within a day as positions open and close.

### Read the latest fills

`snaptrade_get_orders` with status `executed` returns the account's whole history, close to a million characters for an active account, so it lands in a file. `scripts/latest_fills.py` reads that file, sorts the fills on `time_executed` and prints the latest ones, with `--since` to keep only fills from a date on.

```bash
python3 -I <skill base directory>/scripts/latest_fills.py <saved file> --since <YYYY-MM-DD>
```

Those fills date any stock sale. A sale dated today settles the next business day, so a report whose cash rests on those proceeds says so.

### Read a thinkorswim screenshot

A thinkorswim screenshot of the Account Info panel, when the owner gives one, is live and is the better source. Take four fields from it.

1. Margin Equity.
2. Maintenance Requirement.
3. Option Buying Power.
4. Long Marginable Value.

Also read Money Market Balance. A nonzero balance there is cash-like but sits outside these figures, so name it separately.

## Run the calculation

Write the inputs to a JSON file in the scratchpad, in the shape the script's docstring shows. `cash`, `stocks`, `options` and `open_order_reserve` are required, with `{}` or `0` where nothing is held, because a field left out would read as nothing held. Then run `scripts/free_cash.py` from this skill's base directory with `-I`, which keeps Python from loading code from the current directory. The plugin's `tests/test_free_cash.py` pins the script's figures.

```bash
python3 -I <skill base directory>/scripts/free_cash.py <scratchpad>/find-free-cash/input.json
```

The script pairs every short option with the long option or 100-share lot that covers it most cheaply, the way a broker would, and prints what each pairing holds back. It then works out free cash up to three ways and keeps the lowest.

1. **From the broker's cash:** cash minus what short puts, spreads and open orders hold back.
2. **From the broker's buying power:** always put SnapTrade's `buying_power` in `broker_buying_power`.
3. **From thinkorswim, when given:** Option Buying Power minus the loan value of marginable holdings. The loan value is Long Marginable Value minus the stocks' share of the maintenance requirement.

### Check thinkorswim's figure

The thinkorswim check has to come out to $0.00. Margin equity minus maintenance minus what short puts and orders hold back must equal Option Buying Power. A nonzero gap means the script's put or order holds differ from thinkorswim's, so find the difference before giving a figure. The gap can be $0.00 while the cash itself differs by a few hundred dollars between SnapTrade and thinkorswim, and the script keeps the lower figure for that reason.

The check cannot see spreads, because they sit inside the maintenance figure. A spread thinkorswim pairs more expensively than the script does shows up instead as stock maintenance larger than the stocks it is charged on. The script stops when that makes the loan value negative. Short of that, compare the stock maintenance's share of Long Marginable Value, which the script prints, with the broker's house rate for those holdings.

### Explain a gap in the broker's buying power

In a cash-secured account, buying power can count a fill or a sweep that has not reached the cash balance yet. The script prints the gap between buying power and cash minus holds. Explain each gap from the fills of the last two business days before reporting, and name it. Three examples show the pattern, with invented figures.

1. **A sweep that has not reached cash.** Buying power runs $750.00 above cash minus holds. A sweep of $750.00 into FDRXX, Fidelity's money market fund, is dated that day, and the cash shows it on the next pull.
2. **A buyback the cash has not paid for.** Buying power runs $125.65 below. A buyback of 25 calls at $0.05 the day before accounts for $125.00, and the other $0.65 is probably fees. The lower figure, from buying power, is the one to report.
3. **Premium that has not settled.** Buying power runs $1,386.70 above. That matches the premium, after fees, from 20 covered calls sold at $0.70 on the previous business day. The script keeps the lower figure from cash until the premium settles, and the report names the higher one and when it arrives.

Schwab's `buying_power` in SnapTrade equals its cash and ignores what short puts hold back. It only ever comes out higher, so it checks nothing there.

### Count shares

For a share count, put the quoted price in `buy.price` and a limit price in `buy.limit`. The script counts at the higher of the two, so an order at the limit never costs more than the free cash. A limit near the 52-week high keeps the count from overshooting the cash if the price rises. Schwab sells no fractional shares of ETFs, so counts are whole shares.

## Report it

Lead with the free cash and the share count. Then list what holds cash back, one line per short put, spread and open order, and say which source the figure came from. Name anything that will change it soon, such as a short put expiring this week, which frees its hold if it expires worthless and spends it if it is assigned. Measure a short option's distance from its strike with the freshest price of the underlying across all accounts, never with the frozen account's own quote.

The script stops without a figure when it finds an uncovered short call, because a naked call has no cash limit on its loss. Say so in the report, and give no free-cash figure for that account. It also stops on input that would drop a hold, such as a missing field or half a contract, so fix the input rather than work around the error.

Never place, change or cancel an order. The owner places trades, and the ticket should show the order uses no margin before it is sent.
