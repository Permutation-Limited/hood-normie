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

The web app's **Performance** tab shows the same report, from the same code,
under **Realized & income**; its **Unrealized** view is
[`examples/unrealized`](../unrealized/README.md).

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
**long-term**.

When the open lots cannot settle it, the account's whole order history is
replayed first-in-first-out. If every share of the symbol was bought and sold
in this account — what the buys and sells leave behind equals what it holds
now — the replay recovers exactly which acquisitions each sale closed, so the
sale is short- or long-term for certain, or split into both. Robinhood's gain
stays the total; each part gets the gain its own lots imply, and any
difference (fees, rounding) is shared by quantity. A position that shares
were transferred into or out of fails that check and is left alone.

Anything still unsettled is **unknown** rather than guessed. The `BASIS` column
records which case applied:

| Basis | Meaning |
| --- | --- |
| `older lot still open (FIFO)` | Inferred long-term |
| `no older open lot` | The position was closed out, or every open lot is newer |
| `oldest open lot under a year` | Could be either term |
| `order history (FIFO)` | Settled exactly by replaying the account's orders |
| `crypto or options` | Not an equity sale; no lots to consult |
| `tax lots unavailable` | Robinhood could not list lots, e.g. a delisted symbol |
| `set in config` | Settled by `holding_periods` in `income.yaml` |
| `tax-advantaged account` | Not looked up; it does not matter there |

The inference assumes FIFO. If you choose specific lots when selling, or moved
older lots into the account after the sale, check those sales by hand.

A trade counts as an equity sale only when it lines up in time with one of the
account's equity sell orders, since the trade history mixes equities, options,
and crypto under bare tickers that can collide (SUI is both a REIT and a coin).

What stays unknown is what the MCP server cannot show at all: shares that
arrived by transfer and have since been sold (their lots are closed and no buy
exists here), and crypto, whose history lists sales but not how the coins were
acquired.

**Dividends have no tool either.** Two sources fill the gap:

- *Reinvested* dividends are exact. Each DRIP purchase is an equity order whose
  dollar amount is the payment, dated the day it was placed.
- *Cash* dividends are estimated from price history. Robinhood's
  dividend-adjusted closes are the split-adjusted closes minus every later
  dividend, so the gap between the two series drops by exactly the per-share
  dividend on each ex-date. Shares entitled are the open lots acquired before
  the ex-date plus any sold on or after it. An ex-date that no DRIP purchase
  follows within 45 days is taken as paid in cash, and dated by its ex-date.

Checked against every reinvested dividend (whose amount is known exactly), the
estimate matched to the cent in 26 of 30 cases. The misses, of 1–4%, were all
positions receiving lots transferred in after the ex-date: a transferred lot
keeps its original purchase date, so it looks as if it had been there all along.
Price adjustments also cover fund capital-gain distributions and return of
capital, which are taxed differently from dividends; the tool cannot tell them
apart. The `CASH (EST.)` column shows how much of each symbol's total is
estimated.

**Qualified status is never reported**, so it comes from configuration.

## Tax treatment

Federal tax cares about two groups, not six buckets. Short-term gains and
non-qualified dividends are taxed at ordinary income rates; long-term gains and
qualified dividends at the preferential 0/15/20% rates. The closing
**TAXABLE ACCOUNTS** section groups them that way, after the Schedule D
netting that makes simple addition wrong:

- gains and losses net within each term, then across terms, and whatever is
  left keeps the character of the larger side;
- a net capital loss offsets at most $3,000 of ordinary income ($1,500
  married filing separately), and the rest carries into next year;
- dividends never absorb capital losses.

Because losses and the limit apply per return, the grouping is shown only for
the taxable accounts together, never per account.

While anything is unresolved, each group is a range: from every unknown-term
gain and unclassified dividend at ordinary rates to every one at preferential
rates. Simply leaving them out is not a possible outcome — netting lets an
unknown gain absorb a loss on the other line — so the range is the headline.
The by-period table does leave them out, in a column of their own; each
period's figure there is the change in the year-to-date one, so the four add
up to the year.

Last year's unused losses go in `capital_loss_carryover` (below); the report
prints the carryforward its own year leaves over, to copy into next year's.

Not covered: 28% collectibles (gold and silver ETFs), the 199A deduction on
REIT dividends, the 3.8% net investment income tax, and state tax, which
mostly ignores the distinction.

## Wash sales

A loss is disallowed to the extent shares of the same symbol were bought within
30 days before or after the sale, in any account, reinvested dividends
included. The report checks every taxable loss against purchases in all the
accounts it reads and lists the matches under **POSSIBLE WASH SALES**, with the
share of each loss the replacements cover. A replacement in an IRA makes that
share permanent; otherwise it moves into the new shares' basis.

These are flags, not adjustments: Robinhood's realized gain may already
account for a wash sale, and the MCP server does not say. Only identical
tickers are checked, not "substantially identical" funds, and crypto is
skipped because the rule does not currently reach it. A purchase in the
selling account shortly before the sale may be the very shares sold, so those
count only up to what the account still held afterwards. Restricting the run
with `--account` also restricts the purchases checked.

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
capital_loss_carryover:
  short_term: 0      # last year's unused losses, from Schedule D
  long_term: 1500
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
| `lots.py` | Replays order history to recover closed lots |
| `dividends.py` | Estimates cash dividends from price history |
| `treatment.py` | Groups income by tax rate after netting |
| `wash.py` | Flags possible wash sales |
| `main.py` | The command-line tables |
