"""Realized gains and dividends per account, for estimating quarterly taxes.

Sorts one calendar year's income into short-term, long-term, qualified, and
non-qualified buckets. It does not estimate any tax.
"""

import argparse
from decimal import Decimal
import os
import sys

from examples.income.core import (
    DEFAULT_CONFIG, AccountIncome, IncomeReport, IncomeTotals, cumulative,
    dividends_by_symbol, estimated_tax_periods, load_optional_config,
)
from examples.income.report import build_income_report, today_eastern
from examples.paths import workspace_path
from examples.terminal import Style, color_enabled
from hood_normie import RobinhoodClient
from hood_normie.mcp import McpError
from hood_normie.oauth import DEFAULT_ENDPOINT, DEFAULT_TOKEN_FILE, OAuthError


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=None,
                        help="calendar year to report (default: this year)")
    parser.add_argument("--account", action="append",
                        help="account number; repeat to report several accounts")
    parser.add_argument(
        "--config", default=None,
        help="qualified-dividend and holding-period overrides "
             f"(default: {DEFAULT_CONFIG} if it exists)",
    )
    parser.add_argument(
        "--cumulative", action="store_true",
        help="show each estimated-tax period as year-to-date through its end, "
             "as Form 2210 Schedule AI asks",
    )
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

    config = load_optional_config(
        workspace_path(args.config) if args.config else None,
        workspace_path(DEFAULT_CONFIG),
    )
    token = os.environ.get("ROBINHOOD_MCP_TOKEN")
    token_file = workspace_path(args.token_file)
    client = (RobinhoodClient(token, endpoint=args.endpoint, verbose=args.verbose)
              if token else RobinhoodClient.from_token_file(
                  token_file, endpoint=args.endpoint, verbose=args.verbose
              ))
    report = build_income_report(
        client, args.year or today_eastern().year, config, args.account or ()
    )

    for account in report.accounts:
        print_account(account, report.year, style, cumulative=args.cumulative)
        print()
    print_taxable_totals(report, style, cumulative=args.cumulative)
    return 0


def print_account(account: AccountIncome, year: int, style: Style | None = None,
                  *, cumulative: bool = False) -> None:
    style = style or Style(False)
    heading = f"◆ INCOME {year} — {account.label}"
    print(style.apply(heading, style.BOLD, style.CYAN))
    if account.tax_advantaged:
        print(style.apply(
            "tax-advantaged: nothing here is taxed this year, and it is left out "
            "of the taxable total", style.DIM,
        ))

    print(style.apply("REALIZED GAINS", style.BOLD))
    if not account.sales:
        print(style.apply("(no closing trades)", style.DIM))
    else:
        print(style.apply(
            f"{'DATE':<10} {'SYMBOL':<7} {'QUANTITY':>14} {'GAIN':>12}  "
            f"{'TERM':<7} BASIS", style.DIM,
        ))
        for sale in account.sales:
            term = sale.term.upper() if sale.term != "unknown" else "?"
            color = style.YELLOW if sale.term == "unknown" else ""
            print(
                f"{sale.when.isoformat():<10} {sale.symbol:<7} "
                f"{sale.quantity.normalize():>14,f} "
                f"{_money(sale.gain):>12}  "
                + style.apply(f"{term:<7}", color) + " "
                + style.apply(sale.reason, style.DIM)
            )

    print(style.apply("DIVIDENDS", style.BOLD))
    by_symbol = dividends_by_symbol(account.dividends)
    if not by_symbol:
        print(style.apply("(no dividends)", style.DIM))
    else:
        print(style.apply(
            f"{'SYMBOL':<7} {'PAID':>12} {'CASH (EST.)':>12} {'QUALIFIED':>12} "
            f"{'NON-QUAL':>12} {'UNCLASSIFIED':>12}", style.DIM,
        ))
        for symbol, totals in by_symbol.items():
            unclassified = _money(totals.unclassified)
            cash = _money(totals.estimated_cash) if totals.estimated_cash else "-"
            print(
                f"{symbol:<7} {_money(totals.dividends):>12} "
                + style.apply(f"{cash:>12}", style.DIM if not totals.estimated_cash else "")
                + f" {_money(totals.qualified):>12} {_money(totals.nonqualified):>12} "
                + style.apply(f"{unclassified:>12}",
                              style.YELLOW if totals.unclassified else "")
            )

    if account.tax_advantaged:
        # Neither holding period nor qualification matters inside the account.
        print(style.apply("SUMMARY", style.BOLD))
        print(f"{'Realized gains':<24} {_money(account.totals.realized):>14}")
        print(f"{'Dividends':<24} {_money(account.totals.dividends):>14}")
    else:
        print_summary(account.totals, style)
        if account.sales or account.dividends:
            print_periods(account.period_totals(year), year, style, cumulative)


def print_summary(totals: IncomeTotals, style: Style) -> None:
    rows = (
        ("Short-term gains", totals.short_term, False),
        ("Long-term gains", totals.long_term, False),
        ("Unknown-term gains", totals.unknown_term, True),
        ("Qualified dividends", totals.qualified, False),
        ("Non-qualified dividends", totals.nonqualified, False),
        ("Unclassified dividends", totals.unclassified, True),
    )
    print(style.apply("SUMMARY", style.BOLD))
    for label, value, needs_attention in rows:
        line = f"{label:<24} {_money(value):>14}"
        print(style.apply(line, style.YELLOW) if needs_attention and value else line)
    if totals.estimated_cash:
        print(style.apply(
            f"{'  of which cash (est.)':<24} {_money(totals.estimated_cash):>14}",
            style.DIM,
        ))


def print_periods(periods: list[IncomeTotals], year: int, style: Style,
                  cumulative_view: bool = False) -> None:
    """One row per IRS estimated-tax period: Jan–Mar, Apr–May, Jun–Aug, Sep–Dec."""
    rows = cumulative(periods) if cumulative_view else periods
    title = ("BY ESTIMATED-TAX PERIOD (year to date through each period's end)"
             if cumulative_view else "BY ESTIMATED-TAX PERIOD")
    print(style.apply(title, style.BOLD))
    print(style.apply(
        f"{'PERIOD':<13} {'DUE':<10} {'SHORT':>11} {'LONG':>11} {'UNKNOWN':>11} "
        f"{'QUALIFIED':>11} {'NON-QUAL':>11} {'UNCLASS.':>11}", style.DIM,
    ))
    for period, totals in zip(estimated_tax_periods(year), rows):
        unresolved = (
            f"{_money(totals.unknown_term):>11} ",
            f"{_money(totals.unclassified):>11}",
        )
        print(
            f"{period.label:<13} {period.due.isoformat():<10} "
            f"{_money(totals.short_term):>11} {_money(totals.long_term):>11} "
            + style.apply(unresolved[0], style.YELLOW if totals.unknown_term else "")
            + f"{_money(totals.qualified):>11} {_money(totals.nonqualified):>11} "
            + style.apply(unresolved[1], style.YELLOW if totals.unclassified else "")
        )


def print_taxable_totals(report: IncomeReport, style: Style,
                         *, cumulative: bool = False) -> None:
    totals = report.taxable_totals
    print(style.apply(f"◆ TAXABLE ACCOUNTS {report.year}", style.BOLD, style.CYAN))
    print_summary(totals, style)
    print_periods(report.taxable_period_totals, report.year, style, cumulative)
    if totals.unknown_term or totals.unclassified:
        print(style.apply(
            "Unknown and unclassified amounts need a holding period or qualified "
            f"share in {DEFAULT_CONFIG}; see examples/income/README.md.",
            style.YELLOW,
        ))


def _money(value: Decimal) -> str:
    sign = "-" if value < 0 else ""
    return f"{sign}${abs(value):,.2f}"


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, OAuthError, McpError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(2)
