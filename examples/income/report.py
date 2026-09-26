"""Fetch one year's realized gains and dividends for every account.

Shared by the command-line tool and the web API, so both classify the same
records the same way. Rendering lives with each of them.
"""

from datetime import date, datetime
from typing import Iterable, Protocol

from examples.income.core import (
    EASTERN, AccountIncome, IncomeConfig, IncomeReport, classify_sales,
    eastern_date, equity_sell_times, is_equity_sale, lot_dates, reinvested_dividends,
)
from hood_normie.accounts import (
    account_label, account_number, account_records, is_tax_advantaged,
)
from hood_normie.mcp import McpError
from hood_normie.types import JsonObject, JsonValue


class IncomeSource(Protocol):
    """What the report reads; `RobinhoodClient` provides it, and so does the demo."""

    def connect(self) -> None: ...

    def get_accounts(self) -> JsonValue: ...

    def realized_trades(self, account_number: str, span: str) -> list[JsonObject]: ...

    def equity_orders(self, account_number: str, **filters: str) -> list[JsonObject]: ...

    def equity_tax_lots(self, account_number: str, symbol: str) -> list[JsonObject]: ...


def today_eastern() -> date:
    return datetime.now(EASTERN).date()


def build_income_report(
    source: IncomeSource,
    year: int,
    config: IncomeConfig,
    account_numbers: Iterable[str] = (),
    today: date | None = None,
) -> IncomeReport:
    """Classify every requested account's sales and dividends for one year."""
    current = today or today_eastern()
    if year > current.year:
        raise ValueError(f"{year} has not started yet")
    # The trade history takes preset spans only. `ytd` is exactly this year;
    # an earlier year has to come out of the full history.
    span = "ytd" if year == current.year else "all"

    source.connect()
    by_number = {
        str(number): account for account in account_records(source.get_accounts())
        if (number := account_number(account)) is not None
    }
    selected = [str(value) for value in account_numbers] or list(by_number)
    if not selected:
        raise ValueError("Robinhood returned no accounts with an account number")

    accounts: list[AccountIncome] = []
    for number in selected:
        record = by_number.get(number)
        trades = [
            trade for trade in source.realized_trades(number, span)
            if isinstance(trade.get("timestamp"), str)
            and eastern_date(str(trade["timestamp"])).year == year
        ]
        # Every state, not just `filled`: a partly filled order that was then
        # cancelled still sold shares. Orders reach back into the autumn before,
        # so a sale early in the year from an order placed late the year before
        # still finds its order.
        orders = source.equity_orders(number, created_at_gte=f"{year - 1}-10-01")
        sell_times = equity_sell_times(orders)
        sold_equities = sorted({
            str(trade["symbol"]).upper() for trade in trades
            if isinstance(trade.get("symbol"), str)
            and is_equity_sale(str(trade["symbol"]), str(trade["timestamp"]), sell_times)
        })
        tax_advantaged = record is not None and is_tax_advantaged(record)
        open_lots: dict[str, list[date] | None] = {}
        # A retirement account's holding periods change nothing this year, so
        # its sales are not worth a lot lookup each.
        for symbol in [] if tax_advantaged else sold_equities:
            try:
                open_lots[symbol] = lot_dates(source.equity_tax_lots(number, symbol))
            except McpError:
                open_lots[symbol] = None
        accounts.append(AccountIncome(
            label=account_label(number, record),
            account_number=number,
            tax_advantaged=tax_advantaged,
            sales=tuple(classify_sales(
                trades, year, sell_times, open_lots, config,
                tax_advantaged=tax_advantaged,
            )),
            dividends=tuple(reinvested_dividends(orders, year, config)),
        ))
    return IncomeReport(year=year, accounts=tuple(accounts))
