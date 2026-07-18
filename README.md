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

## Run against Robinhood MCP

Robinhood's endpoint is `https://agent.robinhood.com/mcp/trading`. Authenticate
with Robinhood using an MCP-capable client and supply its OAuth access token as
an environment variable (never put it in the config or source tree):

```sh
export ROBINHOOD_MCP_TOKEN='...'
bazel run //:rebalance -- \
  --config "$PWD/config.example.json" \
  --account 'YOUR_ACCOUNT_NUMBER'
```

The program calls only `get_accounts`, `get_portfolio`,
`get_equity_positions`, and `get_equity_quotes`. Robinhood controls OAuth token
issuance; if your MCP client does not expose its token, use that client to save
those tool results in the normalized shape shown by `snapshot.example.json`.

