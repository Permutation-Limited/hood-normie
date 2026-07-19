"""List equity holdings for one or more Robinhood accounts."""

import argparse
from decimal import Decimal
import os
import sys

from examples.paths import workspace_path
from examples.terminal import Style, color_enabled
from hood_normie import RobinhoodClient
from hood_normie.accounts import account_number, account_records, first
from hood_normie.client import NormalizedPosition, normalize_account, position_symbols
from hood_normie.oauth import DEFAULT_ENDPOINT, DEFAULT_TOKEN_FILE, OAuthError
from hood_normie.types import JsonValue


def main() -> int:
    parser = argparse.ArgumentParser(description="List Robinhood equity holdings")
    parser.add_argument("--account", action="append",
                        help="account number; repeat to list multiple accounts")
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
    token_file = workspace_path(args.token_file)
    style = Style(color_enabled(args.color, sys.stdout))

    token = os.environ.get("ROBINHOOD_MCP_TOKEN")
    client = (RobinhoodClient(token, endpoint=args.endpoint, verbose=args.verbose)
              if token else RobinhoodClient.from_token_file(
                  token_file, endpoint=args.endpoint, verbose=args.verbose
              ))
    client.connect()
    accounts = account_records(client.get_accounts())
    accounts_by_number = {
        str(number): account for account in accounts
        if (number := account_number(account)) is not None
    }
    selected = args.account or _all_account_numbers(accounts)

    raw_accounts: list[tuple[str, JsonValue, JsonValue]] = []
    symbols: set[str] = set()
    for number in selected:
        portfolio = client.get_portfolio(number)
        positions = client.get_equity_positions(number)
        raw_accounts.append((number, portfolio, positions))
        symbols.update(position_symbols(positions))
    quotes = client.get_equity_quotes(symbols)

    for index, (number, portfolio, positions) in enumerate(raw_accounts):
        normalized = normalize_account(portfolio, positions, quotes)
        if index:
            print()
        label = _account_label(number, accounts_by_number.get(number))
        print_holdings(label, normalized["positions"], normalized["cash"], style)
    return 0


def _all_account_numbers(accounts: object) -> list[str]:
    records = account_records(accounts)
    numbers = [account_number(account) for account in records]
    result = [str(number) for number in numbers if number is not None]
    if not result:
        raise ValueError("Robinhood returned no accounts with an account number")
    return result


def _account_label(number: str, account: dict[str, JsonValue] | None) -> str:
    if account is None:
        return number
    tax_status = first(
        account, "tax_status", "taxStatus", "tax_type", "taxType",
        "retirement_account_type", "retirementAccountType",
        "brokerage_account_type", "brokerageAccountType",
    )
    nickname = first(account, "nickname", "display_name", "displayName", "name")
    parts = [
        str(value) for value in (tax_status, nickname)
        if isinstance(value, (str, int, float)) and not isinstance(value, bool)
    ]
    parts.append(number)
    return " · ".join(parts)


def print_holdings(
    account_label: str, positions: list[NormalizedPosition],
    cash_value: object = 0,
    style: Style | None = None,
) -> None:
    """Print one account's normalized holdings."""
    style = style or Style(False)
    print(style.apply(f"◆ HOLDINGS — {account_label}", style.BOLD, style.CYAN))
    print(style.apply("SYMBOL       QUANTITY        PRICE        VALUE", style.DIM))
    if not positions:
        print(style.apply("(no equity positions)", style.DIM))
    total_positions = Decimal(0)
    for position in sorted(positions, key=lambda item: item["symbol"]):
        quantity = _decimal(position["quantity"])
        price = _decimal(position["price"])
        value = quantity * price
        total_positions += value
        print(
            f"{position['symbol']:<6} {quantity:>14,f} "
            f"${price:>11,.2f} ${value:>11,.2f}"
        )
    cash = _decimal(cash_value)
    print(style.apply(f"{'CASH':<35}${cash:>11,.2f}", style.CYAN))
    print(style.apply(f"{'TOTAL':<35}${total_positions + cash:>11,.2f}", style.BOLD))


def _decimal(value: object) -> Decimal:
    return Decimal(str(value).replace("$", "").replace(",", ""))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, OAuthError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(2)
