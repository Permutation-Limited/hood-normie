# hood-mcp-py

A small Python library for Robinhood's official Trading MCP server. It provides:

- Streamable HTTP MCP transport and JSON-RPC tool calls.
- OAuth 2.1 discovery, PKCE authentication, token storage, and refresh.
- Account discovery and selection helpers.
- Typed high-level access to accounts, portfolios, equity positions, and quotes.
- Stable normalization of Robinhood responses and multi-account snapshots.

The library is read/write capable at the MCP transport layer, but its high-level
`RobinhoodClient` currently exposes read-only portfolio methods. The included
examples do not place trades.

## Bazel library

Depend on:

```starlark
deps = ["//hood_mcp_py"]
```

Basic use:

```python
from hood_mcp_py import RobinhoodClient

client = RobinhoodClient.from_token_file(".robinhood-mcp-token.json")
snapshot = client.fetch_snapshot(
    account_numbers=["ACCOUNT_ONE", "ACCOUNT_TWO"],
    quote_symbols=["VTI", "BND"],
)
```

Lower-level access is available through `RobinhoodMcpClient`:

```python
from hood_mcp_py import RobinhoodMcpClient

client = RobinhoodMcpClient(endpoint, access_token)
client.connect()
accounts = client.call_tool("get_accounts")
```

## Examples

Authenticate interactively:

```sh
bazel run //examples:authenticate
```

Run the composite portfolio rebalancer:

```sh
cp examples/rebalance/config.example.json config.json
bazel run //examples/rebalance:rebalance
```

The detailed rebalancer configuration and snapshot workflow is documented in
[`examples/rebalance/README.md`](examples/rebalance/README.md).

Compatibility aliases remain available as `//:authenticate`, `//:rebalance`,
and `//:rebalance_lib`, but new users should use the targets under `//examples`.

## Tests

```sh
bazel test //...
```
