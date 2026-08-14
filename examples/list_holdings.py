"""List equity holdings for one or more Robinhood accounts."""

import argparse
from decimal import Decimal
import os
import sys

from examples.paths import workspace_path
from examples.terminal import Style, color_enabled
from hood_normie import RobinhoodClient
from hood_normie.client import NormalizedPosition
from hood_normie.oauth import DEFAULT_ENDPOINT, DEFAULT_TOKEN_FILE, OAuthError


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
    for index, account in enumerate(client.fetch_holdings(args.account or ())):
        if index:
            print()
        print_holdings(account["label"], account["positions"], account["cash"], style)
    return 0


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
