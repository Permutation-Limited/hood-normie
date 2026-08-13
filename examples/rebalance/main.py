"""Example class-level portfolio rebalancer."""

import argparse
import json
import sys
from typing import Mapping, TextIO
from examples.paths import workspace_path
from examples.terminal import Style, color_enabled
from examples.rebalance.core import Position, Recommendation
from examples.rebalance.report import (
    DEFAULT_ENDPOINT, ROBINHOOD, AccountHoldings, PortfolioReport, build_report,
)
from hood_normie.oauth import DEFAULT_TOKEN_FILE, OAuthError


DEFAULT_CONFIG = "config.yaml"


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

    report = build_report(
        config_path=workspace_path(args.config),
        token_file=workspace_path(args.token_file),
        endpoint=args.endpoint,
        portfolio_names=args.portfolio,
        account_numbers=args.account,
        verbose=args.verbose,
    )

    if args.json:
        print(json.dumps([{
            "portfolio": item.portfolio.name,
            "recommendations": [_json_recommendation(r) for r in item.recommendations],
        } for item in report.portfolios], indent=2))
        for item in report.portfolios:
            _warn_unclassified(item, report.asset_classes, args, sys.stderr)
        return 0

    labelled = len(report.portfolios) > 1
    for item in report.portfolios:
        if labelled:
            # Magenta separates portfolio sections from their cyan subsections.
            print(style.apply(f"━━ PORTFOLIO {item.portfolio.name}",
                              style.BOLD, style.MAGENTA))
            print()
        for account in item.accounts:
            _print_asset_table(account, report.asset_classes, style)
        print(style.apply(f"◆ COMPOSITE PORTFOLIO — {item.portfolio.name}",
                          style.BOLD, style.CYAN))
        print(style.apply(f"{'TOTAL':<48}${item.total_value:>11,.2f}", style.BOLD))
        print()
        _warn_unclassified(item, report.asset_classes, args, sys.stdout)
        _print_plan(item, style, labelled)
        print()
    if labelled:
        print(style.apply("━━ ALL PORTFOLIOS", style.BOLD, style.MAGENTA))
        print(style.apply(f"{'TOTAL':<48}${report.grand_total:>11,.2f}", style.BOLD))
    return 0


def _json_recommendation(item: Recommendation) -> dict[str, str]:
    return {
        "asset_class": item.asset_class, "action": item.action,
        "amount": str(abs(item.amount)),
        "current_value": str(item.current_value),
        "target_value": str(item.target_value),
    }


def _warn_unclassified(
    item: PortfolioReport, asset_classes: Mapping[str, str],
    args: argparse.Namespace, stream: TextIO,
) -> None:
    unclassified = item.unclassified(asset_classes)
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


def _print_plan(item: PortfolioReport, style: Style, labelled: bool) -> None:
    heading = "◆ REBALANCE PLAN"
    if labelled:
        heading += f" — {item.portfolio.name}"
    print(style.apply(heading, style.BOLD, style.CYAN))
    print(style.apply(
        "ACTION CLASS              AMOUNT      CURRENT       TARGET", style.DIM
    ))
    for r in item.recommendations:
        line = (f"{r.action:<6} {r.asset_class:<12} "
                f"${abs(r.amount):>11,.2f} "
                f"${r.current_value:>11,.2f} ${r.target_value:>11,.2f}")
        action_color = {
            "BUY": style.GREEN, "SELL": style.RED, "HOLD": style.DIM,
        }.get(r.action, style.DIM)
        print(style.apply(line, action_color))


def _print_asset_table(
    account: AccountHoldings, asset_classes: Mapping[str, str], style: Style,
) -> None:
    kind = "ROBINHOOD ACCOUNT" if account.kind == ROBINHOOD else "EXTERNAL ACCOUNT"
    print(style.apply(f"◆ CURRENT ASSETS — {kind} {account.label}",
                      style.BOLD, style.CYAN))
    print(style.apply(
        "SYMBOL CLASS              QUANTITY        PRICE        VALUE", style.DIM
    ))
    if account.positions:
        for position in sorted(account.positions.values(), key=_by_symbol):
            asset_class = asset_classes.get(position.symbol, "UNCLASSIFIED")
            print(
                f"{position.symbol:<6} {asset_class:<14} "
                f"{position.quantity:>12,f} ${position.price:>11,.2f} "
                f"${position.market_value:>11,.2f}"
            )
    else:
        print(style.apply("(no positions)", style.DIM))
        if account.kind == ROBINHOOD:
            print(style.apply(
                "WARNING: Robinhood returned no equity positions for this account. "
                "Verify its number in config.yaml.", style.YELLOW
            ))
    print(style.apply(f"{'CASH':<48}${account.cash:>11,.2f}", style.CYAN))
    print(style.apply(f"{'TOTAL':<48}${account.total_value:>11,.2f}", style.BOLD))
    print()


def _by_symbol(position: Position) -> str:
    return position.symbol


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, KeyError, OAuthError) as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(2)
