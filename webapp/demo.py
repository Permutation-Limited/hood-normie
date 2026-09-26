"""Invented portfolio data for demo mode.

Demo mode answers the same report from the same computation as a live run, with
one substitution: this snapshot replaces the Robinhood fetch. Nothing here
touches the network, reads a token, or reads the user's config, so the app can be
shown, screenshotted, or developed against without an account.

The numbers are fiction. The UI labels every demo response as such.
"""

from datetime import date
from decimal import Decimal
import os
from typing import Mapping

from examples.income.core import IncomeConfig, IncomeReport
from examples.income.report import build_income_report
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


# Closing trades for the Income tab, as (account, month, day, symbol, quantity,
# price, gain, equity). Each is placed in whichever year is requested.
SALES: list[tuple[str, int, int, str, str, str, str, bool]] = [
    # Older lots still open: inferred long-term.
    ("DEMO-TAXABLE", 2, 11, "VTI", "20", "281.10", "1840.55", True),
    # Closed out entirely, so only the demo config can settle it.
    ("DEMO-TAXABLE", 3, 4, "SPAC", "400", "9.80", "-612.00", True),
    ("DEMO-TAXABLE", 3, 18, "EXITED", "50", "41.25", "905.10", True),
    # The oldest open lot is too young to prove anything.
    ("DEMO-TAXABLE", 5, 20, "MEME", "100", "3.40", "118.00", True),
    # A coin: the trade history lists it alongside equities.
    ("DEMO-TAXABLE", 6, 2, "BTC", "0.015", "64200", "212.40", False),
    ("DEMO-IRA", 4, 9, "BND", "60", "72.10", "-44.70", True),
]

# Open lot acquisition dates, as whole years before the requested one plus a
# month and day; zero years means earlier in the requested year itself.
LOTS: Mapping[tuple[str, str], list[tuple[int, int, int]]] = {
    ("DEMO-TAXABLE", "VTI"): [(4, 6, 12), (0, 1, 15)],
    ("DEMO-TAXABLE", "MEME"): [(0, 1, 8)],
    ("DEMO-TAXABLE", "SPAC"): [],
    ("DEMO-TAXABLE", "EXITED"): [],
}

# Reinvested dividends, as (account, symbol, per-quarter payment).
DIVIDENDS: list[tuple[str, str, str]] = [
    ("DEMO-TAXABLE", "VTI", "312.40"),
    ("DEMO-TAXABLE", "VXUS", "188.15"),
    ("DEMO-TAXABLE", "BND", "41.02"),
    ("DEMO-TAXABLE", "OLDCO", "22.50"),
    ("DEMO-IRA", "VTI", "187.44"),
    ("DEMO-IRA", "BND", "109.38"),
]

# What a user would put in income.yaml. OLDCO is left out on purpose, so the
# demo shows an unclassified dividend.
INCOME_CONFIG = IncomeConfig(
    qualified_fractions={
        "VTI": Decimal("0.95"), "VXUS": Decimal("0.70"), "BND": Decimal(0),
    },
    holding_periods={"SPAC": "short", "EXITED": "long"},
)


def _stamp(year: int, month: int, day: int, hour: int = 15) -> str:
    return f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}:30:00Z"


class DemoIncomeSource:
    """Stands in for RobinhoodClient, answering from the tables above."""

    def __init__(self, year: int) -> None:
        self.year = year

    def connect(self) -> None:
        pass

    def get_accounts(self) -> JsonValue:
        return demo_accounts()

    def realized_trades(self, account_number: str, span: str) -> list[JsonObject]:
        del span  # Every demo trade falls inside the requested year.
        return [
            {"timestamp": _stamp(self.year, month, day), "symbol": symbol,
             "side": "sell", "quantity": quantity, "price": price,
             "realized_gain": gain}
            for account, month, day, symbol, quantity, price, gain, _ in SALES
            if account == account_number
        ]

    def equity_orders(self, account_number: str, **filters: str) -> list[JsonObject]:
        del filters
        orders: list[JsonObject] = []
        for account, month, day, symbol, quantity, price, _, equity in SALES:
            if account == account_number and equity:
                stamp = _stamp(self.year, month, day)
                orders.append({
                    "symbol": symbol, "side": "sell", "state": "filled",
                    "placed_agent": "user", "quantity": quantity,
                    "cumulative_quantity": quantity, "average_price": price,
                    "created_at": stamp, "last_transaction_at": stamp,
                    "executions": [{"timestamp": stamp, "quantity": quantity}],
                })
        for account, symbol, amount in DIVIDENDS:
            if account != account_number:
                continue
            for month in (3, 6, 9, 12):
                orders.append({
                    "symbol": symbol, "side": "buy", "state": "filled",
                    "placed_agent": "drip",
                    "created_at": _stamp(self.year, month, 20, hour=2),
                    "dollar_based_amount": {"amount": amount, "currency_code": "USD"},
                })
        return orders

    def equity_tax_lots(self, account_number: str, symbol: str) -> list[JsonObject]:
        return [
            {"open_date": date(self.year - years, month, day).isoformat()}
            for years, month, day in LOTS.get((account_number, symbol), [])
        ]


def build_demo_income(year: int) -> IncomeReport:
    """The income report from invented records, through the live computation."""
    return build_income_report(DemoIncomeSource(year), year, INCOME_CONFIG)
