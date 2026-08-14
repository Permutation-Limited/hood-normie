"""Invented portfolio data for demo mode.

Demo mode answers the same report from the same computation as a live run, with
one substitution: this snapshot replaces the Robinhood fetch. Nothing here
touches the network, reads a token, or reads the user's config, so the app can be
shown, screenshotted, or developed against without an account.

The numbers are fiction. The UI labels every demo response as such.
"""

from decimal import Decimal
import os
from typing import Mapping

from examples.rebalance.report import Report, build_report
from hood_normie.accounts import account_label
from hood_normie.client import (
    LabeledAccount, NormalizedAccount, NormalizedPosition, PortfolioSnapshot,
)
from hood_normie.types import JsonObject, JsonValue


CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_config.yaml")

# Quotes for every symbol demo_config.yaml classifies, plus one it does not.
PRICES: Mapping[str, str] = {
    "VTI": "285.50",
    "VXUS": "68.20",
    "BND": "72.85",
    "BNDX": "49.10",
    "GLD": "245.75",
    "OLDCO": "12.40",
    "MEME": "3.15",
}

HOLDINGS: Mapping[str, list[tuple[str, str]]] = {
    "DEMO-TAXABLE": [
        ("VTI", "300"),
        ("VXUS", "250"),
        ("BND", "150"),
        ("GLD", "40"),
        ("OLDCO", "500"),
        # Held but unmapped, so the report shows its unclassified notice.
        ("MEME", "200"),
    ],
    "DEMO-IRA": [
        ("VTI", "180"),
        ("VXUS", "120"),
        ("BND", "400"),
        ("GLD", "10"),
    ],
}

CASH: Mapping[str, str] = {
    "DEMO-TAXABLE": "4250.75",
    "DEMO-IRA": "1120.40",
}

# Shaped like `get_accounts` records, so the accounts view parses demo data
# through exactly the code path a live response goes through.
ACCOUNTS: list[JsonObject] = [
    {
        "account_number": "DEMO-TAXABLE",
        "tax_status": "Individual",
        "account_type": "margin",
        "nickname": "Demo Brokerage",
    },
    {
        "account_number": "DEMO-IRA",
        "retirement_account_type": "Roth IRA",
        "account_type": "cash",
        "nickname": "Demo Retirement",
    },
]


def fetch(*, endpoint: str, account_numbers: list[str], symbols: list[str],
          token_file: str, verbose: bool = False) -> PortfolioSnapshot:
    """Stand in for `report.fetch_portfolios`, matching its shape exactly."""
    del endpoint, token_file, verbose  # A demo run has nothing to connect to.
    del symbols  # Every demo symbol is quoted below, so nothing to select.
    accounts: list[NormalizedAccount] = []
    for number in account_numbers or list(HOLDINGS):
        positions: list[NormalizedPosition] = [
            {"symbol": symbol, "quantity": quantity, "price": PRICES[symbol]}
            for symbol, quantity in HOLDINGS.get(number, [])
        ]
        cash = Decimal(CASH.get(number, "0"))
        marked = sum(
            (Decimal(item["quantity"]) * Decimal(item["price"]) for item in positions),
            Decimal(0),
        )
        accounts.append({
            "account_number": number,
            "cash": str(cash),
            "net_liquidation_value": str(marked + cash),
            "positions": positions,
        })
    return {"accounts": accounts, "prices": dict(PRICES)}


def build_demo_report() -> Report:
    """Build the report from demo config and demo holdings."""
    return build_report(config_path=CONFIG, token_file="", fetch=fetch)


def demo_accounts() -> JsonValue:
    """Stand in for `get_accounts`, matching the payload shape it returns."""
    return [dict(account) for account in ACCOUNTS]


def demo_holdings() -> list[LabeledAccount]:
    """Stand in for `RobinhoodClient.fetch_holdings`, matching its shape."""
    by_number = {str(account["account_number"]): account for account in ACCOUNTS}
    snapshot = fetch(endpoint="", account_numbers=[], symbols=[], token_file="")
    holdings: list[LabeledAccount] = []
    for account in snapshot["accounts"]:
        number = str(account.get("account_number"))
        holdings.append({
            "label": account_label(number, by_number.get(number)),
            "account_number": number,
            "net_liquidation_value": account["net_liquidation_value"],
            "cash": account["cash"],
            "positions": account["positions"],
        })
    return holdings
