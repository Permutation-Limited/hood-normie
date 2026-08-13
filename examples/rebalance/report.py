"""Portfolio reports shared by the command-line rebalancer and the web API.

Everything between loading the config and rendering lives here, so the terminal
report and the browser see the same numbers from the same code path. Rendering
itself does not: `main.py` prints tables, `webapp/api.py` serializes JSON.
"""

from dataclasses import dataclass
from decimal import Decimal
import os
from typing import Mapping, Protocol, Sequence

from examples.rebalance.core import (
    Portfolio, Position, Recommendation, calculate, calculate_cash, decimal,
    load_config, parse_asset_classes, parse_portfolios,
)
from hood_normie import RobinhoodClient
from hood_normie.client import NormalizedPosition, PortfolioSnapshot


DEFAULT_ENDPOINT = "https://agent.robinhood.com/mcp/trading"

ROBINHOOD = "robinhood"
EXTERNAL = "external"


class Fetcher(Protocol):
    """Retrieves a portfolio snapshot; substituted in tests to avoid network."""

    def __call__(self, *, endpoint: str, account_numbers: list[str],
                 symbols: list[str], token_file: str,
                 verbose: bool) -> PortfolioSnapshot: ...


@dataclass(frozen=True)
class AccountHoldings:
    """One account's marked positions and cash, before aggregation."""

    label: str
    kind: str
    positions: dict[str, Position]
    cash: Decimal

    @property
    def market_value(self) -> Decimal:
        return sum(
            (position.market_value for position in self.positions.values()), Decimal(0)
        )

    @property
    def total_value(self) -> Decimal:
        return self.market_value + self.cash


@dataclass(frozen=True)
class PortfolioReport:
    """A portfolio's holdings and the plan computed from them."""

    portfolio: Portfolio
    accounts: tuple[AccountHoldings, ...]
    positions: Mapping[str, Position]
    recommendations: tuple[Recommendation, ...]

    @property
    def total_value(self) -> Decimal:
        return sum((account.total_value for account in self.accounts), Decimal(0))

    def unclassified(self, asset_classes: Mapping[str, str]) -> list[Position]:
        """Held symbols with no class, which the allocation math leaves out."""
        return sorted(
            (position for symbol, position in self.positions.items()
             if symbol not in asset_classes),
            key=lambda position: position.symbol,
        )


@dataclass(frozen=True)
class Report:
    asset_classes: dict[str, str]
    portfolios: tuple[PortfolioReport, ...]

    @property
    def grand_total(self) -> Decimal:
        return sum((report.total_value for report in self.portfolios), Decimal(0))


def fetch_portfolios(*, endpoint: str, account_numbers: list[str],
                     symbols: list[str], token_file: str,
                     verbose: bool = False) -> PortfolioSnapshot:
    token = os.environ.get("ROBINHOOD_MCP_TOKEN")
    client = (RobinhoodClient(token, endpoint=endpoint, verbose=verbose) if token else
              RobinhoodClient.from_token_file(
                  token_file, endpoint=endpoint, verbose=verbose
              ))
    return client.fetch_portfolios(account_numbers, symbols)


def build_report(
    *, config_path: str, token_file: str, endpoint: str = DEFAULT_ENDPOINT,
    portfolio_names: Sequence[str] | None = None,
    account_numbers: Sequence[str] | None = None,
    verbose: bool = False,
    fetch: Fetcher | None = None,
) -> Report:
    """Load the config, fetch live data once, and compute every portfolio's plan."""
    config = load_config(config_path)
    asset_classes = parse_asset_classes(config)
    portfolios = select_portfolios(
        parse_portfolios(config, asset_classes), portfolio_names, account_numbers
    )
    requested = [
        number for portfolio in portfolios for number in portfolio.account_numbers
    ]
    if not requested and len(portfolios) > 1:
        raise ValueError(
            "with multiple portfolios, robinhood_account_numbers must be "
            "configured; automatic account selection cannot decide which "
            "portfolio the account belongs to"
        )
    external_symbols = {
        symbol for portfolio in portfolios for symbol in portfolio.external_symbols
    }
    snapshot = (fetch or fetch_portfolios)(
        endpoint=endpoint, account_numbers=requested,
        symbols=sorted(set(asset_classes) | external_symbols),
        token_file=token_file, verbose=verbose,
    )
    prices = {
        key.upper(): decimal(value) for key, value in snapshot.get("prices", {}).items()
    }
    return Report(
        asset_classes=asset_classes,
        portfolios=tuple(
            _portfolio_report(portfolio, snapshot, prices, asset_classes,
                              auto_selected=not requested)
            for portfolio in portfolios
        ),
    )


def select_portfolios(
    portfolios: list[Portfolio],
    names: Sequence[str] | None,
    account_numbers: Sequence[str] | None,
) -> list[Portfolio]:
    """Narrow the configured portfolios to what this run asked for."""
    if names:
        wanted = list(dict.fromkeys(names))
        by_name = {portfolio.name: portfolio for portfolio in portfolios}
        unknown = [name for name in wanted if name not in by_name]
        if unknown:
            raise ValueError(
                f"unknown portfolio(s): {', '.join(unknown)}. Configured: "
                f"{', '.join(by_name)}"
            )
        portfolios = [by_name[name] for name in wanted]
    if account_numbers:
        if len(portfolios) != 1:
            raise ValueError(
                "an explicit account list requires exactly one portfolio; narrow "
                "the run to one portfolio by name first"
            )
        replacement = tuple(str(number) for number in account_numbers)
        portfolios = [_with_accounts(portfolios[0], replacement)]
    return portfolios


def _with_accounts(portfolio: Portfolio, numbers: tuple[str, ...]) -> Portfolio:
    return Portfolio(
        name=portfolio.name,
        targets=portfolio.targets,
        account_numbers=numbers,
        external_accounts=portfolio.external_accounts,
        target_cash=portfolio.target_cash,
        minimum_trade=portfolio.minimum_trade,
    )


def _portfolio_report(
    portfolio: Portfolio, snapshot: PortfolioSnapshot,
    prices: dict[str, Decimal], asset_classes: Mapping[str, str],
    auto_selected: bool,
) -> PortfolioReport:
    accounts = _robinhood_accounts(portfolio, snapshot, auto_selected)
    accounts.extend(_external_accounts(portfolio, prices))
    positions = aggregate_positions(accounts)
    current_cash = sum((account.cash for account in accounts), Decimal(0))
    recommendations = calculate(
        current_cash=current_cash,
        target_cash=portfolio.target_cash,
        targets=portfolio.targets,
        asset_classes=asset_classes,
        positions=positions,
        minimum_trade=portfolio.minimum_trade,
    )
    recommendations.append(calculate_cash(
        current_cash=current_cash,
        target_cash=portfolio.target_cash,
        minimum_trade=portfolio.minimum_trade,
    ))
    return PortfolioReport(
        portfolio=portfolio,
        accounts=tuple(accounts),
        positions=positions,
        recommendations=tuple(recommendations),
    )


def _robinhood_accounts(
    portfolio: Portfolio, snapshot: PortfolioSnapshot, auto_selected: bool
) -> list[AccountHoldings]:
    fetched = snapshot["accounts"]
    if auto_selected:
        # No account was configured anywhere, so Robinhood picked the only
        # recognizable one and this is necessarily the only portfolio.
        selected = list(fetched)
    else:
        by_number = {str(account.get("account_number")): account for account in fetched}
        selected = [by_number[number] for number in portfolio.account_numbers
                    if number in by_number]
    accounts: list[AccountHoldings] = []
    for index, account in enumerate(selected, start=1):
        accounts.append(AccountHoldings(
            label=str(account.get("account_number") or f"Robinhood {index}"),
            kind=ROBINHOOD,
            positions=parse_positions(account.get("positions", [])),
            cash=decimal(account["cash"]),
        ))
    return accounts


def _external_accounts(
    portfolio: Portfolio, prices: Mapping[str, Decimal]
) -> list[AccountHoldings]:
    accounts: list[AccountHoldings] = []
    for external in portfolio.external_accounts:
        positions: dict[str, Position] = {}
        for item in external.get("assets", []):
            symbol = item["symbol"].upper()
            if symbol in positions:
                raise ValueError(
                    f"duplicate symbol {symbol} in external account {external['name']}"
                )
            price = prices.get(symbol)
            if price is None:
                raise ValueError(
                    f"Robinhood did not return a quote for external asset {symbol}"
                )
            positions[symbol] = Position(symbol, decimal(item["quantity"]), price)
        accounts.append(AccountHoldings(
            label=external["name"], kind=EXTERNAL, positions=positions,
            cash=decimal(external.get("cash", 0)),
        ))
    return accounts


def parse_positions(items: list[NormalizedPosition]) -> dict[str, Position]:
    result: dict[str, Position] = {}
    for item in items:
        symbol = item["symbol"].upper()
        position = Position(symbol, decimal(item["quantity"]), decimal(item["price"]))
        existing = result.get(symbol)
        result[symbol] = _merge(existing, position) if existing else position
    return result


def aggregate_positions(accounts: Sequence[AccountHoldings]) -> dict[str, Position]:
    """Combine every account's positions into the portfolio-level holdings."""
    result: dict[str, Position] = {}
    for account in accounts:
        for symbol, position in account.positions.items():
            existing = result.get(symbol)
            result[symbol] = _merge(existing, position) if existing else position
    return result


def _merge(existing: Position, addition: Position) -> Position:
    """Combine two lots of one symbol, keeping a value-weighted average price."""
    quantity = existing.quantity + addition.quantity
    value = existing.market_value + addition.market_value
    price = value / quantity if quantity else addition.price
    return Position(existing.symbol, quantity, price)
