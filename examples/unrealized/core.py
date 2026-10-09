"""Unrealized gains: what each holding is worth now against what it cost.

Pure: it turns position, quote, and tax-lot records into gains and fetches
nothing. `report.py` does the fetching.

Cost basis comes from the open tax lots, which carry the basis Robinhood will
report on a 1099-B — including adjustments a plain average cost misses, such
as a disallowed wash-sale loss added to the replacement shares. Where a lot's
basis is still pending, the position falls back to Robinhood's average cost
and says so. Holding periods are not considered here.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Literal, Mapping

from hood_normie.types import JsonObject


BasisSource = Literal["tax lots", "average cost", "unavailable"]


def decimal(value: object) -> Decimal:
    return Decimal(str(value).replace("$", "").replace(",", ""))


@dataclass(frozen=True)
class Holding:
    """One position marked at the latest quote, against its cost basis."""

    symbol: str
    quantity: Decimal
    price: Decimal | None
    cost_basis: Decimal | None
    basis_source: BasisSource

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


@dataclass(frozen=True)
class Totals:
    """Sums over holdings that have both a price and a basis.

    `incomplete` counts the holdings left out, so a total never quietly omits
    a position.
    """

    market_value: Decimal = Decimal(0)
    cost_basis: Decimal = Decimal(0)
    incomplete: int = 0

    @property
    def unrealized(self) -> Decimal:
        return self.market_value - self.cost_basis

    @property
    def return_rate(self) -> Decimal | None:
        return self.unrealized / self.cost_basis if self.cost_basis > 0 else None


def totals(holdings: Iterable[Holding]) -> Totals:
    value = basis = Decimal(0)
    incomplete = 0
    for holding in holdings:
        if holding.market_value is None or holding.cost_basis is None:
            incomplete += 1
            continue
        value += holding.market_value
        basis += holding.cost_basis
    return Totals(market_value=value, cost_basis=basis, incomplete=incomplete)


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
        return sum((decimal(value) for value in bases), Decimal(0)), "tax lots"
    average = position.get("average_buy_price")
    if average not in (None, ""):
        return (decimal(average) * quantity).quantize(Decimal("0.01")), "average cost"
    return None, "unavailable"


def holding(position: JsonObject, lots: Iterable[JsonObject],
            prices: Mapping[str, object]) -> Holding:
    symbol = str(position["symbol"]).upper()
    quantity = decimal(position["quantity"])
    basis, source = cost_basis(lots, position, quantity)
    price = prices.get(symbol)
    return Holding(
        symbol=symbol, quantity=quantity,
        price=None if price is None else decimal(price),
        cost_basis=basis, basis_source=source,
    )
