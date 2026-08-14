"""JSON serialization of a rebalance report for the single-page app.

Money crosses the wire as decimal strings, never as JSON numbers: the values are
exact cents and a float round-trip would not be. The browser parses them only to
format them for display.

Unlike the CLI's `--json`, `amount` keeps its sign. `action` still carries the
direction, so a client can use either.
"""

from datetime import datetime, timezone
from typing import Mapping, TypedDict

from examples.rebalance.core import Position, Recommendation
from examples.rebalance.report import AccountHoldings, PortfolioReport, Report


class PositionJson(TypedDict):
    symbol: str
    asset_class: str | None
    quantity: str
    price: str
    market_value: str


class AccountJson(TypedDict):
    label: str
    kind: str
    cash: str
    total_value: str
    positions: list[PositionJson]


class RecommendationJson(TypedDict):
    asset_class: str
    action: str
    amount: str
    current_value: str
    target_value: str
    ignored: bool


class PortfolioJson(TypedDict):
    name: str
    total_value: str
    target_cash: str
    minimum_trade: str
    accounts: list[AccountJson]
    recommendations: list[RecommendationJson]
    unclassified: list[PositionJson]


class ReportJson(TypedDict):
    generated_at: str
    demo: bool
    grand_total: str
    portfolios: list[PortfolioJson]


def report_json(report: Report, *, demo: bool = False,
                generated_at: datetime | None = None) -> ReportJson:
    moment = generated_at or datetime.now(timezone.utc)
    return {
        "generated_at": moment.isoformat(),
        # Travels with the data so a client cannot present invented numbers as
        # real ones by losing track of which request it made.
        "demo": demo,
        "grand_total": str(report.grand_total),
        "portfolios": [
            _portfolio_json(item, report.asset_classes) for item in report.portfolios
        ],
    }


def _portfolio_json(
    item: PortfolioReport, asset_classes: Mapping[str, str]
) -> PortfolioJson:
    return {
        "name": item.portfolio.name,
        "total_value": str(item.total_value),
        "target_cash": str(item.portfolio.target_cash),
        "minimum_trade": str(item.portfolio.minimum_trade),
        "accounts": [_account_json(account, asset_classes) for account in item.accounts],
        "recommendations": [
            _recommendation_json(entry) for entry in item.recommendations
        ],
        "unclassified": [
            _position_json(position, asset_classes)
            for position in item.unclassified(asset_classes)
        ],
    }


def _account_json(
    account: AccountHoldings, asset_classes: Mapping[str, str]
) -> AccountJson:
    return {
        "label": account.label,
        "kind": account.kind,
        "cash": str(account.cash),
        "total_value": str(account.total_value),
        "positions": [
            _position_json(position, asset_classes)
            for position in sorted(account.positions.values(),
                                   key=lambda item: item.symbol)
        ],
    }


def _position_json(
    position: Position, asset_classes: Mapping[str, str]
) -> PositionJson:
    return {
        "symbol": position.symbol,
        "asset_class": asset_classes.get(position.symbol),
        "quantity": str(position.quantity),
        "price": str(position.price),
        "market_value": str(position.market_value),
    }


def _recommendation_json(entry: Recommendation) -> RecommendationJson:
    return {
        "asset_class": entry.asset_class,
        "action": entry.action,
        "amount": str(entry.amount),
        "current_value": str(entry.current_value),
        "target_value": str(entry.target_value),
        "ignored": entry.ignored,
    }
