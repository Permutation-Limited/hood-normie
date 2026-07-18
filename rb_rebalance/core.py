"""Pure portfolio rebalancing calculations."""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable, Mapping


CENT = Decimal("0.01")


def decimal(value: object) -> Decimal:
    """Convert broker/config values to Decimal without binary-float noise."""
    return Decimal(str(value).replace("$", "").replace(",", ""))


@dataclass(frozen=True)
class ClassTarget:
    name: str
    weight: Decimal


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
    asset_class: str
    current_value: Decimal
    target_value: Decimal
    amount: Decimal

    @property
    def action(self) -> str:
        if self.amount > 0:
            return "BUY"
        if self.amount < 0:
            return "SELL"
        return "HOLD"


def validate_targets(targets: Iterable[ClassTarget]) -> list[ClassTarget]:
    result = list(targets)
    if not result:
        raise ValueError("at least one target is required")
    names = [target.name for target in result]
    if len(names) != len(set(names)):
        raise ValueError("class names must be unique")
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
    targets: Iterable[ClassTarget],
    asset_classes: Mapping[str, str],
    positions: Mapping[str, Position],
    minimum_trade: Decimal = Decimal(0),
) -> list[Recommendation]:
    """Return class-level dollar deltas needed to reach the allocation.

    Weights apply to invested value, not net liquidation value. Thus a negative
    target_cash deliberately makes invested value greater than account equity.
    """
    checked_targets = validate_targets(targets)
    invested_target = net_liquidation_value - target_cash
    if invested_target < 0:
        raise ValueError("target cash cannot exceed net liquidation value")

    class_names = {target.name for target in checked_targets}
    unknown_classes = sorted(set(asset_classes.values()) - class_names)
    if unknown_classes:
        raise ValueError(f"assets reference undefined classes: {', '.join(unknown_classes)}")
    unmapped = sorted(symbol for symbol in positions if symbol not in asset_classes)
    if unmapped:
        raise ValueError(
            "held symbols are missing from assets config: " + ", ".join(unmapped)
        )

    current_by_class = {name: Decimal(0) for name in class_names}
    for symbol, position in positions.items():
        current_by_class[asset_classes[symbol]] += position.market_value

    recommendations: list[Recommendation] = []
    for target in checked_targets:
        current = current_by_class[target.name]
        desired = invested_target * target.weight
        amount = desired - current
        if abs(amount) < minimum_trade:
            amount = Decimal(0)
        recommendations.append(_recommendation(target, current, desired, amount))
    return sorted(recommendations, key=lambda item: item.asset_class)


def _recommendation(
    target: ClassTarget,
    current: Decimal,
    desired: Decimal,
    amount: Decimal,
) -> Recommendation:
    rounded_amount = amount.quantize(CENT, rounding=ROUND_HALF_UP)
    return Recommendation(
        asset_class=target.name,
        current_value=current.quantize(CENT, rounding=ROUND_HALF_UP),
        target_value=desired.quantize(CENT, rounding=ROUND_HALF_UP),
        amount=rounded_amount,
    )
