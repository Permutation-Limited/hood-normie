"""Unrealized gains per holding, per account, and across taxable accounts.

Each position is marked at the latest quote against its tax-lot cost basis.
Retirement accounts are listed but left out of the taxable total, since their
gains are not taxed when realized. Holding periods are not considered.
"""

import argparse
from decimal import Decimal
import os
import sys

from examples.paths import workspace_path
from examples.terminal import Style, color_enabled
from examples.unrealized.core import Holding, Totals
from examples.unrealized.report import build_unrealized_report
from hood_normie import RobinhoodClient
from hood_normie.mcp import McpError
from hood_normie.oauth import DEFAULT_ENDPOINT, DEFAULT_TOKEN_FILE, OAuthError


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account", action="append",
                        help="account number; repeat to report several accounts")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--token-file", default=DEFAULT_TOKEN_FILE,
                        help="OAuth token file created by //examples:authenticate")
    parser.add_argument(
        "--color", choices=("auto", "always", "never"), default="auto",
        help="colorize human-readable output (default: auto)",
    )
    parser.add_argument("--verbose", action="store_true",
                        help="print MCP JSON-RPC requests and responses to stderr")
    args = parser.parse_args()
    style = Style(color_enabled(args.color, sys.stdout))

    token = os.environ.get("ROBINHOOD_MCP_TOKEN")
    client = (RobinhoodClient(token, endpoint=args.endpoint, verbose=args.verbose)
              if token else RobinhoodClient.from_token_file(
                  workspace_path(args.token_file), endpoint=args.endpoint,
                  verbose=args.verbose,
              ))
    report = build_unrealized_report(client, args.account or ())

    for account in report.accounts:
        heading = f"◆ UNREALIZED — {account.label}"
        print(style.apply(heading, style.BOLD, style.CYAN))
        if account.tax_advantaged:
            print(style.apply(
                "tax-advantaged: not taxed when realized, and left out of the "
                "taxable total", style.DIM,
            ))
        print_holdings(account.holdings, account.totals, style)
        print()
    if len(report.taxable) > 1:
        print(style.apply("◆ UNREALIZED — TAXABLE ACCOUNTS COMBINED", style.BOLD,
                          style.CYAN))
        print_holdings(report.combined, report.taxable_totals, style)
    return 0


def print_holdings(holdings: tuple[Holding, ...], total: Totals,
                   style: Style | None = None) -> None:
    style = style or Style(False)
    if not holdings:
        print(style.apply("(no equity positions)", style.DIM))
        return
    print(style.apply(
        f"{'SYMBOL':<7} {'QUANTITY':>14} {'PRICE':>11} {'VALUE':>14} "
        f"{'COST BASIS':>14} {'GAIN':>14} {'RETURN':>8}", style.DIM,
    ))
    for item in holdings:
        gain = item.unrealized
        color = "" if gain is None else (style.GREEN if gain > 0 else
                                         style.RED if gain < 0 else "")
        note = "" if item.basis_source == "tax lots" else f"  ({item.basis_source})"
        print(
            f"{item.symbol:<7} {item.quantity.normalize():>14,f} "
            f"{_money(item.price):>11} {_money(item.market_value):>14} "
            f"{_money(item.cost_basis):>14} "
            + style.apply(f"{_money(gain):>14} {_percent(item.return_rate):>8}", color)
            + style.apply(note, style.DIM)
        )
    color = (style.GREEN if total.unrealized > 0 else
             style.RED if total.unrealized < 0 else "")
    print(
        # The first three columns (symbol, quantity, price) span 35 characters.
        style.apply(f"{'TOTAL':<35}{_money(total.market_value):>14} "
                    f"{_money(total.cost_basis):>14} ", style.BOLD)
        + style.apply(f"{_money(total.unrealized):>14} "
                      f"{_percent(total.return_rate):>8}", style.BOLD, color)
    )
    if total.incomplete:
        print(style.apply(
            f"{total.incomplete} holding(s) without a price or basis are left out "
            "of the total.", style.YELLOW,
        ))


def _money(value: Decimal | None) -> str:
    if value is None:
        return "—"
    sign = "-" if value < 0 else ""
    return f"{sign}${abs(value):,.2f}"


def _percent(value: Decimal | None) -> str:
    return "—" if value is None else f"{value * 100:+.1f}%"


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, OAuthError, McpError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(2)
