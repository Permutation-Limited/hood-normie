"""Example class-level portfolio rebalancer."""

import argparse
from dataclasses import replace
from decimal import Decimal
import json
import os
import sys
from typing import TextIO
from examples.paths import workspace_path
from examples.terminal import Style, color_enabled
from examples.rebalance.core import (
    Portfolio, Position, Recommendation, calculate, calculate_cash, decimal,
    load_config, parse_asset_classes, parse_portfolios,
)
from hood_normie import RobinhoodClient
from hood_normie.client import NormalizedPosition, PortfolioSnapshot
from hood_normie.oauth import DEFAULT_TOKEN_FILE, OAuthError


DEFAULT_ENDPOINT = "https://agent.robinhood.com/mcp/trading"
DEFAULT_CONFIG = "config.yaml"

AccountTable = tuple[str, dict[str, Position], Decimal]


def main() -> int:
    parser = argparse.ArgumentParser(description="Compute a read-only Robinhood rebalance plan")
    parser.add_argument("--config", default=DEFAULT_CONFIG,
                        help=f"target allocation YAML (default: {DEFAULT_CONFIG})")
    parser.add_argument("--portfolio", action="append",
                        help="configured portfolio name; repeat to select several")
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
    asset_classes = parse_asset_classes(config)
    portfolios = _selected_portfolios(parse_portfolios(config, asset_classes), args)

    account_numbers = [
        number for portfolio in portfolios for number in portfolio.account_numbers
    ]
    if not account_numbers and len(portfolios) > 1:
        raise ValueError(
            "with multiple portfolios, robinhood_account_numbers must be "
            "configured; automatic account selection cannot decide which "
            "portfolio the account belongs to"
        )
    external_symbols = {
        symbol for portfolio in portfolios for symbol in portfolio.external_symbols
    }
    portfolio_data = fetch_portfolios(
        args.endpoint, account_numbers, sorted(set(asset_classes) | external_symbols),
        args.token_file, verbose=args.verbose,
    )
    prices = {
        key.upper(): decimal(value) for key, value in portfolio_data.get("prices", {}).items()
    }

    reports = [
        _build_report(portfolio, portfolio_data, prices, asset_classes,
                      auto_selected=not account_numbers)
        for portfolio in portfolios
    ]
    if args.json:
        print(json.dumps([{
            "portfolio": portfolio.name,
            "recommendations": [{
                "asset_class": r.asset_class, "action": r.action,
                "amount": str(abs(r.amount)),
                "current_value": str(r.current_value), "target_value": str(r.target_value),
            } for r in recommendations],
        } for portfolio, _, recommendations, _ in reports], indent=2))
        for _, _, _, positions in reports:
            _warn_unclassified(positions, asset_classes, args, sys.stderr)
        return 0

    total_equity = Decimal(0)
    for portfolio, tables, recommendations, positions in reports:
        equity = _marked_equity(tables)
        total_equity += equity
        if len(reports) > 1:
            print(style.apply(f"━━ PORTFOLIO {portfolio.name}", style.BOLD, style.CYAN))
            print()
        for label, held_positions, account_cash in tables:
            _print_asset_table(label, held_positions, account_cash, asset_classes, style)
        print(style.apply(f"◆ COMPOSITE PORTFOLIO — {portfolio.name}",
                          style.BOLD, style.CYAN))
        print(style.apply(f"{'TOTAL':<48}${equity:>11,.2f}", style.BOLD))
        print()
        _warn_unclassified(positions, asset_classes, args, sys.stdout)
        _print_plan(portfolio, recommendations, style, labelled=len(reports) > 1)
        print()
    if len(reports) > 1:
        print(style.apply("◆ ALL PORTFOLIOS", style.BOLD, style.CYAN))
        print(style.apply(f"{'TOTAL':<48}${total_equity:>11,.2f}", style.BOLD))
    return 0


def _selected_portfolios(
    portfolios: list[Portfolio], args: argparse.Namespace
) -> list[Portfolio]:
    """Apply the --portfolio and --account command-line overrides."""
    if args.portfolio:
        wanted = list(dict.fromkeys(args.portfolio))
        by_name = {portfolio.name: portfolio for portfolio in portfolios}
        unknown = [name for name in wanted if name not in by_name]
        if unknown:
            raise ValueError(
                f"unknown portfolio(s): {', '.join(unknown)}. Configured: "
                f"{', '.join(by_name)}"
            )
        portfolios = [by_name[name] for name in wanted]
    if args.account:
        if len(portfolios) != 1:
            raise ValueError(
                "--account requires exactly one portfolio; narrow the run with "
                "--portfolio NAME"
            )
        portfolios = [replace(portfolios[0], account_numbers=tuple(args.account))]
    return portfolios


def _build_report(
    portfolio: Portfolio, portfolio_data: PortfolioSnapshot,
    prices: dict[str, Decimal], asset_classes: dict[str, str],
    auto_selected: bool,
) -> tuple[Portfolio, list[AccountTable], list[Recommendation], dict[str, Position]]:
    """Compute one portfolio's account tables and rebalance recommendations."""
    tables = _robinhood_tables(portfolio, portfolio_data, auto_selected)
    tables.extend(_external_tables(portfolio, prices))
    positions = _aggregate_positions(tables)
    current_cash = sum((cash for _, _, cash in tables), Decimal(0))
    recommendations = calculate(
        current_cash=current_cash,
        target_cash=portfolio.target_cash,
        targets=portfolio.targets,
        asset_classes=asset_classes,
        positions=positions,
        minimum_trade=portfolio.minimum_trade,
    )
    recommendations.append(calculate_cash(
        current_cash=current_cash,
        target_cash=portfolio.target_cash,
        minimum_trade=portfolio.minimum_trade,
    ))
    return portfolio, tables, recommendations, positions


def _robinhood_tables(
    portfolio: Portfolio, portfolio_data: PortfolioSnapshot, auto_selected: bool
) -> list[AccountTable]:
    fetched = portfolio_data["accounts"]
    if auto_selected:
        # No account was configured anywhere, so Robinhood picked the only
        # recognizable one and this is necessarily the only portfolio.
        accounts = list(fetched)
    else:
        by_number = {
            str(account.get("account_number")): account for account in fetched
        }
        accounts = [by_number[number] for number in portfolio.account_numbers
                    if number in by_number]
    tables: list[AccountTable] = []
    for index, account in enumerate(accounts, start=1):
        label = str(account.get("account_number") or f"Robinhood {index}")
        tables.append((
            f"ROBINHOOD ACCOUNT {label}",
            _parse_positions(account.get("positions", [])),
            decimal(account["cash"]),
        ))
    return tables


def _external_tables(
    portfolio: Portfolio, prices: dict[str, Decimal]
) -> list[AccountTable]:
    tables: list[AccountTable] = []
    for external in portfolio.external_accounts:
        positions: dict[str, Position] = {}
        for item in external.get("assets", []):
            symbol = item["symbol"].upper()
            if symbol in positions:
                raise ValueError(
                    f"duplicate symbol {symbol} in external account {external['name']}"
                )
            price = prices.get(symbol)
            if price is None:
                raise ValueError(
                    f"Robinhood did not return a quote for external asset {symbol}"
                )
            positions[symbol] = Position(symbol, decimal(item["quantity"]), price)
        tables.append((
            f"EXTERNAL ACCOUNT {external['name']}",
            positions,
            decimal(external.get("cash", 0)),
        ))
    return tables


def _marked_equity(tables: list[AccountTable]) -> Decimal:
    return sum(
        (position.market_value
         for _, positions, _ in tables for position in positions.values()),
        Decimal(0),
    ) + sum((cash for _, _, cash in tables), Decimal(0))


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


def _aggregate_positions(accounts: list[AccountTable]) -> dict[str, Position]:
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


def _warn_unclassified(
    positions: dict[str, Position], asset_classes: dict[str, str],
    args: argparse.Namespace, stream: TextIO,
) -> None:
    unclassified = sorted(
        (position for symbol, position in positions.items() if symbol not in asset_classes),
        key=lambda position: position.symbol,
    )
    if not unclassified:
        return
    style = Style(color_enabled(args.color, stream) and not args.json)
    print(style.apply(
        "⚠ NOTICE: Unclassified assets are implicitly ignored in allocation calculations:",
        style.BOLD, style.YELLOW,
    ), file=stream)
    for position in unclassified:
        print(f"  - {position.symbol}: ${position.market_value:,.2f}", file=stream)
    print(
        "Their value is removed from the allocation base and no trade is assumed. "
        "Map a symbol to a non-ignored class if it should affect targets.\n",
        file=stream,
    )


def _print_plan(
    portfolio: Portfolio, recommendations: list[Recommendation], style: Style,
    labelled: bool,
) -> None:
    heading = "◆ REBALANCE PLAN"
    if labelled:
        heading += f" — {portfolio.name}"
    print(style.apply(heading, style.BOLD, style.CYAN))
    print(style.apply(
        "ACTION CLASS              AMOUNT      CURRENT       TARGET", style.DIM
    ))
    for r in recommendations:
        line = (f"{r.action:<6} {r.asset_class:<12} "
                f"${abs(r.amount):>11,.2f} "
                f"${r.current_value:>11,.2f} ${r.target_value:>11,.2f}")
        action_color = {
            "BUY": style.GREEN, "SELL": style.RED, "HOLD": style.DIM,
        }.get(r.action, style.DIM)
        print(style.apply(line, action_color))


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
