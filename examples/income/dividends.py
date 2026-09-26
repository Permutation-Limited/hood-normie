"""Dividends paid in cash, reconstructed from price history.

Robinhood's MCP has no dividend tool. A reinvested dividend leaves a DRIP order
behind; one paid in cash leaves nothing. Price history still records it:
Robinhood's dividend-adjusted closes are the split-adjusted closes minus every
later dividend, so the gap between the two series is constant between
ex-dividend dates and drops by exactly the per-share dividend on each one.

The shares entitled to a dividend are those held before its ex-date: the open
lots acquired before it, plus whatever was sold on or after it. Lots
transferred in after the ex-date keep their original acquisition date, so they
can be counted when they should not be; the amount is an estimate.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Iterable, Mapping

from examples.income.core import CENT, IncomeConfig, Dividend


# Smaller steps are rounding in the published closes, not a distribution.
MINIMUM_PER_SHARE = Decimal("0.0001")

# How long after an ex-date a DRIP purchase can still be that dividend's.
REINVESTMENT_WINDOW = timedelta(days=45)


@dataclass(frozen=True)
class DividendEvent:
    symbol: str
    ex_date: date
    per_share: Decimal


def dividend_events(
    symbol: str, split_adjusted: Mapping[str, str], fully_adjusted: Mapping[str, str]
) -> list[DividendEvent]:
    """Ex-dates and per-share amounts from two daily close series.

    Comparing against split-adjusted rather than raw closes keeps a stock split
    from reading as a string of dividends.
    """
    days = sorted(day for day in split_adjusted if day in fully_adjusted)
    gaps = [Decimal(split_adjusted[day]) - Decimal(fully_adjusted[day]) for day in days]
    events: list[DividendEvent] = []
    for before, after, day in zip(gaps, gaps[1:], days[1:]):
        paid = before - after
        if paid >= MINIMUM_PER_SHARE:
            events.append(DividendEvent(symbol.upper(), date.fromisoformat(day), paid))
    return events


def shares_entitled(
    ex_date: date,
    lots: Iterable[tuple[date, Decimal]],
    sales: Iterable[tuple[date, Decimal]],
) -> Decimal:
    """Shares held going into an ex-date: older open lots plus later sales."""
    held = sum((quantity for opened, quantity in lots if opened < ex_date), Decimal(0))
    sold_since = sum((quantity for sold, quantity in sales if sold >= ex_date), Decimal(0))
    return held + sold_since


def unreinvested_events(
    events: Iterable[DividendEvent], reinvested: Iterable[Dividend]
) -> list[DividendEvent]:
    """The events no DRIP purchase accounts for, earliest first.

    Each reinvestment pays for the latest unclaimed event of its symbol that
    went ex before it, within the window. Pairing from the purchase's side
    keeps one unreinvested month from shifting every later pairing by one.
    """
    unclaimed = sorted(events, key=lambda item: item.ex_date)
    for purchase in sorted(reinvested, key=lambda item: item.when):
        candidates = [
            event for event in unclaimed
            if event.symbol == purchase.symbol
            and event.ex_date <= purchase.when <= event.ex_date + REINVESTMENT_WINDOW
        ]
        if candidates:
            unclaimed.remove(candidates[-1])
    return unclaimed


def estimated_cash_dividends(
    events: Iterable[DividendEvent],
    year: int,
    lots: Mapping[str, list[tuple[date, Decimal]]],
    sales: Mapping[str, list[tuple[date, Decimal]]],
    config: IncomeConfig,
) -> list[Dividend]:
    """Cash dividends for events in `year`, dated by ex-date.

    The ex-date stands in for the pay date, which Robinhood does not report;
    for a fund they are usually days apart.
    """
    dividends: list[Dividend] = []
    for event in events:
        if event.ex_date.year != year:
            continue
        shares = shares_entitled(
            event.ex_date, lots.get(event.symbol, []), sales.get(event.symbol, [])
        )
        amount = (event.per_share * shares).quantize(CENT)
        if amount > 0:
            dividends.append(Dividend(
                when=event.ex_date, symbol=event.symbol, amount=amount,
                qualified_fraction=config.qualified_fractions.get(event.symbol),
                reinvested=False,
            ))
    return sorted(dividends, key=lambda item: (item.when, item.symbol))
