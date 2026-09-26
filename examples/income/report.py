"""Fetch one year's realized gains and dividends for every account.

Shared by the command-line tool and the web API, so both classify the same
records the same way. Rendering lives with each of them.
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Iterable, Protocol

from examples.income.core import (
    EASTERN, AccountIncome, ClosedPortion, Dividend, IncomeConfig, IncomeReport,
    WashSale,
    classify_sales, decimal, eastern_date, equity_sell_times, is_equity_sale,
    lot_dates, lot_quantities, reinvested_dividends,
)
from examples.income.dividends import (
    DividendEvent, dividend_events, estimated_cash_dividends, unreinvested_events,
)
from examples.income.lots import closed_portions, fills, sell_fills
from examples.income.wash import LossSale, Purchase, find_wash_sales
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

    def equity_positions(self, account_number: str) -> list[JsonObject]: ...

    def daily_closes(
        self, symbols: Iterable[str], start_time: str, adjustment_type: str
    ) -> dict[str, dict[str, str]]: ...


@dataclass
class AccountRecords:
    """Everything fetched for one account before any classification."""

    number: str
    record: JsonObject | None
    trades: list[JsonObject]
    orders: list[JsonObject]
    positions: dict[str, Decimal]
    # Open lots by symbol, fetched on first use; None where Robinhood refused.
    lots: dict[str, list[JsonObject] | None]

    @property
    def tax_advantaged(self) -> bool:
        return self.record is not None and is_tax_advantaged(self.record)


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

    fetched = [_fetch(source, number, by_number.get(number), span, year)
               for number in selected]
    events = _dividend_events(source, fetched, year)
    accounts = tuple(
        _account_income(source, records, year, config, events) for records in fetched
    )
    return IncomeReport(
        year=year, accounts=accounts,
        wash_sales=tuple(_wash_sales(fetched, accounts)),
        carryover_short=config.carryover_short,
        carryover_long=config.carryover_long,
    )


def _wash_sales(fetched: list[AccountRecords],
                accounts: tuple[AccountIncome, ...]) -> list[WashSale]:
    """Loss sales in taxable accounts against purchases in every account."""
    purchases: list[Purchase] = []
    for records, account in zip(fetched, accounts):
        symbols = {str(order.get("symbol")).upper() for order in records.orders
                   if order.get("side") == "buy" and order.get("symbol")}
        for symbol in symbols:
            for moment, _, side, quantity, _ in fills(records.orders, symbol):
                if side == "buy":
                    purchases.append(Purchase(
                        symbol=symbol, when=eastern_date(moment.isoformat()),
                        account_number=records.number, account_label=account.label,
                        tax_advantaged=records.tax_advantaged, quantity=quantity,
                    ))
    by_number = {records.number: records for records in fetched}

    def held_after(number: str, symbol: str, day: date) -> Decimal:
        # Walk back from today's position through every fill after the day.
        # Transfers are invisible here, so this is an estimate.
        records = by_number[number]
        held = records.positions.get(symbol, Decimal(0))
        for moment, _, side, quantity, _ in fills(records.orders, symbol):
            if eastern_date(moment.isoformat()) > day:
                held += -quantity if side == "buy" else quantity
        return max(held, Decimal(0))

    losses = [
        LossSale(records.number, account.label, sale)
        for records, account in zip(fetched, accounts) if not account.tax_advantaged
        for sale in account.sales
    ]
    return find_wash_sales(losses, purchases, held_after)


def _fetch(source: IncomeSource, number: str, record: JsonObject | None,
           span: str, year: int) -> AccountRecords:
    trades = [
        trade for trade in source.realized_trades(number, span)
        if isinstance(trade.get("timestamp"), str)
        and eastern_date(str(trade["timestamp"])).year == year
    ]
    positions: dict[str, Decimal] = {}
    for position in source.equity_positions(number):
        symbol = position.get("symbol")
        if isinstance(symbol, str) and position.get("quantity") is not None:
            positions[symbol.upper()] = decimal(position["quantity"])
    # The whole history, in every state: a partly filled order that was then
    # cancelled still sold shares, and replaying lots needs every buy.
    return AccountRecords(
        number=number, record=record, trades=trades,
        orders=source.equity_orders(number), positions=positions, lots={},
    )


def _lots(source: IncomeSource, records: AccountRecords,
          symbol: str) -> list[JsonObject] | None:
    if symbol not in records.lots:
        try:
            records.lots[symbol] = source.equity_tax_lots(records.number, symbol)
        except McpError:
            records.lots[symbol] = None
    return records.lots[symbol]


def _held_symbols(records: AccountRecords, year: int) -> set[str]:
    """Symbols held now, or traded since the start of the year before."""
    symbols = set(records.positions)
    for order in records.orders:
        created = order.get("created_at")
        symbol = order.get("symbol")
        if (isinstance(created, str) and isinstance(symbol, str)
                and eastern_date(created).year >= year - 1
                and decimal(order.get("cumulative_quantity") or 0) > 0):
            symbols.add(symbol.upper())
    return symbols


def _dividend_events(source: IncomeSource, fetched: list[AccountRecords],
                     year: int) -> dict[str, list[DividendEvent]]:
    """Every held symbol's ex-dates, from the December before `year` on.

    One pair of price-history requests covers every account.
    """
    symbols: set[str] = set()
    for records in fetched:
        symbols |= _held_symbols(records, year)
    if not symbols:
        return {}
    start = f"{year - 1}-12-01T00:00:00Z"
    split = source.daily_closes(symbols, start, "split")
    full = source.daily_closes(symbols, start, "all")
    return {
        symbol: dividend_events(symbol, split[symbol], full[symbol])
        for symbol in symbols if symbol in split and symbol in full
    }


def _account_income(source: IncomeSource, records: AccountRecords, year: int,
                    config: IncomeConfig,
                    events: dict[str, list[DividendEvent]]) -> AccountIncome:
    sell_times = equity_sell_times(records.orders)
    sold_equities = sorted({
        str(trade["symbol"]).upper() for trade in records.trades
        if isinstance(trade.get("symbol"), str)
        and is_equity_sale(str(trade["symbol"]), str(trade["timestamp"]), sell_times)
    })
    open_lots: dict[str, list[date] | None] = {}
    closed: dict[str, list[ClosedPortion]] = {}
    # A retirement account's holding periods change nothing this year, so its
    # sales are not worth a lot lookup each.
    for symbol in [] if records.tax_advantaged else sold_equities:
        lots = _lots(source, records, symbol)
        open_lots[symbol] = None if lots is None else lot_dates(lots)
        closed.update(closed_portions(
            records.orders, symbol, records.positions.get(symbol, Decimal(0))
        ) or {})

    # DRIP purchases a year either side, so a December ex-date reinvested in
    # January still pairs with its own event rather than looking unpaid.
    drips: list[Dividend] = [
        item for span_year in (year - 1, year, year + 1)
        for item in reinvested_dividends(records.orders, span_year, config)
    ]
    held = _held_symbols(records, year)
    unpaired = unreinvested_events(
        [event for symbol in held for event in events.get(symbol, [])], drips
    )
    cash_symbols = {event.symbol for event in unpaired if event.ex_date.year == year}
    cash = estimated_cash_dividends(
        unpaired, year,
        {symbol: lot_quantities(_lots(source, records, symbol) or [])
         for symbol in cash_symbols},
        {symbol: sell_fills(records.orders, symbol) for symbol in cash_symbols},
        config,
    )
    dividends = [item for item in drips if item.when.year == year] + cash

    return AccountIncome(
        label=account_label(records.number, records.record),
        account_number=records.number,
        tax_advantaged=records.tax_advantaged,
        sales=tuple(classify_sales(
            records.trades, year, sell_times, open_lots, config,
            tax_advantaged=records.tax_advantaged, closed_lots=closed,
        )),
        dividends=tuple(sorted(dividends, key=lambda item: (item.when, item.symbol))),
    )
