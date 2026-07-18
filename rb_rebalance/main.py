"""Command-line entry point."""

import argparse
from decimal import Decimal
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any

from rb_rebalance.accounts import select_account
from rb_rebalance.core import Position, Target, calculate, decimal
from rb_rebalance.mcp import RobinhoodMcpClient
from rb_rebalance.oauth import DEFAULT_TOKEN_FILE, OAuthError, load_access_token
from rb_rebalance.paths import workspace_path


DEFAULT_ENDPOINT = "https://agent.robinhood.com/mcp/trading"
DEFAULT_CONFIG = "config.json"
DEFAULT_SNAPSHOT = "snapshot.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Compute a read-only Robinhood rebalance plan")
    parser.add_argument("--config", default=DEFAULT_CONFIG,
                        help=f"target allocation JSON (default: {DEFAULT_CONFIG})")
    parser.add_argument("--snapshot", default=DEFAULT_SNAPSHOT,
                        help=f"offline broker snapshot JSON (default: {DEFAULT_SNAPSHOT})")
    parser.add_argument("--live", action="store_true",
                        help="fetch current data from Robinhood instead of reading --snapshot")
    parser.add_argument("--save-snapshot", nargs="?", const=DEFAULT_SNAPSHOT,
                        metavar="PATH",
                        help=f"with --live, save fetched data (default path: {DEFAULT_SNAPSHOT})")
    parser.add_argument("--account", help="Robinhood account number (required if ambiguous)")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--token-file", default=DEFAULT_TOKEN_FILE,
                        help="OAuth token file created by //:authenticate")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args()

    args.config = workspace_path(args.config)
    args.snapshot = workspace_path(args.snapshot)
    args.token_file = workspace_path(args.token_file)
    if args.save_snapshot:
        args.save_snapshot = workspace_path(args.save_snapshot)

    with open(args.config, encoding="utf-8") as stream:
        config = json.load(stream)
    targets = [Target(
        symbol=item["symbol"].upper(),
        weight=decimal(item["weight"]),
        asset_class=item.get("asset_class", "stock"),
    ) for item in config["targets"]]

    if args.save_snapshot and not args.live:
        parser.error("--save-snapshot requires --live")
    if args.live:
        snapshot = fetch_snapshot(args.endpoint, args.account, [t.symbol for t in targets],
                                  args.token_file)
        if args.save_snapshot:
            save_snapshot(args.save_snapshot, snapshot)
            print(f"Saved current Robinhood snapshot to {args.save_snapshot}", file=sys.stderr)
    else:
        try:
            with open(args.snapshot, encoding="utf-8") as stream:
                snapshot = json.load(stream)
        except FileNotFoundError as error:
            raise SystemExit(
                f"snapshot not found: {args.snapshot}; copy snapshot.example.json or run "
                "with --live --save-snapshot"
            ) from error

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
    account_number = account or select_account(accounts)
    arguments = {"account_number": account_number}
    portfolio = client.call_tool("get_portfolio", arguments)
    raw_positions = client.call_tool("get_equity_positions", arguments)
    raw_quotes = client.call_tool("get_equity_quotes", {"symbols": symbols})
    return normalize_snapshot(portfolio, raw_positions, raw_quotes)


def save_snapshot(path: str, snapshot: dict[str, Any]) -> None:
    """Atomically replace a normalized snapshot without leaving a partial file."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent, text=True
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(snapshot, stream, indent=2)
            stream.write("\n")
        os.replace(temporary, target)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


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
