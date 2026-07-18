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
from rb_rebalance.core import ClassTarget, Position, calculate, calculate_cash, decimal
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
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--from-snapshot", action="store_true",
                      help="read offline data from --snapshot instead of Robinhood")
    mode.add_argument("--live", action="store_false", dest="from_snapshot",
                      help=argparse.SUPPRESS)
    parser.set_defaults(from_snapshot=False)
    parser.add_argument("--save-snapshot", nargs="?", const=DEFAULT_SNAPSHOT,
                        metavar="PATH",
                        help=f"save live fetched data (default path: {DEFAULT_SNAPSHOT})")
    parser.add_argument("--account", help="Robinhood account number (required if ambiguous)")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--token-file", default=DEFAULT_TOKEN_FILE,
                        help="OAuth token file created by //:authenticate")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    parser.add_argument("--verbose", action="store_true",
                        help="print MCP JSON-RPC requests and responses to stderr")
    args = parser.parse_args()

    args.config = workspace_path(args.config)
    args.snapshot = workspace_path(args.snapshot)
    args.token_file = workspace_path(args.token_file)
    if args.save_snapshot:
        args.save_snapshot = workspace_path(args.save_snapshot)

    with open(args.config, encoding="utf-8") as stream:
        config = json.load(stream)
    if "classes" not in config or "assets" not in config:
        if "targets" in config:
            raise ValueError(
                "config uses the old per-symbol targets schema; replace it with "
                "top-level classes and assets sections (see config.example.json)"
            )
        raise ValueError("config must contain top-level classes and assets sections")
    targets = [ClassTarget(
        name=item["name"],
        weight=decimal(item["weight"]) if item.get("weight") is not None else None,
        target_amount=(decimal(item["target_amount"])
                       if item.get("target_amount") is not None else None),
        ignore=bool(item.get("ignore", False)),
    ) for item in config["classes"]]
    asset_classes = {
        item["symbol"].upper(): item["class"] for item in config["assets"]
    }
    if len(asset_classes) != len(config["assets"]):
        raise ValueError("asset symbols must be unique")

    if args.save_snapshot and args.from_snapshot:
        parser.error("--save-snapshot cannot be used with --from-snapshot")
    if not args.from_snapshot:
        account_number = args.account or config.get("account_number")
        snapshot = fetch_snapshot(args.endpoint, account_number, list(asset_classes),
                                  args.token_file, verbose=args.verbose)
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
                "without --from-snapshot and use --save-snapshot"
            ) from error

    positions = {
        item["symbol"].upper(): Position(
            item["symbol"].upper(), decimal(item["quantity"]), decimal(item["price"])
        ) for item in snapshot["positions"]
    }
    net_liquidation_value = decimal(snapshot["net_liquidation_value"])
    if "cash" not in snapshot:
        raise ValueError(
            "snapshot has no broker-reported cash value; refresh it with "
            "--save-snapshot or add the Robinhood cash field"
        )
    current_cash = decimal(snapshot["cash"])
    target_cash = decimal(config.get("target_cash", 0))
    minimum_trade = decimal(config.get("minimum_trade", 0))
    recommendations = calculate(
        net_liquidation_value=net_liquidation_value,
        target_cash=target_cash,
        targets=targets,
        asset_classes=asset_classes,
        positions=positions,
        minimum_trade=minimum_trade,
    )
    cash_recommendation = calculate_cash(
        current_cash=current_cash,
        target_cash=target_cash,
        minimum_trade=minimum_trade,
    )
    output_recommendations = recommendations + [cash_recommendation]
    if not args.json:
        account_label = snapshot.get("account_number") or config.get("account_number")
        heading = "CURRENT ASSETS"
        if account_label:
            heading += f" — ACCOUNT {account_label}"
        print(heading)
        print("SYMBOL CLASS              QUANTITY        PRICE        VALUE")
        if positions:
            for position in sorted(positions.values(), key=lambda item: item.symbol):
                asset_class = asset_classes.get(position.symbol, "UNCLASSIFIED")
                print(
                    f"{position.symbol:<6} {asset_class:<14} "
                    f"{position.quantity:>12,f} ${position.price:>11,.2f} "
                    f"${position.market_value:>11,.2f}"
                )
            total_assets = sum(
                (position.market_value for position in positions.values()), Decimal(0)
            )
            print(f"{'TOTAL':<33} {'':>0} ${total_assets:>11,.2f}\n")
        else:
            print("(no equity positions returned)\n")
            print(
                "WARNING: Robinhood returned no equity positions for this account. "
                "Verify account_number in config.json; Robinhood may list both an "
                "empty Agentic account and a funded brokerage account.\n"
            )
    unclassified = sorted(
        (position for symbol, position in positions.items() if symbol not in asset_classes),
        key=lambda position: position.symbol,
    )
    warning_stream = sys.stderr if args.json else sys.stdout
    if unclassified:
        print("NOTICE: Unclassified assets are implicitly ignored in allocation calculations:",
              file=warning_stream)
        for position in unclassified:
            print(f"  - {position.symbol}: ${position.market_value:,.2f}", file=warning_stream)
        print(
            "Their value is removed from the allocation base and no trade is assumed. "
            "Map a symbol to a non-ignored class if it should affect targets.\n",
            file=warning_stream,
        )
    if args.json:
        print(json.dumps([{
            "asset_class": r.asset_class, "action": r.action,
            "amount": str(abs(r.amount)),
            "current_value": str(r.current_value), "target_value": str(r.target_value),
        } for r in output_recommendations], indent=2))
    else:
        print("ACTION CLASS              AMOUNT      CURRENT       TARGET")
        for r in output_recommendations:
            print(f"{r.action:<6} {r.asset_class:<12} "
                  f"${abs(r.amount):>11,.2f} "
                  f"${r.current_value:>11,.2f} ${r.target_value:>11,.2f}")
        projected_cash = target_cash
        print(f"\nProjected cash: ${projected_cash:,.2f}")
    return 0


def fetch_snapshot(endpoint: str, account: str | None, symbols: list[str],
                   token_file: str, verbose: bool = False) -> dict[str, Any]:
    token = os.environ.get("ROBINHOOD_MCP_TOKEN") or load_access_token(token_file)
    client = RobinhoodMcpClient(endpoint, token, verbose=verbose)
    client.connect()
    accounts = client.call_tool("get_accounts")
    account_number = account or select_account(accounts)
    arguments = {"account_number": account_number}
    portfolio = client.call_tool("get_portfolio", arguments)
    raw_positions = client.call_tool("get_equity_positions", arguments)
    held_symbols = _position_symbols(raw_positions)
    quote_symbols = sorted(set(symbols) | set(held_symbols))
    raw_quotes = client.call_tool("get_equity_quotes", {"symbols": quote_symbols})
    snapshot = normalize_snapshot(portfolio, raw_positions, raw_quotes)
    snapshot["account_number"] = account_number
    return snapshot


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
    value_fields = (
        "net_liquidation_value", "netLiquidationValue",
        "net_liquidation", "netLiquidation",
        "total_value", "totalValue",
        "total_equity", "totalEquity",
        "portfolio_value", "portfolioValue",
        "portfolio_equity", "portfolioEquity",
        "equity",
    )
    portfolio_record = _find_record_with_field(portfolio, value_fields)
    net_value = _money_value(_first(portfolio_record, *value_fields)) if portfolio_record else None
    if net_value is None:
        raise SystemExit(
            "could not find net liquidation/total value in get_portfolio response. "
            f"Response shape (values omitted): {_response_shape(portfolio)}"
        )
    cash = _money_value(_first(portfolio_record, "cash"))
    if cash is None:
        raise SystemExit(
            "could not find broker-reported cash in get_portfolio response. "
            f"Response shape (values omitted): {_response_shape(portfolio)}"
        )
    price_fields = (
        "price", "mark_price", "markPrice", "last_trade_price", "lastTradePrice",
        "last_price", "lastPrice", "current_price", "currentPrice",
    )
    quote_map = {}
    for quote in _find_records_with_fields(quotes, ("symbol",), price_fields):
        symbol = _first(quote, "symbol")
        price = _money_value(_first(quote, *price_fields))
        if symbol and price is not None:
            quote_map[str(symbol).upper()] = price
    normalized_positions = []
    missing_prices = []
    for position in _position_records(positions):
        symbol = str(_first(position, "symbol") or "").upper()
        quantity = _money_value(_first(position, "quantity", "shares"))
        price = quote_map.get(symbol) or _money_value(
            _first(position, *price_fields, "market_price", "marketPrice")
        )
        if symbol and quantity is not None:
            if price is None:
                missing_prices.append(symbol)
            else:
                normalized_positions.append(
                    {"symbol": symbol, "quantity": quantity, "price": price}
                )
    if missing_prices:
        raise SystemExit(
            "Robinhood returned positions without usable quotes for: "
            + ", ".join(sorted(missing_prices))
        )
    return {"net_liquidation_value": net_value, "cash": cash,
            "positions": normalized_positions, "prices": quote_map}


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


def _find_record_with_field(payload: Any, fields: tuple[str, ...]) -> dict[str, Any] | None:
    """Depth-first search through MCP content wrappers for a matching record."""
    if isinstance(payload, dict):
        if any(payload.get(field) is not None for field in fields):
            return payload
        for value in payload.values():
            found = _find_record_with_field(value, fields)
            if found is not None:
                return found
    elif isinstance(payload, list):
        for value in payload:
            found = _find_record_with_field(value, fields)
            if found is not None:
                return found
    return None


def _find_records_with_fields(
    payload: Any, required: tuple[str, ...], alternatives: tuple[str, ...]
) -> list[dict[str, Any]]:
    """Find nested records containing required keys and one alternative key."""
    found: list[dict[str, Any]] = []
    if isinstance(payload, dict):
        if (all(payload.get(field) is not None for field in required)
                and any(payload.get(field) is not None for field in alternatives)):
            found.append(payload)
        else:
            for value in payload.values():
                found.extend(_find_records_with_fields(value, required, alternatives))
    elif isinstance(payload, list):
        for value in payload:
            found.extend(_find_records_with_fields(value, required, alternatives))
    return found


def _position_records(payload: Any) -> list[dict[str, Any]]:
    return _find_records_with_fields(payload, ("symbol",), ("quantity", "shares"))


def _position_symbols(payload: Any) -> list[str]:
    """Extract held symbols before quotes are requested."""
    return sorted({
        str(_first(position, "symbol")).upper()
        for position in _position_records(payload)
        if _first(position, "symbol")
    })


def _money_value(value: Any) -> Any:
    """Unwrap common structured-money representations while preserving scalars."""
    if isinstance(value, dict):
        return _first(value, "amount", "value", "decimal", "units")
    return value


def _response_shape(payload: Any, depth: int = 0) -> Any:
    """Return keys and container types without leaking financial values."""
    if depth >= 5:
        return "..."
    if isinstance(payload, dict):
        return {key: _response_shape(value, depth + 1) for key, value in payload.items()}
    if isinstance(payload, list):
        return [_response_shape(payload[0], depth + 1)] if payload else []
    return type(payload).__name__


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, KeyError, OAuthError) as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(2)
