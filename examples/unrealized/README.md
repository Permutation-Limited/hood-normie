# Unrealized gains

What every holding is worth now against what it cost — per holding, per
account, and merged across the taxable accounts:

```sh
bazel run //examples/unrealized
bazel run //examples/unrealized -- --account ACCOUNT_NUMBER
bazel run //examples/unrealized -- --lots
```

The web app shows the same report on the **Performance** tab, under
**Unrealized**.

```text
◆ UNREALIZED — Individual · Demo Brokerage · DEMO-TAXABLE
SYMBOL        QUANTITY       PRICE          VALUE     COST BASIS           GAIN   RETURN    SHORT-TERM     LONG-TERM
BND                150      $72.85     $10,927.50     $11,415.00       -$487.50    -4.3%      -$162.50      -$325.00
VTI                300     $285.50     $85,650.00     $63,720.00     $21,930.00   +34.4%     $7,310.00    $14,620.00
TOTAL                              $96,577.50     $75,135.00     $21,442.50   +28.5%     $7,147.50    $14,295.00
```

With `--lots`, each holding's open lots are listed beneath it, oldest first,
with the date each short-term lot goes long-term:

```text
VTI                300     $285.50     $85,650.00     $63,720.00     $21,930.00   +34.4%     $7,310.00    $14,620.00
  2023-05-14 LONG              200      $57,100.00     $42,480.00     $14,620.00
  2026-06-10 SHORT             100      $28,550.00     $21,240.00      $7,310.00  long-term 2027-06-11
```

Retirement accounts are listed but left out of the combined total: their gains
are not taxed when realized. The combined section appears when more than one
taxable account is read.

## Where the numbers come from

- **Price**: `get_equity_quotes`, one request covering every account, so a
  symbol held in two accounts is marked at the same price in both.
- **Cost basis**: the sum of `tax_cost_basis` over the position's open lots
  from `get_equity_tax_lots`. That is the basis Robinhood reports on a 1099-B,
  so it includes adjustments a plain average cost does not — a wash sale's
  disallowed loss, for one, is added to the replacement shares' basis.
- **Fallback**: when a lot's basis is still pending (a purchase that has not
  synced yet) or the lots do not cover the position, the position's
  `average_buy_price` stands in, and the row says so (`average cost` in the CLI,
  an asterisk on the web).

## Short- and long-term

Each lot carries Robinhood's own `term`, and a holding's gain is split by its
lots: each lot is marked at the holding's price, and any cent of rounding
between the lots and the holding goes to the larger part, so the two columns
always add up to the gain. A holding whose basis fell back to average cost has
no lots to split by, so its gain is reported as unknown-term and the total says
how much that is.

`term` is used as given rather than recomputed from the purchase date, because
it is the more accurate of the two: a wash sale's replacement shares inherit
the holding period of the shares sold, and Robinhood reflects that in `term`
while keeping the purchase date as `open_date`. The "goes long-term" date is
counted from the purchase date, so such a lot may get there sooner.

Equities only: options and crypto positions are not included.

## Layout

| Path | What it is |
| --- | --- |
| `core.py` | Gains, totals, and merging across accounts; pure, no network |
| `report.py` | Fetches positions, quotes, and lots and builds the report |
| `main.py` | The command-line tables |
