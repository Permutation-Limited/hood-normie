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
    weight: Decimal | None = None
    target_amount: Decimal | None = None


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
    if any(target.weight is not None and target.weight < 0 for target in result):
        raise ValueError("target weights cannot be negative")
    if any(target.target_amount is not None and target.target_amount < 0 for target in result):
        raise ValueError("class target amounts cannot be negative")
    variable = [target for target in result if target.target_amount is None]
    if any(target.weight is None for target in variable):
        missing = ", ".join(target.name for target in variable if target.weight is None)
        raise ValueError(f"classes without target_amount require weight: {missing}")
    variable_weight = sum((target.weight for target in variable), Decimal(0))
    if variable and variable_weight <= 0:
        raise ValueError("percentage-targeted class weights must total more than zero")
    if len(variable) == len(result) and abs(variable_weight - Decimal(1)) > Decimal("0.000001"):
        raise ValueError(f"target weights must sum to 1; got {variable_weight}")
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

    fixed_total = sum(
        (target.target_amount for target in checked_targets
         if target.target_amount is not None),
        Decimal(0),
    )
    remaining_target = invested_target - fixed_total
    if remaining_target < 0:
        raise ValueError(
            f"fixed class targets ({fixed_total}) exceed investable target ({invested_target})"
        )
    variable_targets = [
        target for target in checked_targets if target.target_amount is None
    ]
    variable_weight = sum((target.weight for target in variable_targets), Decimal(0))
    if not variable_targets and remaining_target != 0:
        raise ValueError(
            "fixed class targets do not consume the investable target and no "
            "percentage-targeted class can receive the remainder"
        )

    class_names = {target.name for target in checked_targets}
    unknown_classes = sorted(set(asset_classes.values()) - class_names)
    if unknown_classes:
        raise ValueError(f"assets reference undefined classes: {', '.join(unknown_classes)}")
    current_by_class = {name: Decimal(0) for name in class_names}
    for symbol, position in positions.items():
        asset_class = asset_classes.get(symbol)
        if asset_class is not None:
            current_by_class[asset_class] += position.market_value

    recommendations: list[Recommendation] = []
    for target in checked_targets:
        current = current_by_class[target.name]
        desired = (target.target_amount if target.target_amount is not None else
                   remaining_target * target.weight / variable_weight)
        amount = desired - current
        if abs(amount) < minimum_trade:
            amount = Decimal(0)
        recommendations.append(_recommendation(target, current, desired, amount))
    return sorted(recommendations, key=lambda item: item.asset_class)


def calculate_cash(
    *, net_liquidation_value: Decimal, target_cash: Decimal,
    positions: Mapping[str, Position], minimum_trade: Decimal = Decimal(0),
) -> Recommendation:
    """Return the implicit cash-class change after accounting for all assets."""
    current_cash = net_liquidation_value - sum(
        (position.market_value for position in positions.values()), Decimal(0)
    )
    amount = target_cash - current_cash
    if abs(amount) < minimum_trade:
        amount = Decimal(0)
    return Recommendation(
        asset_class="cash",
        current_value=current_cash.quantize(CENT, rounding=ROUND_HALF_UP),
        target_value=target_cash.quantize(CENT, rounding=ROUND_HALF_UP),
        amount=amount.quantize(CENT, rounding=ROUND_HALF_UP),
    )


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
