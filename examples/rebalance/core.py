"""Pure portfolio rebalancing calculations for the example application."""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable, Mapping, NotRequired, Required, TypedDict, cast

import yaml


CENT = Decimal("0.01")

NumericInput = str | int | float


class ClassConfig(TypedDict):
    name: Required[str]
    weight: NotRequired[NumericInput | None]
    target_amount: NotRequired[NumericInput | None]
    ignore: NotRequired[bool]


AssetConfig = TypedDict("AssetConfig", {"symbol": str, "class": str})


class ExternalAssetConfig(TypedDict):
    symbol: str
    quantity: NumericInput


class ExternalAccountConfig(TypedDict):
    name: str
    cash: NotRequired[NumericInput]
    assets: NotRequired[list[ExternalAssetConfig]]


class AccountSelectionConfig(TypedDict):
    robinhood_account_numbers: NotRequired[list[str | int]]
    account_number: NotRequired[str | int]


class PortfolioConfig(AccountSelectionConfig):
    name: Required[str]
    classes: Required[list[ClassConfig]]
    target_cash: NotRequired[NumericInput]
    minimum_trade: NotRequired[NumericInput]
    external_accounts: NotRequired[list[ExternalAccountConfig]]


class RebalanceConfig(TypedDict):
    assets: Required[list[AssetConfig]]
    portfolios: Required[list[PortfolioConfig]]
    # Retired schemas, detected only to produce an explicit migration error.
    classes: NotRequired[object]
    targets: NotRequired[object]
    robinhood_account_numbers: NotRequired[object]
    account_number: NotRequired[object]
    target_cash: NotRequired[object]
    minimum_trade: NotRequired[object]
    external_accounts: NotRequired[object]


# Fields that belonged to the retired single-portfolio schema and now live on
# each entry of the top-level portfolios list.
PORTFOLIO_FIELDS = (
    "classes", "robinhood_account_numbers", "account_number", "target_cash",
    "minimum_trade", "external_accounts",
)


def load_config(path: str) -> RebalanceConfig:
    """Load a YAML mapping from an explicitly YAML-named config file."""
    if not path.lower().endswith((".yaml", ".yml")):
        raise ValueError("config path must end in .yaml or .yml")
    with open(path, encoding="utf-8") as stream:
        raw_config: object = yaml.safe_load(stream)
    if not isinstance(raw_config, dict):
        raise ValueError("config must be a YAML mapping")
    # PyYAML has no schema facility. This cast is confined to the deserialization
    # boundary; callers use the explicit configuration schema above.
    return cast(RebalanceConfig, raw_config)


def decimal(value: object) -> Decimal:
    """Convert broker/config values to Decimal without binary-float noise."""
    return Decimal(str(value).replace("$", "").replace(",", ""))


def configured_account_numbers(config: AccountSelectionConfig) -> list[str]:
    """Return configured brokerage accounts from the plural config field."""
    if "account_number" in config:
        raise ValueError(
            "config field account_number is no longer supported; use "
            "robinhood_account_numbers"
        )
    return [str(value) for value in config.get("robinhood_account_numbers", [])]


@dataclass(frozen=True)
class ClassTarget:
    name: str
    weight: Decimal | None = None
    target_amount: Decimal | None = None
    ignore: bool = False


@dataclass(frozen=True)
class Portfolio:
    """One independently rebalanced set of accounts and class targets."""

    name: str
    targets: tuple[ClassTarget, ...]
    account_numbers: tuple[str, ...] = ()
    external_accounts: tuple[ExternalAccountConfig, ...] = ()
    target_cash: Decimal = Decimal(0)
    minimum_trade: Decimal = Decimal(0)

    @property
    def external_symbols(self) -> set[str]:
        return {
            item["symbol"].upper()
            for account in self.external_accounts
            for item in account.get("assets", [])
        }


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
    ignored: bool = False

    @property
    def action(self) -> str:
        if self.ignored:
            return ""
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
    ignored = [target for target in result if target.ignore]
    if any(target.target_amount is not None for target in ignored):
        raise ValueError("ignored classes cannot have target_amount")
    active = [target for target in result if not target.ignore]
    if not active:
        raise ValueError("at least one non-ignored class is required")
    variable = [target for target in active if target.target_amount is None]
    if any(target.weight is None for target in variable):
        missing = ", ".join(target.name for target in variable if target.weight is None)
        raise ValueError(f"classes without target_amount require weight: {missing}")
    variable_weight = sum((_required_weight(target) for target in variable), Decimal(0))
    if variable and variable_weight <= 0:
        raise ValueError("percentage-targeted class weights must total more than zero")
    if len(variable) == len(active) and abs(variable_weight - Decimal(1)) > Decimal("0.000001"):
        raise ValueError(f"target weights must sum to 1; got {variable_weight}")
    return result


def parse_asset_classes(config: RebalanceConfig) -> dict[str, str]:
    """Return the global symbol-to-class map shared by every portfolio."""
    if "assets" not in config:
        raise ValueError("config must contain a top-level assets section")
    entries = config["assets"]
    asset_classes = {item["symbol"].upper(): item["class"] for item in entries}
    if len(asset_classes) != len(entries):
        raise ValueError("asset symbols must be unique")
    return asset_classes


def parse_portfolios(
    config: RebalanceConfig, asset_classes: Mapping[str, str]
) -> list[Portfolio]:
    """Return every configured portfolio, validated against the global assets."""
    if "portfolios" not in config:
        if "targets" in config:
            raise ValueError(
                "config uses the old per-symbol targets schema; replace it with "
                "a top-level assets section and a portfolios list "
                "(see examples/rebalance/config.example.yaml)"
            )
        moved = [field for field in PORTFOLIO_FIELDS if field in config]
        if moved:
            raise ValueError(
                "config uses the old single-portfolio schema; move "
                f"{', '.join(moved)} into an entry of a top-level portfolios list "
                "(see examples/rebalance/config.example.yaml)"
            )
        raise ValueError("config must contain a top-level portfolios section")
    entries = config["portfolios"]
    if not isinstance(entries, list) or not entries:
        raise ValueError("portfolios must be a non-empty list")
    portfolios = [_parse_portfolio(entry, asset_classes) for entry in entries]
    names = [portfolio.name for portfolio in portfolios]
    if len(names) != len(set(names)):
        raise ValueError("portfolio names must be unique")
    owner: dict[str, str] = {}
    for portfolio in portfolios:
        for number in portfolio.account_numbers:
            if number in owner:
                raise ValueError(
                    f"Robinhood account {number} is listed in both portfolio "
                    f"{owner[number]} and portfolio {portfolio.name}"
                )
            owner[number] = portfolio.name
    return portfolios


def _parse_portfolio(
    entry: PortfolioConfig, asset_classes: Mapping[str, str]
) -> Portfolio:
    if "name" not in entry:
        raise ValueError("every portfolio requires a name")
    name = str(entry["name"])
    if "classes" not in entry:
        raise ValueError(f"portfolio {name} must contain a classes section")
    declared = [ClassTarget(
        name=item["name"],
        weight=decimal(item["weight"]) if item.get("weight") is not None else None,
        target_amount=(decimal(item["target_amount"])
                       if item.get("target_amount") is not None else None),
        ignore=bool(item.get("ignore", False)),
    ) for item in entry["classes"]]
    # Classification is global, so a portfolio need only name the classes it has
    # an opinion about. The rest target $0 here: held value still counts and the
    # plan sells it. Declare the class with ignore: true to exclude it instead.
    undeclared = sorted(set(asset_classes.values()) - {t.name for t in declared})
    targets = validate_targets(declared + [
        ClassTarget(name=class_name, target_amount=Decimal(0))
        for class_name in undeclared
    ])
    external_accounts = list(entry.get("external_accounts", []))
    external_names = [account["name"] for account in external_accounts]
    if len(external_names) != len(set(external_names)):
        raise ValueError(f"external account names must be unique in portfolio {name}")
    return Portfolio(
        name=name,
        targets=tuple(targets),
        account_numbers=tuple(configured_account_numbers(entry)),
        external_accounts=tuple(external_accounts),
        target_cash=decimal(entry.get("target_cash", 0)),
        minimum_trade=decimal(entry.get("minimum_trade", 0)),
    )


def calculate(
    *,
    current_cash: Decimal,
    target_cash: Decimal,
    targets: Iterable[ClassTarget],
    asset_classes: Mapping[str, str],
    positions: Mapping[str, Position],
    minimum_trade: Decimal = Decimal(0),
) -> list[Recommendation]:
    """Return class-level dollar deltas needed to reach the allocation.

    Weights apply to invested value, not account equity. Account equity is
    derived from the same marked positions and reported cash used by the
    recommendations, so the resulting trades reconcile to the cash change.
    Thus a negative target_cash deliberately creates margin exposure.
    """
    checked_targets = validate_targets(targets)
    class_names = {target.name for target in checked_targets}
    ignored_classes = {target.name for target in checked_targets if target.ignore}
    ignored_value = sum(
        (position.market_value for symbol, position in positions.items()
         if asset_classes.get(symbol) in ignored_classes or symbol not in asset_classes),
        Decimal(0),
    )
    marked_position_value = sum(
        (position.market_value for position in positions.values()), Decimal(0)
    )
    marked_account_equity = marked_position_value + current_cash
    invested_target = marked_account_equity - target_cash - ignored_value
    if invested_target < 0:
        raise ValueError(
            "target cash plus ignored assets cannot exceed marked account equity"
        )

    fixed_total = sum(
        (target.target_amount for target in checked_targets
         if not target.ignore and target.target_amount is not None),
        Decimal(0),
    )
    remaining_target = invested_target - fixed_total
    if remaining_target < 0:
        raise ValueError(
            f"fixed class targets ({fixed_total}) exceed investable target ({invested_target})"
        )
    variable_targets = [
        target for target in checked_targets
        if not target.ignore and target.target_amount is None
    ]
    variable_weight = sum(
        (_required_weight(target) for target in variable_targets), Decimal(0)
    )
    if not variable_targets and remaining_target != 0:
        raise ValueError(
            "fixed class targets do not consume the investable target and no "
            "percentage-targeted class can receive the remainder"
        )

    unknown_classes = sorted(set(asset_classes.values()) - class_names)
    if unknown_classes:
        raise ValueError(f"assets reference undefined classes: {', '.join(unknown_classes)}")
    current_by_class = {target.name: Decimal(0) for target in checked_targets}
    unclassified_value = Decimal(0)
    for symbol, position in positions.items():
        asset_class = asset_classes.get(symbol)
        if asset_class is not None:
            current_by_class[asset_class] += position.market_value
        else:
            unclassified_value += position.market_value

    recommendations: list[Recommendation] = []
    for target in checked_targets:
        if target.ignore:
            current = current_by_class[target.name]
            recommendations.append(_recommendation(
                target, current, current, Decimal(0), ignored=True
            ))
            continue
        current = current_by_class[target.name]
        desired = (target.target_amount if target.target_amount is not None else
                   remaining_target * _required_weight(target) / variable_weight)
        amount = desired - current
        if abs(amount) < minimum_trade:
            amount = Decimal(0)
        recommendations.append(_recommendation(target, current, desired, amount))
    if unclassified_value != 0:
        recommendations.append(Recommendation(
            asset_class="unclassified",
            current_value=unclassified_value.quantize(CENT, rounding=ROUND_HALF_UP),
            target_value=unclassified_value.quantize(CENT, rounding=ROUND_HALF_UP),
            amount=Decimal(0).quantize(CENT),
            ignored=True,
        ))
    return sorted(
        recommendations,
        key=lambda item: (
            item.ignored,
            item.asset_class == "unclassified",
            item.asset_class,
        ),
    )


def _required_weight(target: ClassTarget) -> Decimal:
    if target.weight is None:
        raise ValueError(f"class {target.name} requires a weight")
    return target.weight


def calculate_cash(
    *, current_cash: Decimal, target_cash: Decimal,
    minimum_trade: Decimal = Decimal(0),
) -> Recommendation:
    """Return the cash change using the broker-reported current cash value."""
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
    ignored: bool = False,
) -> Recommendation:
    rounded_amount = amount.quantize(CENT, rounding=ROUND_HALF_UP)
    return Recommendation(
        asset_class=target.name,
        current_value=current.quantize(CENT, rounding=ROUND_HALF_UP),
        target_value=desired.quantize(CENT, rounding=ROUND_HALF_UP),
        amount=rounded_amount,
        ignored=ignored,
    )
