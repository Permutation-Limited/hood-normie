"""Pure portfolio rebalancing calculations."""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable, Mapping


CENT = Decimal("0.01")
SHARE = Decimal("0.000001")


def decimal(value: object) -> Decimal:
    """Convert broker/config values to Decimal without binary-float noise."""
    return Decimal(str(value).replace("$", "").replace(",", ""))


@dataclass(frozen=True)
class Target:
    symbol: str
    weight: Decimal
    asset_class: str


@dataclass(frozen=True)
class Position:
    symbol: str
    quantity: Decimal
    price: Decimal

    @property
    def market_value(self) -> Decimal:
        return self.quantity * self.price


@dataclass(frozen=True)
class Recommendation:
    symbol: str
    asset_class: str
    current_value: Decimal
    target_value: Decimal
    amount: Decimal
    price: Decimal
    shares: Decimal

    @property
    def action(self) -> str:
        if self.amount > 0:
            return "BUY"
        if self.amount < 0:
            return "SELL"
        return "HOLD"


def validate_targets(targets: Iterable[Target]) -> list[Target]:
    result = list(targets)
    if not result:
        raise ValueError("at least one target is required")
    symbols = [target.symbol for target in result]
    if len(symbols) != len(set(symbols)):
        raise ValueError("target symbols must be unique")
    if any(target.weight < 0 for target in result):
        raise ValueError("target weights cannot be negative")
    total = sum((target.weight for target in result), Decimal(0))
    if abs(total - Decimal(1)) > Decimal("0.000001"):
        raise ValueError(f"target weights must sum to 1; got {total}")
    return result


def calculate(
    *,
    net_liquidation_value: Decimal,
    target_cash: Decimal,
    targets: Iterable[Target],
    positions: Mapping[str, Position],
    prices: Mapping[str, Decimal],
    minimum_trade: Decimal = Decimal(0),
    liquidate_unconfigured: bool = False,
) -> list[Recommendation]:
    """Return dollar/share deltas needed to reach the configured allocation.

    Weights apply to invested value, not net liquidation value. Thus a negative
    target_cash deliberately makes invested value greater than account equity.
    """
    checked_targets = validate_targets(targets)
    invested_target = net_liquidation_value - target_cash
    if invested_target < 0:
        raise ValueError("target cash cannot exceed net liquidation value")

    recommendations: list[Recommendation] = []
    target_symbols = {target.symbol for target in checked_targets}
    for target in checked_targets:
        position = positions.get(target.symbol)
        price = prices.get(target.symbol) or (position.price if position else None)
        if price is None or price <= 0:
            raise ValueError(f"missing positive price for {target.symbol}")
        current = position.market_value if position else Decimal(0)
        desired = invested_target * target.weight
        amount = desired - current
        if abs(amount) < minimum_trade:
            amount = Decimal(0)
        recommendations.append(_recommendation(target, current, desired, amount, price))

    if liquidate_unconfigured:
        for symbol, position in positions.items():
            if symbol not in target_symbols and position.market_value != 0:
                recommendations.append(_recommendation(
                    Target(symbol, Decimal(0), "unconfigured"),
                    position.market_value,
                    Decimal(0),
                    -position.market_value,
                    position.price,
                ))
    return sorted(recommendations, key=lambda item: item.symbol)


def _recommendation(
    target: Target,
    current: Decimal,
    desired: Decimal,
    amount: Decimal,
    price: Decimal,
) -> Recommendation:
    rounded_amount = amount.quantize(CENT, rounding=ROUND_HALF_UP)
    shares = (rounded_amount / price).quantize(SHARE, rounding=ROUND_HALF_UP)
    return Recommendation(
        symbol=target.symbol,
        asset_class=target.asset_class,
        current_value=current.quantize(CENT, rounding=ROUND_HALF_UP),
        target_value=desired.quantize(CENT, rounding=ROUND_HALF_UP),
        amount=rounded_amount,
        price=price,
        shares=shares,
    )

