# rb-rebalance

A read-only Bazel/Python tool that retrieves a Robinhood portfolio through the
official Trading MCP and prints the dollar and fractional-share trades needed
to reach a configured stock/bond allocation and cash target.

It **does not place orders**. Review every recommendation, margin availability,
buying power, taxes, and unsettled funds yourself.

## Allocation model

Target weights sum to 1 and apply to invested assets:

```
invested target = net liquidation value - target cash
symbol target   = invested target * symbol weight
trade amount    = symbol target - current symbol market value
```

Consequently, a `target_cash` of `-2000` intentionally targets $2,000 of margin
borrowing. Bonds are represented by bond ETF symbols such as `BND`; Robinhood's
equity tools treat ETFs as equities.

## Run offline

Create local working files from the checked-in examples:

```sh
cp config.example.json config.json
cp snapshot.example.json snapshot.json
```

`config.json` and `snapshot.json` are ignored by Git, while the example files
remain checked in as documentation. Edit `config.json` with your actual target
allocation, then run:

```sh
bazel test //...
bazel run //:rebalance
```

The default run reads `config.json` and `snapshot.json` and makes no network
requests. Override them with `--config PATH` or `--snapshot PATH`. Add `--json`
for machine-readable output. Set `liquidate_unconfigured` to true only if
holdings omitted from the targets should appear as full sells.

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
bazel run //:rebalance -- --live --account 'YOUR_ACCOUNT_NUMBER'
```

The rebalancer reads the saved token and refreshes it automatically when needed.
`ROBINHOOD_MCP_TOKEN` is still supported as a temporary override, but storing a
token in shell history or source-controlled files is not recommended.

The rebalancer calls only `get_accounts`, `get_portfolio`,
`get_equity_positions`, and `get_equity_quotes`. Robinhood controls OAuth token
issuance and displays the permissions for you to approve in the browser.

## Create or update `snapshot.json`

First authenticate as described above and make sure `config.json` contains every
symbol whose current quote is needed. Then fetch live positions, portfolio value,
and quotes and atomically replace the default snapshot:

```sh
bazel run //:rebalance -- \
  --live \
  --save-snapshot \
  --account 'YOUR_ACCOUNT_NUMBER'
```

The command both prints the current rebalance plan and writes normalized broker
data to `snapshot.json`. Subsequent `bazel run //:rebalance` invocations use that
saved data without contacting Robinhood.

To write another file, put its path after the option:

```sh
bazel run //:rebalance -- --live --save-snapshot snapshots/2026-07-18.json \
  --account 'YOUR_ACCOUNT_NUMBER'
```

Snapshot contents are account-sensitive because they include symbols, quantities,
prices, and portfolio value. Only the root-level default `snapshot.json` is
ignored automatically; add any alternate snapshot directory to `.gitignore` if
you use one. A snapshot is a point-in-time input, so refresh it before relying on
the recommendations.
