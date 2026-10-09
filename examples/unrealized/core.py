"""Unrealized gains: what each holding is worth now against what it cost.

Pure: it turns position, quote, and tax-lot records into gains and fetches
nothing. `report.py` does the fetching.

Cost basis comes from the open tax lots, which carry the basis Robinhood will
report on a 1099-B — including adjustments a plain average cost misses, such
as a disallowed wash-sale loss added to the replacement shares. Where a lot's
basis is still pending, the position falls back to Robinhood's average cost
and says so.

Each lot's holding period is Robinhood's own `term`, not one recomputed from
its acquisition date: a wash sale's replacement shares inherit the holding
period of the shares sold, and Robinhood reflects that in `term` while keeping
the purchase date as `open_date`.
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Iterable, Literal, Mapping

from hood_normie.types import JsonObject


BasisSource = Literal["tax lots", "average cost", "unavailable"]
Term = Literal["short", "long", "unknown"]
CENT = Decimal("0.01")


def decimal(value: object) -> Decimal:
    return Decimal(str(value).replace("$", "").replace(",", ""))


@dataclass(frozen=True)
class Lot:
    """One open tax lot: shares bought together, with their own basis and term."""

    acquired: date | None
    quantity: Decimal
    cost_basis: Decimal | None
    term: Term
    account_number: str = ""

    @property
    def long_term_on(self) -> date | None:
        """When a short-term lot goes long-term: the day after its anniversary.

        Counted from the purchase date, so a wash-sale replacement that
        inherited an older holding period may get there sooner.
        """
        if self.term != "short" or self.acquired is None:
            return None
        try:
            anniversary = self.acquired.replace(year=self.acquired.year + 1)
        except ValueError:  # February 29
            anniversary = date(self.acquired.year + 1, 3, 1)
        return date.fromordinal(anniversary.toordinal() + 1)

    def market_value(self, price: Decimal | None) -> Decimal | None:
        return None if price is None else (self.quantity * price).quantize(CENT)

    def unrealized(self, price: Decimal | None) -> Decimal | None:
        value = self.market_value(price)
        return None if value is None or self.cost_basis is None else value - self.cost_basis


@dataclass(frozen=True)
class Holding:
    """One position marked at the latest quote, against its cost basis."""

    symbol: str
    quantity: Decimal
    price: Decimal | None
    cost_basis: Decimal | None
    basis_source: BasisSource
    # Empty when the basis did not come from the lots.
    lots: tuple[Lot, ...] = field(default=(), compare=False)
    # The accounts the holding spans; one unless merged by `combine`.
    account_numbers: tuple[str, ...] = field(default=(), compare=False)

    @property
    def market_value(self) -> Decimal | None:
        if self.price is None:
            return None
        return (self.quantity * self.price).quantize(Decimal("0.01"))

    @property
    def unrealized(self) -> Decimal | None:
        if self.market_value is None or self.cost_basis is None:
            return None
        return self.market_value - self.cost_basis

    @property
    def return_rate(self) -> Decimal | None:
        """Unrealized gain as a fraction of cost; None without a positive cost."""
        if self.unrealized is None or not self.cost_basis or self.cost_basis <= 0:
            return None
        return self.unrealized / self.cost_basis

    @property
    def by_term(self) -> dict[Term, Decimal]:
        """Unrealized gain split by holding period.

        Each lot is marked at the holding's price; per-lot rounding that keeps
        the parts from adding to the holding's gain goes to the largest part.
        Without lot bases the whole gain is unknown-term.
        """
        split: dict[Term, Decimal] = {"short": Decimal(0), "long": Decimal(0),
                                      "unknown": Decimal(0)}
        gain = self.unrealized
        if gain is None:
            return split
        if self.basis_source != "tax lots" or not self.lots:
            split["unknown"] = gain
            return split
        for lot in self.lots:
            split[lot.term] += lot.unrealized(self.price) or Decimal(0)
        largest = max(split, key=lambda term: abs(split[term]))
        split[largest] += gain - sum(split.values(), Decimal(0))
        return split

    @property
    def next_long_term(self) -> date | None:
        """The earliest date a short-term lot of this holding goes long-term."""
        dates = [lot.long_term_on for lot in self.lots if lot.long_term_on]
        return min(dates) if dates else None


@dataclass(frozen=True)
class Totals:
    """Sums over holdings that have both a price and a basis.

    `incomplete` counts the holdings left out, so a total never quietly omits
    a position.
    """

    market_value: Decimal = Decimal(0)
    cost_basis: Decimal = Decimal(0)
    incomplete: int = 0
    short_term: Decimal = Decimal(0)
    long_term: Decimal = Decimal(0)
    unknown_term: Decimal = Decimal(0)

    @property
    def unrealized(self) -> Decimal:
        return self.market_value - self.cost_basis

    @property
    def return_rate(self) -> Decimal | None:
        return self.unrealized / self.cost_basis if self.cost_basis > 0 else None


def totals(holdings: Iterable[Holding]) -> Totals:
    value = basis = Decimal(0)
    split: dict[Term, Decimal] = {"short": Decimal(0), "long": Decimal(0),
                                  "unknown": Decimal(0)}
    incomplete = 0
    for holding in holdings:
        if holding.market_value is None or holding.cost_basis is None:
            incomplete += 1
            continue
        value += holding.market_value
        basis += holding.cost_basis
        for term, amount in holding.by_term.items():
            split[term] += amount
    return Totals(market_value=value, cost_basis=basis, incomplete=incomplete,
                  short_term=split["short"], long_term=split["long"],
                  unknown_term=split["unknown"])


@dataclass(frozen=True)
class AccountUnrealized:
    label: str
    account_number: str
    tax_advantaged: bool
    holdings: tuple[Holding, ...]

    @property
    def totals(self) -> Totals:
        return totals(self.holdings)


@dataclass(frozen=True)
class UnrealizedReport:
    accounts: tuple[AccountUnrealized, ...]

    @property
    def taxable(self) -> tuple[AccountUnrealized, ...]:
        """Accounts whose gains will be taxed when realized; IRAs are not."""
        return tuple(item for item in self.accounts if not item.tax_advantaged)

    @property
    def combined(self) -> tuple[Holding, ...]:
        """Taxable holdings merged by symbol across accounts."""
        return combine(holding for account in self.taxable
                       for holding in account.holdings)

    @property
    def taxable_totals(self) -> Totals:
        return totals(self.combined)


def combine(holdings: Iterable[Holding]) -> tuple[Holding, ...]:
    """Merge holdings of the same symbol, adding quantities and bases.

    A merged holding has a basis only if every part had one; its source is the
    weakest of its parts'.
    """
    order: tuple[BasisSource, ...] = ("tax lots", "average cost", "unavailable")
    merged: dict[str, Holding] = {}
    for holding in holdings:
        current = merged.get(holding.symbol)
        if current is None:
            merged[holding.symbol] = holding
            continue
        basis = (None if current.cost_basis is None or holding.cost_basis is None
                 else current.cost_basis + holding.cost_basis)
        merged[holding.symbol] = Holding(
            symbol=holding.symbol,
            quantity=current.quantity + holding.quantity,
            price=current.price if current.price is not None else holding.price,
            cost_basis=basis,
            basis_source=max(current.basis_source, holding.basis_source,
                             key=order.index),
            lots=current.lots + holding.lots,
            account_numbers=current.account_numbers + holding.account_numbers,
        )
    return tuple(sorted(merged.values(), key=lambda item: item.symbol))


def cost_basis(lots: Iterable[JsonObject], position: JsonObject,
               quantity: Decimal) -> tuple[Decimal | None, BasisSource]:
    """A position's basis from its lots, or its average cost if any lot is pending."""
    records = list(lots)
    bases = [lot.get("tax_cost_basis") for lot in records]
    lot_quantity = sum((decimal(lot.get("quantity") or 0) for lot in records), Decimal(0))
    if (records and all(value not in (None, "") for value in bases)
            and abs(lot_quantity - quantity) <= Decimal("0.000001")):
        # Robinhood writes bases to six places; a basis is whole cents.
        total = sum((decimal(value) for value in bases), Decimal(0))
        return total.quantize(CENT), "tax lots"
    average = position.get("average_buy_price")
    if average not in (None, ""):
        return (decimal(average) * quantity).quantize(Decimal("0.01")), "average cost"
    return None, "unavailable"


TERMS: Mapping[str, Term] = {"st": "short", "lt": "long",
                             "short": "short", "long": "long"}


def parse_lots(records: Iterable[JsonObject], account_number: str = "") -> tuple[Lot, ...]:
    """Robinhood's lot records, oldest first."""
    lots: list[Lot] = []
    for record in records:
        opened = record.get("open_date")
        basis = record.get("tax_cost_basis")
        lots.append(Lot(
            acquired=date.fromisoformat(str(opened)[:10]) if opened else None,
            quantity=decimal(record.get("quantity") or 0),
            cost_basis=None if basis in (None, "") else decimal(basis).quantize(CENT),
            term=TERMS.get(str(record.get("term") or "").lower(), "unknown"),
            account_number=account_number,
        ))
    return tuple(sorted(lots, key=lambda lot: lot.acquired or date.max))


def holding(position: JsonObject, lots: Iterable[JsonObject],
            prices: Mapping[str, object], account_number: str = "") -> Holding:
    symbol = str(position["symbol"]).upper()
    quantity = decimal(position["quantity"])
    records = list(lots)
    basis, source = cost_basis(records, position, quantity)
    price = prices.get(symbol)
    return Holding(
        symbol=symbol, quantity=quantity,
        price=None if price is None else decimal(price),
        cost_basis=basis, basis_source=source,
        lots=parse_lots(records, account_number) if source == "tax lots" else (),
        account_numbers=(account_number,) if account_number else (),
    )
