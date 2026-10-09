"""Fetch every account's positions, quotes, and lots into an unrealized report.

Shared by the command-line tool and the web API, so both compute the same
gains from the same records.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable, Protocol

from examples.unrealized.core import (
    AccountUnrealized, Lot, UnrealizedReport, decimal, holding, parse_lots,
)
from hood_normie.accounts import (
    account_label, account_number, account_records, is_tax_advantaged,
)
from hood_normie.client import normalize_quotes
from hood_normie.mcp import McpError
from hood_normie.types import JsonObject, JsonValue


class UnrealizedSource(Protocol):
    """What the report reads; `RobinhoodClient` provides it, and so does the demo."""

    def connect(self) -> None: ...

    def get_accounts(self) -> JsonValue: ...

    def equity_positions(self, account_number: str) -> list[JsonObject]: ...

    def get_equity_quotes(self, symbols: Iterable[str]) -> JsonValue: ...

    def equity_tax_lots(self, account_number: str, symbol: str) -> list[JsonObject]: ...


def build_unrealized_report(
    source: UnrealizedSource, account_numbers: Iterable[str] = ()
) -> UnrealizedReport:
    source.connect()
    by_number = {
        str(number): account for account in account_records(source.get_accounts())
        if (number := account_number(account)) is not None
    }
    selected = [str(value) for value in account_numbers] or list(by_number)
    if not selected:
        raise ValueError("Robinhood returned no accounts with an account number")

    positions = {
        number: [item for item in source.equity_positions(number)
                 if isinstance(item.get("symbol"), str)
                 and item.get("quantity") is not None]
        for number in selected
    }
    symbols = {str(item["symbol"]).upper() for items in positions.values()
               for item in items}
    # One quote request for every account, so a symbol held twice is marked
    # at the same price in both.
    prices = normalize_quotes(source.get_equity_quotes(symbols)) if symbols else {}

    accounts: list[AccountUnrealized] = []
    for number in selected:
        record = by_number.get(number)
        holdings = []
        for position in positions[number]:
            try:
                lots = source.equity_tax_lots(number, str(position["symbol"]))
            except McpError:
                lots = []  # Falls back to the position's average cost.
            holdings.append(holding(position, lots, prices, number))
        accounts.append(AccountUnrealized(
            label=account_label(number, record),
            account_number=number,
            tax_advantaged=record is not None and is_tax_advantaged(record),
            holdings=tuple(sorted(holdings, key=lambda item: item.symbol)),
        ))
    return UnrealizedReport(accounts=tuple(accounts))


@dataclass(frozen=True)
class HoldingLots:
    """One holding's open lots across the requested accounts, for a drill-down."""

    symbol: str
    price: Decimal | None
    lots: tuple[Lot, ...]


def build_holding_lots(source: UnrealizedSource, account_numbers: Iterable[str],
                       symbol: str) -> HoldingLots:
    """Fetch a single holding's lots on demand, marked at a fresh quote.

    The summary report reads every lot to split gains by term but leaves them
    out of its payload; this fills in one holding when a reader asks for it.
    """
    numbers = [str(value) for value in account_numbers]
    if not numbers:
        raise ValueError("lots need at least one account number")
    symbol = symbol.upper()
    source.connect()
    lots: list[Lot] = []
    for number in numbers:
        lots.extend(parse_lots(source.equity_tax_lots(number, symbol), number))
    price = normalize_quotes(source.get_equity_quotes([symbol])).get(symbol)
    return HoldingLots(
        symbol=symbol,
        price=None if price is None else decimal(price),
        lots=tuple(sorted(lots, key=lambda lot: lot.acquired or date.max)),
    )
