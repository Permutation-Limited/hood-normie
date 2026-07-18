# rb-rebalance

A read-only Bazel/Python tool that retrieves a Robinhood portfolio through the
official Trading MCP and prints the class-level dollar adjustments needed
to reach a configured asset-class allocation and cash target. Recommendations
are class-level dollar amounts; the tool does not choose which symbol to trade.

It **does not place orders**. Review every recommendation, margin availability,
buying power, taxes, and unsettled funds yourself.

## Allocation model

Class weights sum to 1 and apply to invested assets:

```
invested target = net liquidation value - target cash
class target    = invested target * class weight
trade amount    = class target - current class market value
```

Consequently, a `target_cash` of `-2000` intentionally targets $2,000 of margin
borrowing. Each held symbol is mapped to a class, and all positions in that class
are aggregated before calculating the recommendation.

## Configuration model

`classes` defines the allocation policy. `assets` only classifies symbols:

```json
{
  "account_number": null,
  "target_cash": -2000,
  "minimum_trade": 5,
  "classes": [
    {"name": "stocks", "weight": 0.80, "target_amount": null},
    {"name": "bonds", "weight": 0.20, "target_amount": null}
  ],
  "assets": [
    {"symbol": "VTI", "class": "stocks"},
    {"symbol": "VXUS", "class": "stocks"},
    {"symbol": "BND", "class": "bonds"}
  ]
}
```

The output says how many dollars of each class to buy or sell. It deliberately
does not divide that amount among `VTI`, `VXUS`, or other symbols. Every held
equity/ETF symbol should appear in `assets`. Unmapped holdings produce a warning
before the recommendations and are excluded from current class balances. The
result therefore assumes their value will be sold or reassigned; classify them
before relying on the recommendations.

### Fixed dollar class targets

Set `target_amount` on a class to target an exact dollar value. It takes priority
over that class's `weight`:

```json
"classes": [
  {"name": "stocks", "weight": 0.80, "target_amount": null},
  {"name": "bonds", "weight": 0.20, "target_amount": 250000}
]
```

The program first reserves `$250,000` for bonds. It then distributes the
remaining investable value among classes whose `target_amount` is `null`, in
proportion to their weights. This preserves `target_cash` while ensuring fixed
dollar targets win over percentage targets. A percentage-only class must have a
weight; a fixed-dollar class may omit its weight entirely.

Before recommendations, human-readable output includes a current-assets table
with each symbol's mapped class, quantity, price, and market value. The heading
also shows the account number used for the request. If Robinhood returns no
positions, verify that `account_number` identifies the funded brokerage account
rather than an empty Agentic account.

## Run offline

Create local working files from the checked-in examples:

```sh
cp config.example.json config.json
cp snapshot.example.json snapshot.json
```

`config.json` and `snapshot.json` are ignored by Git, while the example files
remain checked in as documentation. Edit `config.json` with your actual target
allocation. You may also store the Robinhood account number in this ignored file:

```json
"account_number": "YOUR_ACCOUNT_NUMBER"
```

Replace the existing `"account_number": null` line; the snippet above is only
that one field, not a complete config file. Then run:

```sh
bazel test //...
bazel run //:rebalance
```

The default run reads `config.json` and `snapshot.json` and makes no network
requests. Override them with `--config PATH` or `--snapshot PATH`. Add `--json`
for machine-readable output.

Relative paths are resolved from the workspace directory where you invoked
`bazel run`, not from Bazel's internal runfiles directory. Absolute paths work
unchanged.

## Authenticate with Robinhood

Robinhood's endpoint uses OAuth 2.1 with browser approval. Run the authentication
helper from a desktop with a browser:

```sh
bazel run //:authenticate
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
to both `//:authenticate` and `//:rebalance`.

## Run against Robinhood MCP

After authentication:

```sh
bazel run //:rebalance -- --live
```

For live requests, account selection uses `--account` first, then
`account_number` from `config.json`, and finally automatic selection when
Robinhood returns exactly one recognizable account. This makes `--account`
useful as a one-run override without editing the config.

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
bazel run //:rebalance -- --live --verbose
```

Verbose output goes to stderr, so `--json` stdout remains machine-readable. The
program does not print the OAuth `Authorization` header or token. Robinhood's
responses can contain sensitive account numbers, balances, positions, and other
brokerage data, so review verbose output before saving or sharing it.

## Create or update `snapshot.json`

First authenticate as described above and make sure `config.json` maps every held
symbol to a class. Then fetch live positions, portfolio value,
and quotes and atomically replace the default snapshot:

```sh
bazel run //:rebalance -- \
  --live \
  --save-snapshot
```

The command both prints the current rebalance plan and writes normalized broker
data to `snapshot.json`. Subsequent `bazel run //:rebalance` invocations use that
saved data without contacting Robinhood.

To write another file, put its path after the option:

```sh
bazel run //:rebalance -- --live --save-snapshot snapshots/2026-07-18.json \
  --account 'AN_OPTIONAL_ONE_RUN_OVERRIDE'
```

Snapshot contents are account-sensitive because they include symbols, quantities,
prices, and portfolio value. Only the root-level default `snapshot.json` is
ignored automatically; add any alternate snapshot directory to `.gitignore` if
you use one. A snapshot is a point-in-time input, so refresh it before relying on
the recommendations.
