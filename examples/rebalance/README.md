# Rebalancing example

A read-only example built with `hood_normie` that retrieves Robinhood portfolios through the
official Trading MCP and prints the class-level dollar adjustments needed
to reach a configured asset-class allocation and cash target. Recommendations
are class-level dollar amounts; the tool does not choose which symbol to trade.

It **does not place orders**. Review every recommendation, margin availability,
buying power, taxes, and unsettled funds yourself.

## Allocation model

Each portfolio is computed independently: its accounts, its cash, its targets.
Nothing is netted across portfolios. Class weights sum to 1 and apply to the
invested assets of the portfolio they belong to:

```
marked equity   = marked position values + broker-reported cash
invested target = marked equity - target cash
class target    = invested target * class weight
trade amount    = class target - current class market value
```

Consequently, a `target_cash` of `-2000` intentionally targets $2,000 of margin
borrowing. Each held symbol is mapped to a class, and all positions in that class
are aggregated before calculating the recommendation.

## Configuration model

The config has exactly two top-level sections. `assets` is global: it classifies
symbols for every portfolio. `portfolios` is a list, and each entry owns its own
accounts and its own allocation policy:

```yaml
assets:
  - {symbol: VTI, class: stocks}
  - {symbol: VXUS, class: stocks}
  - {symbol: BND, class: bonds}
  - {symbol: OLD, class: legacy}
portfolios:
  - name: taxable
    robinhood_account_numbers: [ACCOUNT_ONE]
    target_cash: -2000
    minimum_trade: 5
    classes:
      - {name: stocks, weight: 0.80, target_amount: null, ignore: false}
      - {name: bonds, weight: 0.20, target_amount: null, ignore: false}
      - {name: legacy, ignore: true}
    external_accounts:
      - name: 401(k)
        cash: 500
        assets:
          - {symbol: VTI, quantity: 10}
  - name: retirement
    robinhood_account_numbers: [ACCOUNT_TWO]
    classes:
      - {name: stocks, weight: 0.60}
      - {name: bonds, weight: 0.40}
```

Each portfolio requires `name` and `classes`. `robinhood_account_numbers`,
`external_accounts`, `target_cash` (default `0`), and `minimum_trade`
(default `0`) are optional and are never inherited between portfolios — a
portfolio with no accounts of either kind simply holds nothing.

The output says how many dollars of each class to buy or sell. It deliberately
does not divide that amount among `VTI`, `VXUS`, or other symbols. Every held
equity/ETF symbol may appear in `assets`. Unmapped holdings are implicitly ignored
and produce a notice before the recommendations.

### Ignored classes

Set `ignore: true` on a class to leave its assets entirely outside allocation
calculations. Ignored and unclassified asset values are subtracted from the
allocation base and excluded from active class balances; the program assumes no
trade in them. Ignored classes and the aggregate implicit `unclassified` class
appear in the final table with a blank action, identical current and target
values, and a `$0.00` amount. Ignored classes cannot have `target_amount`. Their
assets also remain visible individually in the current-assets table.
Recommendation rows are ordered with active classes first, followed by configured
ignored classes, the implicit `unclassified` class, and finally `cash`.

The active allocation base is:

```text
marked position values + broker-reported cash - target cash
    - ignored/unclassified asset value
```

The marked position values used in this calculation are the same quantity-times-
quote values shown in the account tables. This keeps the trades self-financing
even when Robinhood's separately reported net liquidation value differs from
those quotes.

The recommendation table also contains an implicit `cash` class. Current cash is
read directly from Robinhood's `get_portfolio` `cash` field; it is not inferred
from portfolio value and positions. For this row, `BUY cash` means cash should
increase and `SELL cash` means cash should decrease; the amount is the difference
between broker-reported cash and `target_cash`. Cash is included in `--json`
output.

### Fixed dollar class targets

Set `target_amount` on a class to target an exact dollar value. It takes priority
over that class's `weight`:

```yaml
classes:
  - {name: stocks, weight: 0.80, target_amount: null}
  - {name: bonds, weight: 0.20, target_amount: 250000}
```

The program first reserves `$250,000` for bonds. It then distributes the
remaining investable value among classes whose `target_amount` is `null`, in
proportion to their weights. This preserves `target_cash` while ensuring fixed
dollar targets win over percentage targets. A percentage-only class must have a
weight; a fixed-dollar class may omit its weight entirely.

Before recommendations, human-readable output includes a current-assets table
with each symbol's mapped class, quantity, price, and market value. The heading
also shows the Robinhood account number or external account name. Each account
has its own table, while the final action table uses their combined holdings.

### Multiple portfolios

`portfolios` may hold any number of entries. Portfolio names must be unique, and
a Robinhood account number may appear in only one portfolio — sharing one would
count its holdings twice.

Because classification is global while policy is per portfolio, a portfolio need
only declare the classes it has an opinion about. Any class named in `assets` but
missing from a portfolio's `classes` gets an implicit `target_amount: 0` there:
holdings of it still count toward that portfolio's value, and the plan says to
sell them. Declare the class with `ignore: true` instead to leave it out of the
calculation entirely.

With more than one portfolio, human-readable output repeats the account tables,
composite total, and rebalance plan under a `━━ PORTFOLIO name` heading for each
one, and ends with an `◆ ALL PORTFOLIOS` grand total. `--json` emits one object
per portfolio: `[{"portfolio": name, "recommendations": [...]}]`.

Restrict a run to particular portfolios with `--portfolio NAME`, repeated for
several. Names must match the config.

### Multiple and external accounts

Put any number of brokerage numbers in a portfolio's
`robinhood_account_numbers`. On the command line, repeat `--account NUMBER` to
override that list for one run; because the override cannot say which portfolio
it belongs to, it requires a run of exactly one portfolio (use `--portfolio`
first if the config has several).

Automatic account selection — letting Robinhood pick when no number is
configured — works only for a single-portfolio config, for the same reason.

`external_accounts` contains named accounts whose positions are not retrieved
from Robinhood. Each entry requires a `name`; each asset requires `symbol` and
`quantity`. An optional `cash` field defaults to zero. The program obtains current
prices from Robinhood quotes. External asset value and cash are added to composite
marked equity, and external cash is included in composite current cash.
Symbols use the same global `assets` mapping as Robinhood holdings, and external
account names must be unique within their portfolio. Each account table shows its
cash and total value. After a portfolio's account tables, a composite portfolio
`TOTAL` shows its combined marked equity.

## Configure and run

Create a local config from the checked-in example:

```sh
cp examples/rebalance/config.example.yaml config.yaml
```

`config.yaml` is ignored by Git, while the example remains checked in as
documentation. Edit it with your actual target allocation and account numbers:

```yaml
portfolios:
  - name: taxable
    robinhood_account_numbers: [ACCOUNT_ONE, ACCOUNT_TWO]
```

Replace the placeholder account numbers under each portfolio; the snippet above
is only that fragment, not a complete config file. Delete the second example
portfolio if you only rebalance one. JSON config files are not accepted. Then
run:

```sh
bazel test //...
bazel run //examples/rebalance:rebalance
```

Every run fetches current data from Robinhood. Override the config path with
`--config PATH`. Add `--json` for machine-readable output.

Human-readable reports use color automatically when stdout is a terminal. Use
`--color=always` to preserve color through a pager, or `--color=never` (or set
the standard `NO_COLOR` environment variable) for plain text. JSON output is
never colorized.

Relative paths are resolved from the workspace directory where you invoked
`bazel run`, not from Bazel's internal runfiles directory. Absolute paths work
unchanged.

## Authenticate with Robinhood

Robinhood's endpoint uses OAuth 2.1 with browser approval. Run the authentication
helper from a desktop with a browser:

```sh
bazel run //examples:authenticate
```

The helper:

1. Discovers Robinhood's OAuth endpoints from its MCP metadata.
2. Dynamically registers this local program as a public OAuth client.
3. Opens Robinhood in your browser using PKCE protection.
4. Waits on a loopback-only callback (`127.0.0.1`) for approval.
5. Saves the access and refresh tokens to `.robinhood-mcp-token.json` with file
   mode `0600` (readable and writable only by your user).

The token file is ignored by Git. Treat it like a password: never commit, paste,
or share it. To keep it elsewhere, pass `--token-file /secure/path/token.json`
to both `//examples:authenticate` and `//examples/rebalance:rebalance`.

## Run against Robinhood MCP

After authentication:

```sh
bazel run //examples/rebalance:rebalance
```

For live requests, account selection uses repeated `--account` arguments first,
then each portfolio's `robinhood_account_numbers`, and finally — only for a
single-portfolio run with no configured numbers — automatic selection when
Robinhood returns exactly one recognizable account. Every portfolio's accounts
are fetched in one pass, so adding portfolios does not re-request shared quotes.

The rebalancer reads the saved token and refreshes it automatically when needed.
`ROBINHOOD_MCP_TOKEN` is still supported as a temporary override, but storing a
token in shell history or source-controlled files is not recommended.

The rebalancer calls only `get_accounts`, `get_portfolio`,
`get_equity_positions`, and `get_equity_quotes`. Robinhood controls OAuth token
issuance and displays the permissions for you to approve in the browser.
It reads positions before requesting quotes, so quotes include every held symbol
as well as every symbol configured in `assets`. A held symbol is never silently
dropped when its quote is missing; the run stops with an explicit error instead.

### Verbose MCP diagnostics

To inspect every MCP JSON-RPC request and complete JSON response:

```sh
bazel run //examples/rebalance:rebalance -- --verbose
```

Verbose output goes to stderr, so `--json` stdout remains machine-readable. The
program does not print the OAuth `Authorization` header or token. Robinhood's
responses can contain sensitive account numbers, balances, positions, and other
brokerage data, so review verbose output before saving or sharing it.
