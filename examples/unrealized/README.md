# Unrealized gains

What every holding is worth now against what it cost — per holding, per
account, and merged across the taxable accounts:

```sh
bazel run //examples/unrealized
bazel run //examples/unrealized -- --account ACCOUNT_NUMBER
```

The web app shows the same report on the **Performance** tab, under
**Unrealized**.

```text
◆ UNREALIZED — Individual · Demo Brokerage · DEMO-TAXABLE
SYMBOL        QUANTITY       PRICE          VALUE     COST BASIS           GAIN   RETURN
BND                150      $72.85     $10,927.50     $11,415.00       -$487.50    -4.3%
VTI                300     $285.50     $85,650.00     $63,720.00     $21,930.00   +34.4%
TOTAL                              $96,577.50     $75,135.00     $21,442.50   +28.5%
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

Equities only: options and crypto positions are not included. Holding periods
are not considered, so unrealized gains are not split short- and long-term.

## Layout

| Path | What it is |
| --- | --- |
| `core.py` | Gains, totals, and merging across accounts; pure, no network |
| `report.py` | Fetches positions, quotes, and lots and builds the report |
| `main.py` | The command-line tables |
