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

Edit `config.example.json`, then test with the included snapshot:

```sh
bazel test //...
bazel run //:rebalance -- \
  --config "$PWD/config.example.json" \
  --snapshot "$PWD/snapshot.example.json"
```

Add `--json` for machine-readable output. Set `liquidate_unconfigured` to true
only if holdings omitted from the targets should appear as full sells.

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
bazel run //:rebalance -- \
  --config "$PWD/config.example.json" \
  --account 'YOUR_ACCOUNT_NUMBER'
```

The rebalancer reads the saved token and refreshes it automatically when needed.
`ROBINHOOD_MCP_TOKEN` is still supported as a temporary override, but storing a
token in shell history or source-controlled files is not recommended.

The rebalancer calls only `get_accounts`, `get_portfolio`,
`get_equity_positions`, and `get_equity_quotes`. Robinhood controls OAuth token
issuance and displays the permissions for you to approve in the browser.
