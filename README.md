# hood-normie

A small Python library for Robinhood's official Trading MCP server. It provides:

- Streamable HTTP MCP transport and JSON-RPC tool calls.
- OAuth 2.1 discovery, PKCE authentication, token storage, and refresh.
- Account discovery and selection helpers.
- Typed high-level access to accounts, portfolios, equity positions, and quotes.
- Stable normalization of Robinhood responses and multi-account portfolio data.
- A targeted example showing how to implement simple portfolio rebalancing (read-only instructions, doesn't execute trades)

The library is read/write capable at the MCP transport layer, but its high-level
`RobinhoodClient` currently exposes read-only portfolio methods. The included
examples do not place trades.

## Prerequisites

This project requires [Bazelisk](https://github.com/bazelbuild/bazelisk) to
build, run examples, and execute tests. Bazelisk reads `.bazelversion` and
automatically uses the required Bazel version.

## Examples

Authenticate interactively via web browser. This stores credentials in a git-ignored file `.robinhood-mcp-token.json`, which is read by other examples:

```sh
bazel run //examples:authenticate
```

List the Robinhood accounts available to the authenticated user:

```sh
bazel run //examples:list_accounts
```

Run the composite portfolio rebalancer:

```sh
cp examples/rebalance/config.example.yaml config.yaml
bazel run //examples/rebalance:rebalance
```

Example output (using illustrative account values):

```text
◆ CURRENT ASSETS — ROBINHOOD ACCOUNT EXAMPLE
SYMBOL CLASS              QUANTITY        PRICE        VALUE
BND    bonds               250.000 $      72.00 $  18,000.00
VTI    stocks              200.000 $     400.00 $  80,000.00
CASH                                            $  -1,000.00
TOTAL                                           $  97,000.00

◆ COMPOSITE PORTFOLIO
TOTAL                                           $  97,000.00

◆ REBALANCE PLAN
ACTION CLASS              AMOUNT      CURRENT       TARGET
BUY    bonds        $   1,800.00 $  18,000.00 $  19,800.00
SELL   stocks       $     800.00 $  80,000.00 $  79,200.00
SELL   cash         $   1,000.00 $  -1,000.00 $  -2,000.00
```

The recommendations are class-level dollar adjustments only. The example is
read-only and does not choose a security or place an order.

The detailed rebalancer configuration is documented in
[`examples/rebalance/README.md`](examples/rebalance/README.md).

## Bazel library

Depend on:

```starlark
deps = ["//hood_normie"]
```

Basic use:

```python
from hood_normie import RobinhoodClient

client = RobinhoodClient.from_token_file(".robinhood-mcp-token.json")
portfolio = client.fetch_portfolios(
    account_numbers=["ACCOUNT_ONE", "ACCOUNT_TWO"],
    quote_symbols=["VTI", "BND"],
)
```

Lower-level access is available through `RobinhoodMcpClient`:

```python
from hood_normie import RobinhoodMcpClient

client = RobinhoodMcpClient(endpoint, access_token)
client.connect()
accounts = client.call_tool("get_accounts")
```

## Tests

```sh
bazel test //...
```

The suite includes the `//:typecheck` mypy target. Run it independently with
`bazel test //:typecheck` when you only need static type validation.

## Pre-commit checks

Install the repository's Git pre-commit hook with:

```sh
bazel run //hooks:install
```

The hook currently runs only `detect-secrets` against staged files. Run it
manually against all tracked files with:

```sh
bazel run //hooks:run -- --all-files
```
