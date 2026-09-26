"""Realized gains and dividends, split the way a tax return asks for them.

Everything here is pure: it turns Robinhood tool records into classified sales
and dividends, and fetches nothing. `report.py` does the fetching.

Robinhood's MCP reports each closing trade's realized gain but not its holding
period, and exposes only the lots still open. The holding period of a sale is
therefore inferred, and only in one direction. Under first-in-first-out lot
relief (Robinhood's default), every share a sale closed was acquired no later
than the oldest lot still open that predates the sale. When that lot was already
held more than a year on the sale date, so was everything sold before it, and
the sale is long-term. Anything else stays "unknown" rather than guessed.

Dividends are only visible when Robinhood reinvested them: each DRIP purchase is
an equity order whose dollar amount is the dividend paid. Whether a dividend is
qualified is never reported at all, so that comes from configuration.

Nothing here estimates tax. It sorts income into the buckets an estimate needs.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
import os
from typing import Iterable, Literal, Mapping, TypedDict, cast
from zoneinfo import ZoneInfo

import yaml

from hood_normie.types import JsonObject


Term = Literal["short", "long", "unknown"]
TERMS: tuple[Term, ...] = ("short", "long", "unknown")

# Robinhood buckets days in US Eastern time, and so does the tax calendar a
# brokerage 1099 is built on.
EASTERN = ZoneInfo("America/New_York")
CENT = Decimal("0.01")

# How far a trade's timestamp may sit from its order's to count as that order.
MATCH_TOLERANCE = timedelta(seconds=5)

# Where the optional overrides live, relative to the workspace.
DEFAULT_CONFIG = "income.yaml"

EQUITY = "equity"
OTHER = "other"

# Why a sale landed in its term bucket, shown beside it so an inference is
# never mistaken for a broker-reported fact.
INFERRED_LONG = "older lot still open (FIFO)"
NO_OLDER_LOT = "no older open lot"
YOUNG_OLDEST_LOT = "oldest open lot under a year"
NOT_EQUITY = "crypto or options"
LOTS_UNAVAILABLE = "tax lots unavailable"
TAX_ADVANTAGED = "tax-advantaged account"
CONFIGURED = "set in config"
REPLAYED = "order history (FIFO)"


class IncomeConfigFile(TypedDict, total=False):
    """The optional YAML file that fills in what Robinhood does not report."""

    qualified_dividends: dict[str, object]
    holding_periods: dict[str, object]


@dataclass(frozen=True)
class IncomeConfig:
    """Classifications Robinhood does not report, keyed by symbol.

    `qualified_fractions` maps a symbol to the share of its dividends that is
    qualified. `holding_periods` settles sales whose term could not be inferred;
    it never overrides an inferred term.
    """

    qualified_fractions: Mapping[str, Decimal] = field(default_factory=dict)
    holding_periods: Mapping[str, Term] = field(default_factory=dict)


@dataclass(frozen=True)
class Sale:
    """One closing trade and its realized gain, as Robinhood reported it."""

    when: date
    symbol: str
    quantity: Decimal
    price: Decimal
    gain: Decimal
    asset: str
    term: Term
    reason: str


@dataclass(frozen=True)
class Dividend:
    """One dividend payment, split by how much of it is qualified."""

    when: date
    symbol: str
    amount: Decimal
    # None when nothing says how this symbol's dividends are taxed.
    qualified_fraction: Decimal | None
    # False for a cash payment estimated from price history (see dividends.py).
    reinvested: bool = True

    @property
    def qualified(self) -> Decimal:
        if self.qualified_fraction is None:
            return Decimal(0)
        return (self.amount * self.qualified_fraction).quantize(CENT)

    @property
    def nonqualified(self) -> Decimal:
        if self.qualified_fraction is None:
            return Decimal(0)
        # The remainder, so the two parts always add back to the payment.
        return self.amount - self.qualified

    @property
    def unclassified(self) -> Decimal:
        return self.amount if self.qualified_fraction is None else Decimal(0)


@dataclass(frozen=True)
class IncomeTotals:
    short_term: Decimal = Decimal(0)
    long_term: Decimal = Decimal(0)
    unknown_term: Decimal = Decimal(0)
    qualified: Decimal = Decimal(0)
    nonqualified: Decimal = Decimal(0)
    unclassified: Decimal = Decimal(0)
    # The part of the three dividend buckets estimated rather than reported.
    estimated_cash: Decimal = Decimal(0)

    @property
    def realized(self) -> Decimal:
        return self.short_term + self.long_term + self.unknown_term

    @property
    def dividends(self) -> Decimal:
        return self.qualified + self.nonqualified + self.unclassified

    def __add__(self, other: "IncomeTotals") -> "IncomeTotals":
        return IncomeTotals(
            short_term=self.short_term + other.short_term,
            long_term=self.long_term + other.long_term,
            unknown_term=self.unknown_term + other.unknown_term,
            qualified=self.qualified + other.qualified,
            nonqualified=self.nonqualified + other.nonqualified,
            unclassified=self.unclassified + other.unclassified,
            estimated_cash=self.estimated_cash + other.estimated_cash,
        )


@dataclass(frozen=True)
class AccountIncome:
    """One account's realized gains and dividends for a calendar year."""

    label: str
    account_number: str
    tax_advantaged: bool
    sales: tuple[Sale, ...]
    dividends: tuple[Dividend, ...]

    @property
    def totals(self) -> IncomeTotals:
        return income_totals(self.sales, self.dividends)

    def period_totals(self, year: int) -> list[IncomeTotals]:
        """Totals for each estimated-tax period of the year, in order."""
        return [
            income_totals(
                [sale for sale in self.sales if period.start <= sale.when <= period.end],
                [item for item in self.dividends
                 if period.start <= item.when <= period.end],
            )
            for period in estimated_tax_periods(year)
        ]


@dataclass(frozen=True)
class IncomeReport:
    year: int
    accounts: tuple[AccountIncome, ...]

    @property
    def taxable(self) -> tuple[AccountIncome, ...]:
        """Accounts whose income is taxed this year; retirement income is not."""
        return tuple(item for item in self.accounts if not item.tax_advantaged)

    @property
    def taxable_totals(self) -> IncomeTotals:
        return sum((item.totals for item in self.taxable), IncomeTotals())

    @property
    def taxable_period_totals(self) -> list[IncomeTotals]:
        periods = [IncomeTotals() for _ in estimated_tax_periods(self.year)]
        for account in self.taxable:
            periods = [
                total + part
                for total, part in zip(periods, account.period_totals(self.year))
            ]
        return periods


@dataclass(frozen=True)
class TaxPeriod:
    """One estimated-tax payment period, as the IRS defines them.

    They are not calendar quarters: two months, then three, then four. Form
    2210's annualized method (Schedule AI) asks for income through each end
    date, so the cumulative sums matter as much as each period's own.
    """

    number: int
    start: date
    end: date
    # The nominal due date; a weekend or holiday moves it to the next business day.
    due: date

    @property
    def label(self) -> str:
        return f"{self.start:%b} {self.start.day}–{self.end:%b} {self.end.day}"


def estimated_tax_periods(year: int) -> tuple[TaxPeriod, ...]:
    return (
        TaxPeriod(1, date(year, 1, 1), date(year, 3, 31), date(year, 4, 15)),
        TaxPeriod(2, date(year, 4, 1), date(year, 5, 31), date(year, 6, 15)),
        TaxPeriod(3, date(year, 6, 1), date(year, 8, 31), date(year, 9, 15)),
        TaxPeriod(4, date(year, 9, 1), date(year, 12, 31), date(year + 1, 1, 15)),
    )


def cumulative(periods: Iterable[IncomeTotals]) -> list[IncomeTotals]:
    """Running totals through the end of each period."""
    running = IncomeTotals()
    result: list[IncomeTotals] = []
    for period in periods:
        running = running + period
        result.append(running)
    return result


def income_totals(
    sales: Iterable[Sale], dividends: Iterable[Dividend]
) -> IncomeTotals:
    by_term = {term: Decimal(0) for term in TERMS}
    for sale in sales:
        by_term[sale.term] += sale.gain
    paid = list(dividends)
    return IncomeTotals(
        short_term=by_term["short"],
        long_term=by_term["long"],
        unknown_term=by_term["unknown"],
        qualified=sum((item.qualified for item in paid), Decimal(0)),
        nonqualified=sum((item.nonqualified for item in paid), Decimal(0)),
        unclassified=sum((item.unclassified for item in paid), Decimal(0)),
        estimated_cash=sum(
            (item.amount for item in paid if not item.reinvested), Decimal(0)
        ),
    )


def dividends_by_symbol(dividends: Iterable[Dividend]) -> dict[str, IncomeTotals]:
    """Each symbol's dividends for the year, in symbol order."""
    grouped: dict[str, IncomeTotals] = {}
    for item in sorted(dividends, key=lambda value: value.symbol):
        grouped[item.symbol] = grouped.get(item.symbol, IncomeTotals()) + IncomeTotals(
            qualified=item.qualified, nonqualified=item.nonqualified,
            unclassified=item.unclassified,
            estimated_cash=Decimal(0) if item.reinvested else item.amount,
        )
    return grouped


def is_long_term(acquired: date, sold: date) -> bool:
    """Held more than one year: sold after the first anniversary of acquisition."""
    try:
        anniversary = acquired.replace(year=acquired.year + 1)
    except ValueError:
        # Acquired on February 29: the anniversary falls at the end of February.
        anniversary = date(acquired.year + 1, 3, 1)
    return sold > anniversary


def infer_term(sold: date, open_lot_dates: Iterable[date]) -> tuple[Term, str]:
    """Bound a sale's holding period by the oldest lot still open (see module doc)."""
    older = [acquired for acquired in open_lot_dates if acquired <= sold]
    if not older:
        return "unknown", NO_OLDER_LOT
    if is_long_term(min(older), sold):
        return "long", INFERRED_LONG
    return "unknown", YOUNG_OLDEST_LOT


def eastern_date(timestamp: str) -> date:
    """The US Eastern calendar date of an ISO 8601 timestamp."""
    return parse_timestamp(timestamp).astimezone(EASTERN).date()


def parse_timestamp(timestamp: str) -> datetime:
    moment = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    if moment.tzinfo is None:
        raise ValueError(f"timestamp without a timezone: {timestamp}")
    return moment


def decimal(value: object) -> Decimal:
    return Decimal(str(value).replace("$", "").replace(",", ""))


def text_field(record: JsonObject, name: str) -> str | None:
    value = record.get(name)
    return value if isinstance(value, str) and value else None


SellTimes = Mapping[str, list[tuple[str, datetime]]]

# One acquisition's share of a sale, as order-history replay recovers it:
# (acquired, quantity, cost per share).
ClosedPortion = tuple[date, Decimal, Decimal]


def equity_sell_times(orders: Iterable[JsonObject]) -> dict[str, list[tuple[str, datetime]]]:
    """Every moment each executed equity sell order was placed or executed."""
    times: dict[str, list[tuple[str, datetime]]] = {}
    for order in orders:
        symbol = text_field(order, "symbol")
        if order.get("side") != "sell" or symbol is None:
            continue
        if decimal(order.get("cumulative_quantity") or 0) <= 0:
            continue  # Nothing executed, so nothing was sold.
        stamps = [order.get("created_at"), order.get("last_transaction_at")]
        executions = order.get("executions")
        if isinstance(executions, list):
            stamps.extend(
                item.get("timestamp") for item in executions if isinstance(item, dict)
            )
        order_id = text_field(order, "id") or ""
        times.setdefault(symbol.upper(), []).extend(
            (order_id, parse_timestamp(stamp))
            for stamp in stamps if isinstance(stamp, str) and stamp
        )
    return times


def matching_sell_order(
    symbol: str, timestamp: str, sell_times: SellTimes
) -> str | None:
    """The id of the equity sell order a trade belongs to, if any."""
    moment = parse_timestamp(timestamp)
    return next(
        (order_id for order_id, candidate in sell_times.get(symbol.upper(), [])
         if abs(moment - candidate) <= MATCH_TOLERANCE),
        None,
    )


def is_equity_sale(symbol: str, timestamp: str, sell_times: SellTimes) -> bool:
    """Whether a trade is one of the account's equity sell orders.

    The trade history mixes equities, options, and crypto under bare symbols,
    and tickers collide across them (SUI is both a REIT and a coin), so the
    symbol alone cannot tell them apart; the time of the order can.
    """
    return matching_sell_order(symbol, timestamp, sell_times) is not None


def lot_dates(lots: Iterable[JsonObject]) -> list[date]:
    dates: list[date] = []
    for lot in lots:
        opened = text_field(lot, "open_date")
        if opened is not None:
            dates.append(date.fromisoformat(opened[:10]))
    return dates


def lot_quantities(lots: Iterable[JsonObject]) -> list[tuple[date, Decimal]]:
    """Each open lot's acquisition date and share count."""
    found: list[tuple[date, Decimal]] = []
    for lot in lots:
        opened = text_field(lot, "open_date")
        quantity = lot.get("quantity")
        if opened is not None and quantity is not None:
            found.append((date.fromisoformat(opened[:10]), decimal(quantity)))
    return found


def classify_sales(
    trades: Iterable[JsonObject],
    year: int,
    sell_times: SellTimes,
    open_lots: Mapping[str, list[date] | None],
    config: IncomeConfig,
    tax_advantaged: bool = False,
    closed_lots: Mapping[str, list[ClosedPortion]] | None = None,
) -> list[Sale]:
    """Turn `get_pnl_trade_history` records from one year into classified sales.

    `open_lots` maps an equity symbol to its open lot dates, or None when they
    could not be read. `closed_lots` maps a sell order id to the acquisitions
    it closed, where the order history could be replayed (see lots.py); a sale
    the open lots cannot settle is split by those instead. A tax-advantaged
    account's sales are left unclassified.
    """
    sales: list[Sale] = []
    for trade in trades:
        timestamp = text_field(trade, "timestamp")
        symbol = text_field(trade, "symbol")
        gain = trade.get("realized_gain")
        if timestamp is None or symbol is None or gain is None:
            continue
        when = eastern_date(timestamp)
        if when.year != year:
            continue
        symbol = symbol.upper()
        order_id = matching_sell_order(symbol, timestamp, sell_times)
        asset = EQUITY if order_id is not None else OTHER
        quantity = decimal(trade.get("quantity") or 0)
        price = decimal(trade.get("price") or 0)
        # An order without an id cannot be told apart from another one.
        portions = (closed_lots or {}).get(order_id) if order_id else None
        term: Term
        if tax_advantaged:
            term, reason = "unknown", TAX_ADVANTAGED
        elif asset == OTHER:
            term, reason = "unknown", NOT_EQUITY
        elif (dates := open_lots.get(symbol)) is None:
            term, reason = "unknown", LOTS_UNAVAILABLE
        else:
            term, reason = infer_term(when, dates)
        if term == "unknown" and not tax_advantaged and asset == EQUITY and portions:
            sales.extend(split_by_lots(
                when, symbol, quantity, price, decimal(gain), portions
            ))
            continue
        if (term == "unknown" and not tax_advantaged
                and symbol in config.holding_periods):
            term, reason = config.holding_periods[symbol], CONFIGURED
        sales.append(Sale(
            when=when, symbol=symbol, quantity=quantity, price=price,
            gain=decimal(gain), asset=asset, term=term, reason=reason,
        ))
    return sorted(sales, key=lambda sale: (sale.when, sale.symbol))


def split_by_lots(
    when: date, symbol: str, quantity: Decimal, price: Decimal, gain: Decimal,
    portions: Iterable[ClosedPortion],
) -> list[Sale]:
    """One sale per holding period among the lots it closed.

    Robinhood's gain stays the total. Each part gets the gain its own lots
    imply, and whatever that misses (fees, rounding) is shared by quantity.
    """
    closed = list(portions)
    replayed = sum((item[1] for item in closed), Decimal(0))
    # A trade can be one of several fills of its order; take its share.
    scale = quantity / replayed if replayed and quantity else Decimal(1)
    parts: dict[Term, list[Decimal]] = {}
    for acquired, shares, cost in closed:
        term: Term = "long" if is_long_term(acquired, when) else "short"
        bucket = parts.setdefault(term, [Decimal(0), Decimal(0)])
        bucket[0] += shares * scale
        bucket[1] += shares * scale * cost
    total = sum((bucket[0] for bucket in parts.values()), Decimal(0))
    implied = {term: price * bucket[0] - bucket[1] for term, bucket in parts.items()}
    missing = gain - sum(implied.values(), Decimal(0))
    sales: list[Sale] = []
    remaining = gain
    for index, (term, (shares, _)) in enumerate(sorted(parts.items())):
        last = index == len(parts) - 1
        part = remaining if last else (
            implied[term] + missing * shares / total).quantize(CENT)
        remaining -= part
        sales.append(Sale(
            when=when, symbol=symbol, quantity=shares.quantize(Decimal("0.000001")),
            price=price, gain=part, asset=EQUITY, term=term, reason=REPLAYED,
        ))
    return sales


def reinvested_dividends(
    orders: Iterable[JsonObject], year: int, config: IncomeConfig
) -> list[Dividend]:
    """Dividends from one year's filled DRIP purchases.

    A reinvestment buys exactly the dividend's cash, so the order's dollar
    amount is the payment. A dividend taken as cash leaves no order behind and
    is invisible here.
    """
    dividends: list[Dividend] = []
    for order in orders:
        symbol = text_field(order, "symbol")
        created = text_field(order, "created_at")
        if (order.get("placed_agent") != "drip" or order.get("side") != "buy"
                or order.get("state") != "filled" or symbol is None or created is None):
            continue
        when = eastern_date(created)
        if when.year != year:
            continue
        symbol = symbol.upper()
        dividends.append(Dividend(
            when=when, symbol=symbol, amount=order_amount(order),
            qualified_fraction=config.qualified_fractions.get(symbol),
        ))
    return sorted(dividends, key=lambda item: (item.when, item.symbol))


def order_amount(order: JsonObject) -> Decimal:
    dollars = order.get("dollar_based_amount")
    if isinstance(dollars, dict) and dollars.get("amount") is not None:
        return decimal(dollars["amount"]).quantize(CENT)
    quantity = order.get("cumulative_quantity") or order.get("quantity")
    price = order.get("average_price")
    if quantity is None or price is None:
        raise ValueError(
            f"DRIP order for {order.get('symbol')} has neither a dollar amount "
            "nor a filled quantity and price"
        )
    return (decimal(quantity) * decimal(price)).quantize(CENT)


def load_optional_config(path: str | None, default: str) -> IncomeConfig:
    """Load the named config, or the default one only if it exists."""
    if path is not None:
        return load_income_config(path)
    return load_income_config(default) if os.path.isfile(default) else IncomeConfig()


def load_income_config(path: str) -> IncomeConfig:
    if not path.lower().endswith((".yaml", ".yml")):
        raise ValueError("config path must end in .yaml or .yml")
    with open(path, encoding="utf-8") as stream:
        raw: object = yaml.safe_load(stream)
    if raw is None:
        return IncomeConfig()
    if not isinstance(raw, dict):
        raise ValueError("income config must be a YAML mapping")
    # PyYAML has no schema facility; parse_income_config validates every field.
    return parse_income_config(cast(IncomeConfigFile, raw))


def parse_income_config(raw: IncomeConfigFile) -> IncomeConfig:
    unknown = set(raw) - {"qualified_dividends", "holding_periods"}
    if unknown:
        raise ValueError(f"unknown income config fields: {', '.join(sorted(unknown))}")
    fractions = {
        str(symbol).upper(): qualified_fraction(symbol, value)
        for symbol, value in _mapping(raw, "qualified_dividends").items()
    }
    periods = {
        str(symbol).upper(): holding_period(symbol, value)
        for symbol, value in _mapping(raw, "holding_periods").items()
    }
    return IncomeConfig(qualified_fractions=fractions, holding_periods=periods)


def _mapping(raw: IncomeConfigFile, name: Literal[
    "qualified_dividends", "holding_periods"
]) -> dict[str, object]:
    value = raw.get(name) or {}
    if not isinstance(value, dict):
        raise ValueError(f"{name} must map symbols to values")
    return value


def qualified_fraction(symbol: object, value: object) -> Decimal:
    """A symbol's qualified share: a fraction, or `qualified` / `nonqualified`."""
    if value == "qualified":
        return Decimal(1)
    if value in ("nonqualified", "non-qualified", "ordinary"):
        return Decimal(0)
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError(
            f"qualified_dividends.{symbol} must be a fraction from 0 to 1, "
            "'qualified', or 'nonqualified'"
        )
    try:
        fraction = decimal(value)
    except ArithmeticError:
        fraction = Decimal(-1)
    if not Decimal(0) <= fraction <= Decimal(1):
        raise ValueError(f"qualified_dividends.{symbol} must be between 0 and 1")
    return fraction


def holding_period(symbol: object, value: object) -> Term:
    if value == "short" or value == "long":
        return value
    raise ValueError(f"holding_periods.{symbol} must be 'short' or 'long'")
