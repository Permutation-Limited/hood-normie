# Realized income

One calendar year's realized gains and dividends for each Robinhood account,
sorted into the buckets an estimated tax payment needs:

- realized gains split **short-term**, **long-term**, and **unknown term**;
- dividends split **qualified**, **non-qualified**, and **unclassified**.

It computes no tax. Rates, brackets, and safe-harbor rules are left to you.

```sh
bazel run //examples/income
bazel run //examples/income -- --year 2025
bazel run //examples/income -- --account ACCOUNT_NUMBER
bazel run //examples/income -- --cumulative
```

The web app's **Income** tab shows the same report, from the same code.

```text
◆ INCOME 2026 — individual · Main · 111
REALIZED GAINS
DATE       SYMBOL        QUANTITY         GAIN  TERM    BASIS
2026-02-11 VTI                 20    $1,840.55  LONG    older lot still open (FIFO)
2026-03-04 SPAC               400     -$612.00  ?       no older open lot
DIVIDENDS (reinvested)
SYMBOL          PAID    QUALIFIED     NON-QUAL UNCLASSIFIED
VTI        $1,249.60    $1,187.12       $62.48        $0.00
SUMMARY
Short-term gains                  $0.00
Long-term gains               $1,840.55
Unknown-term gains             -$612.00
...
```

## Estimated-tax periods

Each taxable account, and the closing taxable summary, also breaks its buckets
down by the IRS's estimated-tax periods. These are not calendar quarters:

| Period | Due |
| --- | --- |
| Jan 1 – Mar 31 | Apr 15 |
| Apr 1 – May 31 | Jun 15 |
| Jun 1 – Aug 31 | Sep 15 |
| Sep 1 – Dec 31 | Jan 15 of the next year |

Due dates are nominal; one that falls on a weekend or holiday moves to the next
business day. `--cumulative` shows each row as the year to date through the
period's end (Mar 31, May 31, Aug 31, Dec 31), which is what Form 2210's
annualized income installment method (Schedule AI) asks for. The web tab has
the same switch.

A sale belongs to the period of its trade date, and a dividend to the day it
was reinvested, both in US Eastern time.

Retirement accounts (IRAs and similar) are listed with plain totals and left out
of the closing **TAXABLE ACCOUNTS** summary, since nothing in them is taxed as
it happens.

## What Robinhood reports, and what is inferred

The MCP server exposes less than a 1099 does, so each bucket says how it was
filled.

**Realized gains** come from `get_pnl_trade_history`: every closing trade with
Robinhood's own realized gain. The gain is Robinhood's figure; nothing here
recomputes cost basis.

**Holding periods are not reported.** `get_equity_tax_lots` lists only the lots
still open, so a sale's term is inferred from what it left behind. Under
first-in-first-out lot relief — Robinhood's default — everything a sale closed
was acquired no later than the oldest lot still open. If that lot was already
held more than a year on the sale date, so was everything sold, and the sale is
**long-term**. Otherwise the tool says **unknown** rather than guessing. The
`BASIS` column records which case applied:

| Basis | Meaning |
| --- | --- |
| `older lot still open (FIFO)` | Inferred long-term |
| `no older open lot` | The position was closed out, or every open lot is newer |
| `oldest open lot under a year` | Could be either term |
| `crypto or options` | Not an equity sale; no lots to consult |
| `tax lots unavailable` | Robinhood could not list lots, e.g. a delisted symbol |
| `set in config` | Settled by `holding_periods` in `income.yaml` |
| `tax-advantaged account` | Not looked up; it does not matter there |

The inference assumes FIFO. If you choose specific lots when selling, or moved
older lots into the account after the sale, check those sales by hand.

A trade counts as an equity sale only when it lines up in time with one of the
account's equity sell orders, since the trade history mixes equities, options,
and crypto under bare tickers that can collide (SUI is both a REIT and a coin).

**Dividends are visible only when reinvested.** There is no dividend tool; each
DRIP purchase is an equity order whose dollar amount is the payment. A dividend
taken as cash leaves no trace here. The date is the day the reinvestment was
placed, which may be a day off the pay date.

**Qualified status is never reported**, so it comes from configuration.

## Configuration

Optional. Copy the example to the repository root:

```sh
cp examples/income/income.example.yaml income.yaml
```

```yaml
qualified_dividends:
  VTI: 0.95          # fraction of VTI's dividends that is qualified
  BND: nonqualified  # or: qualified
holding_periods:
  OLDCO: long        # settles sales whose term is otherwise unknown
```

A symbol missing from `qualified_dividends` is reported as unclassified rather
than guessed. A fund publishes its qualified share with its year-end tax
information; bond funds and REITs are mostly non-qualified. `holding_periods`
applies to every unknown-term sale of that symbol in the year, and never
overrides an inferred term.

`income.yaml` is git-ignored. Pass another file with `--config PATH`; the web
server takes `--income-config PATH`.

## Layout

| Path | What it is |
| --- | --- |
| `core.py` | Classification, config parsing, totals; pure, no network |
| `report.py` | Fetches the records per account and builds the report |
| `main.py` | The command-line tables |
