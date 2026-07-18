"""Command-line entry point."""

import argparse
from decimal import Decimal
import json
import os
import sys
from typing import Any

from rb_rebalance.core import Position, Target, calculate, decimal
from rb_rebalance.mcp import RobinhoodMcpClient
from rb_rebalance.oauth import DEFAULT_TOKEN_FILE, OAuthError, load_access_token


DEFAULT_ENDPOINT = "https://agent.robinhood.com/mcp/trading"


def main() -> int:
    parser = argparse.ArgumentParser(description="Compute a read-only Robinhood rebalance plan")
    parser.add_argument("--config", required=True, help="Target allocation JSON")
    parser.add_argument("--snapshot", help="Offline broker snapshot JSON (skips MCP)")
    parser.add_argument("--account", help="Robinhood account number (required if ambiguous)")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--token-file", default=DEFAULT_TOKEN_FILE,
                        help="OAuth token file created by //:authenticate")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args()

    with open(args.config, encoding="utf-8") as stream:
        config = json.load(stream)
    targets = [Target(
        symbol=item["symbol"].upper(),
        weight=decimal(item["weight"]),
        asset_class=item.get("asset_class", "stock"),
    ) for item in config["targets"]]

    if args.snapshot:
        with open(args.snapshot, encoding="utf-8") as stream:
            snapshot = json.load(stream)
    else:
        snapshot = fetch_snapshot(args.endpoint, args.account, [t.symbol for t in targets],
                                  args.token_file)

    positions = {
        item["symbol"].upper(): Position(
            item["symbol"].upper(), decimal(item["quantity"]), decimal(item["price"])
        ) for item in snapshot["positions"]
    }
    prices = {key.upper(): decimal(value) for key, value in snapshot.get("prices", {}).items()}
    recommendations = calculate(
        net_liquidation_value=decimal(snapshot["net_liquidation_value"]),
        target_cash=decimal(config.get("target_cash", 0)),
        targets=targets,
        positions=positions,
        prices=prices,
        minimum_trade=decimal(config.get("minimum_trade", 0)),
        liquidate_unconfigured=bool(config.get("liquidate_unconfigured", False)),
    )
    if args.json:
        print(json.dumps([{
            "symbol": r.symbol, "asset_class": r.asset_class, "action": r.action,
            "amount": str(abs(r.amount)), "shares": str(abs(r.shares)),
            "current_value": str(r.current_value), "target_value": str(r.target_value),
            "price": str(r.price),
        } for r in recommendations], indent=2))
    else:
        print("ACTION SYMBOL CLASS          AMOUNT       SHARES      CURRENT       TARGET")
        for r in recommendations:
            print(f"{r.action:<6} {r.symbol:<6} {r.asset_class:<8} "
                  f"${abs(r.amount):>11,.2f} {abs(r.shares):>12,f} "
                  f"${r.current_value:>11,.2f} ${r.target_value:>11,.2f}")
        projected_cash = decimal(snapshot["net_liquidation_value"]) - sum(
            (r.target_value for r in recommendations if r.asset_class != "unconfigured"), Decimal(0)
        )
        print(f"\nProjected cash: ${projected_cash:,.2f}")
    return 0


def fetch_snapshot(endpoint: str, account: str | None, symbols: list[str],
                   token_file: str) -> dict[str, Any]:
    token = os.environ.get("ROBINHOOD_MCP_TOKEN") or load_access_token(token_file)
    client = RobinhoodMcpClient(endpoint, token)
    client.connect()
    accounts = client.call_tool("get_accounts")
    account_number = account or _select_account(accounts)
    arguments = {"account_number": account_number}
    portfolio = client.call_tool("get_portfolio", arguments)
    raw_positions = client.call_tool("get_equity_positions", arguments)
    raw_quotes = client.call_tool("get_equity_quotes", {"symbols": symbols})
    return normalize_snapshot(portfolio, raw_positions, raw_quotes)


def _select_account(payload: Any) -> str:
    accounts = _records(payload, "accounts")
    if len(accounts) != 1:
        raise SystemExit("pass --account because Robinhood returned zero or multiple accounts")
    value = _first(accounts[0], "account_number", "accountNumber", "number")
    if value is None:
        raise SystemExit("could not find an account number in get_accounts response")
    return str(value)


def normalize_snapshot(portfolio: Any, positions: Any, quotes: Any) -> dict[str, Any]:
    portfolio_record = _records(portfolio, "portfolios", "portfolio")[0]
    net_value = _first(portfolio_record, "net_liquidation_value", "netLiquidationValue",
                       "total_value", "totalValue", "equity")
    if net_value is None:
        raise SystemExit("could not find net liquidation/total value in get_portfolio response")
    quote_map = {}
    for quote in _records(quotes, "quotes", "results"):
        symbol = _first(quote, "symbol")
        price = _first(quote, "price", "mark_price", "markPrice", "last_trade_price")
        if symbol and price is not None:
            quote_map[str(symbol).upper()] = price
    normalized_positions = []
    for position in _records(positions, "positions", "results"):
        symbol = str(_first(position, "symbol") or "").upper()
        quantity = _first(position, "quantity", "shares")
        price = quote_map.get(symbol) or _first(position, "price", "market_price", "marketPrice")
        if symbol and quantity is not None and price is not None:
            normalized_positions.append({"symbol": symbol, "quantity": quantity, "price": price})
    return {"net_liquidation_value": net_value, "positions": normalized_positions,
            "prices": quote_map}


def _records(payload: Any, *keys: str) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
            if isinstance(value, dict):
                return [value]
        return [payload]
    raise SystemExit(f"unexpected Robinhood response: {payload!r}")


def _first(record: dict[str, Any], *keys: str) -> Any:
    return next((record[key] for key in keys if record.get(key) is not None), None)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, KeyError, OAuthError) as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(2)
