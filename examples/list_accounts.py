"""List Robinhood brokerage accounts available to the authenticated user."""

import argparse
import os
import sys

from examples.paths import workspace_path
from hood_normie import RobinhoodClient
from hood_normie.accounts import account_records, account_summary
from hood_normie.oauth import DEFAULT_ENDPOINT, DEFAULT_TOKEN_FILE, OAuthError
from hood_normie.types import JsonObject


def main() -> int:
    parser = argparse.ArgumentParser(description="List available Robinhood accounts")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--token-file", default=DEFAULT_TOKEN_FILE,
                        help="OAuth token file created by //examples:authenticate")
    parser.add_argument("--verbose", action="store_true",
                        help="print MCP JSON-RPC requests and responses to stderr")
    args = parser.parse_args()
    token_file = workspace_path(args.token_file)

    token = os.environ.get("ROBINHOOD_MCP_TOKEN")
    client = (RobinhoodClient(token, endpoint=args.endpoint, verbose=args.verbose)
              if token else RobinhoodClient.from_token_file(
                  token_file, endpoint=args.endpoint, verbose=args.verbose
              ))
    client.connect()
    accounts = account_records(client.get_accounts())
    print_accounts(accounts)
    return 0


def print_accounts(accounts: list[JsonObject]) -> None:
    """Print a compact account table."""
    if not accounts:
        print("No Robinhood accounts found.")
        return

    rows = [(
        _display(summary["tax_status"]),
        _display(summary["account_type"]),
        _display(summary["account_number"]),
        _display(summary["nickname"]),
    ) for summary in map(account_summary, accounts)]
    headers = ("TAX STATUS", "CASH", "ACCOUNT NUMBER", "NICKNAME")
    widths = tuple(
        max(len(headers[index]), *(len(row[index]) for row in rows))
        for index in range(len(headers))
    )
    print("ROBINHOOD ACCOUNTS")
    print(
        f"{headers[0]:<{widths[0]}}  {headers[1]:<{widths[1]}}  "
        f"{headers[2]:<{widths[2]}}  {headers[3]}"
    )
    for tax_status, cash_type, number, nickname in rows:
        print(
            f"{tax_status:<{widths[0]}}  {cash_type:<{widths[1]}}  "
            f"{number:<{widths[2]}}  {nickname}"
        )


def _display(value: str | None) -> str:
    return value if value is not None else "(unavailable)"


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, OAuthError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(2)
