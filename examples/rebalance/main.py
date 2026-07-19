"""Example class-level portfolio rebalancer."""

import argparse
from decimal import Decimal
import json
import os
import sys
from examples.paths import workspace_path
from examples.terminal import Style, color_enabled
from examples.rebalance.core import (
    ClassTarget, Position, calculate, calculate_cash, configured_account_numbers,
    decimal, load_config,
)
from hood_normie import RobinhoodClient
from hood_normie.client import NormalizedPosition, PortfolioSnapshot
from hood_normie.oauth import DEFAULT_TOKEN_FILE, OAuthError


DEFAULT_ENDPOINT = "https://agent.robinhood.com/mcp/trading"
DEFAULT_CONFIG = "config.yaml"


def main() -> int:
    parser = argparse.ArgumentParser(description="Compute a read-only Robinhood rebalance plan")
    parser.add_argument("--config", default=DEFAULT_CONFIG,
                        help=f"target allocation YAML (default: {DEFAULT_CONFIG})")
    parser.add_argument("--account", action="append",
                        help="Robinhood account number; repeat for multiple accounts")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--token-file", default=DEFAULT_TOKEN_FILE,
                        help="OAuth token file created by //examples:authenticate")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    parser.add_argument(
        "--color", choices=("auto", "always", "never"), default="auto",
        help="colorize human-readable output (default: auto)",
    )
    parser.add_argument("--verbose", action="store_true",
                        help="print MCP JSON-RPC requests and responses to stderr")
    args = parser.parse_args()
    style = Style(color_enabled(args.color, sys.stdout) and not args.json)

    args.config = workspace_path(args.config)
    args.token_file = workspace_path(args.token_file)

    config = load_config(args.config)
    if "classes" not in config or "assets" not in config:
        if "targets" in config:
            raise ValueError(
                "config uses the old per-symbol targets schema; replace it with "
                "top-level classes and assets sections "
                "(see examples/rebalance/config.example.yaml)"
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
    external_accounts = config.get("external_accounts", [])
    external_names = [item["name"] for item in external_accounts]
    if len(external_names) != len(set(external_names)):
        raise ValueError("external account names must be unique")
    external_symbols = {
        item["symbol"].upper()
        for account in external_accounts for item in account.get("assets", [])
    }
    account_numbers = args.account or configured_account_numbers(config)

    portfolio_data = fetch_portfolios(
        args.endpoint, account_numbers,
        sorted(set(asset_classes) | external_symbols),
        args.token_file, verbose=args.verbose,
    )
    robinhood_accounts = portfolio_data["accounts"]
    account_positions: list[tuple[str, dict[str, Position], Decimal]] = []
    current_cash = Decimal(0)
    for index, account in enumerate(robinhood_accounts, start=1):
        label = str(account.get("account_number") or f"Robinhood {index}")
        parsed = _parse_positions(account.get("positions", []))
        account_cash = decimal(account["cash"])
        account_positions.append((f"ROBINHOOD ACCOUNT {label}", parsed, account_cash))
        current_cash += account_cash

    prices = {
        key.upper(): decimal(value) for key, value in portfolio_data.get("prices", {}).items()
    }
    for external in external_accounts:
        external_positions: dict[str, Position] = {}
        external_cash = decimal(external.get("cash", 0))
        for item in external.get("assets", []):
            symbol = item["symbol"].upper()
            if symbol in external_positions:
                raise ValueError(f"duplicate symbol {symbol} in external account {external['name']}")
            price = prices.get(symbol)
            if price is None:
                raise ValueError(
                    f"Robinhood did not return a quote for external asset {symbol}"
                )
            external_positions[symbol] = Position(
                symbol, decimal(item["quantity"]), price
            )
        account_positions.append(
            (f"EXTERNAL ACCOUNT {external['name']}", external_positions, external_cash)
        )
        current_cash += external_cash

    positions = _aggregate_positions(account_positions)
    marked_account_equity = (
        sum((position.market_value for position in positions.values()), Decimal(0))
        + current_cash
    )
    target_cash = decimal(config.get("target_cash", 0))
    minimum_trade = decimal(config.get("minimum_trade", 0))
    recommendations = calculate(
        current_cash=current_cash,
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
        for label, held_positions, account_cash in account_positions:
            _print_asset_table(label, held_positions, account_cash, asset_classes, style)
        print(style.apply("◆ COMPOSITE PORTFOLIO", style.BOLD, style.CYAN))
        print(style.apply(f"{'TOTAL':<48}${marked_account_equity:>11,.2f}", style.BOLD))
        print()
    unclassified = sorted(
        (position for symbol, position in positions.items() if symbol not in asset_classes),
        key=lambda position: position.symbol,
    )
    warning_stream = sys.stderr if args.json else sys.stdout
    if unclassified:
        warning_style = Style(color_enabled(args.color, warning_stream) and not args.json)
        print(warning_style.apply(
            "⚠ NOTICE: Unclassified assets are implicitly ignored in allocation calculations:",
            warning_style.BOLD, warning_style.YELLOW,
        ), file=warning_stream)
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
        print(style.apply("◆ REBALANCE PLAN", style.BOLD, style.CYAN))
        print(style.apply(
            "ACTION CLASS              AMOUNT      CURRENT       TARGET", style.DIM
        ))
        for r in output_recommendations:
            line = (f"{r.action:<6} {r.asset_class:<12} "
                    f"${abs(r.amount):>11,.2f} "
                    f"${r.current_value:>11,.2f} ${r.target_value:>11,.2f}")
            action_color = {
                "BUY": style.GREEN, "SELL": style.RED, "HOLD": style.DIM,
            }.get(r.action, style.DIM)
            print(style.apply(line, action_color))
    return 0


def fetch_portfolios(endpoint: str, accounts: list[str], symbols: list[str],
                     token_file: str, verbose: bool = False) -> PortfolioSnapshot:
    token = os.environ.get("ROBINHOOD_MCP_TOKEN")
    client = (RobinhoodClient(token, endpoint=endpoint, verbose=verbose) if token else
              RobinhoodClient.from_token_file(
                  token_file, endpoint=endpoint, verbose=verbose
              ))
    return client.fetch_portfolios(accounts, symbols)


def _parse_positions(items: list[NormalizedPosition]) -> dict[str, Position]:
    result: dict[str, Position] = {}
    for item in items:
        symbol = item["symbol"].upper()
        position = Position(symbol, decimal(item["quantity"]), decimal(item["price"]))
        if symbol in result:
            existing = result[symbol]
            quantity = existing.quantity + position.quantity
            value = existing.market_value + position.market_value
            price = value / quantity if quantity else position.price
            position = Position(symbol, quantity, price)
        result[symbol] = position
    return result


def _aggregate_positions(
    accounts: list[tuple[str, dict[str, Position], Decimal]]
) -> dict[str, Position]:
    result: dict[str, Position] = {}
    for _, positions, _ in accounts:
        for symbol, position in positions.items():
            existing = result.get(symbol)
            if existing is None:
                result[symbol] = position
                continue
            quantity = existing.quantity + position.quantity
            value = existing.market_value + position.market_value
            price = value / quantity if quantity else position.price
            result[symbol] = Position(symbol, quantity, price)
    return result


def _print_asset_table(
    label: str, positions: dict[str, Position], cash: Decimal,
    asset_classes: dict[str, str], style: Style,
) -> None:
    print(style.apply(f"◆ CURRENT ASSETS — {label}", style.BOLD, style.CYAN))
    print(style.apply(
        "SYMBOL CLASS              QUANTITY        PRICE        VALUE", style.DIM
    ))
    if positions:
        for position in sorted(positions.values(), key=lambda item: item.symbol):
            asset_class = asset_classes.get(position.symbol, "UNCLASSIFIED")
            print(
                f"{position.symbol:<6} {asset_class:<14} "
                f"{position.quantity:>12,f} ${position.price:>11,.2f} "
                f"${position.market_value:>11,.2f}"
            )
    else:
        print(style.apply("(no positions)", style.DIM))
        if label.startswith("ROBINHOOD"):
            print(style.apply(
                "WARNING: Robinhood returned no equity positions for this account. "
                "Verify its number in config.yaml.", style.YELLOW
            ))
    total_assets = sum(
        (position.market_value for position in positions.values()), Decimal(0)
    )
    print(style.apply(f"{'CASH':<48}${cash:>11,.2f}", style.CYAN))
    print(style.apply(f"{'TOTAL':<48}${total_assets + cash:>11,.2f}", style.BOLD))
    print()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, KeyError, OAuthError) as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(2)
