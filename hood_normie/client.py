"""High-level, normalized client for Robinhood's Trading MCP tools."""

from typing import Iterable, NotRequired, TypedDict

from hood_normie.accounts import select_account
from hood_normie.mcp import RobinhoodMcpClient
from hood_normie.oauth import DEFAULT_ENDPOINT, load_access_token
from hood_normie.types import JsonObject, JsonValue, MoneyValue


class NormalizedPosition(TypedDict):
    symbol: str
    quantity: MoneyValue
    price: MoneyValue


class NormalizedAccount(TypedDict):
    net_liquidation_value: MoneyValue
    cash: MoneyValue
    positions: list[NormalizedPosition]
    account_number: NotRequired[str]


class NormalizedAccountWithPrices(NormalizedAccount):
    prices: dict[str, MoneyValue]


class PortfolioSnapshot(TypedDict):
    accounts: list[NormalizedAccount]
    prices: dict[str, MoneyValue]


class RobinhoodClient:
    """Read Robinhood accounts and quotes through the official Trading MCP."""

    def __init__(self, access_token: str, *, endpoint: str = DEFAULT_ENDPOINT,
                 timeout: float = 30, verbose: bool = False):
        self.mcp = RobinhoodMcpClient(
            endpoint, access_token, timeout=timeout, verbose=verbose
        )

    @classmethod
    def from_token_file(cls, token_file: str, *, endpoint: str = DEFAULT_ENDPOINT,
                        timeout: float = 30, verbose: bool = False) -> "RobinhoodClient":
        return cls(
            load_access_token(token_file), endpoint=endpoint,
            timeout=timeout, verbose=verbose,
        )

    def connect(self) -> None:
        self.mcp.connect()

    def get_accounts(self) -> JsonValue:
        return self.mcp.call_tool("get_accounts")

    def get_portfolio(self, account_number: str) -> JsonValue:
        return self.mcp.call_tool("get_portfolio", {"account_number": account_number})

    def get_equity_positions(self, account_number: str) -> JsonValue:
        return self.mcp.call_tool(
            "get_equity_positions", {"account_number": account_number}
        )

    def get_equity_quotes(self, symbols: Iterable[str]) -> JsonValue:
        symbol_values: list[JsonValue] = []
        symbol_values.extend(sorted(set(symbols)))
        return self.mcp.call_tool(
            "get_equity_quotes", {"symbols": symbol_values}
        )

    def fetch_portfolios(
        self, account_numbers: Iterable[str] = (), quote_symbols: Iterable[str] = ()
    ) -> PortfolioSnapshot:
        """Fetch and normalize multiple accounts plus a shared live price map."""
        self.connect()
        selected = [str(value) for value in account_numbers]
        if not selected:
            selected = [select_account(self.get_accounts())]

        raw_accounts: list[tuple[str, JsonValue, JsonValue]] = []
        held_symbols: set[str] = set()
        for account_number in selected:
            portfolio = self.get_portfolio(account_number)
            positions = self.get_equity_positions(account_number)
            raw_accounts.append((account_number, portfolio, positions))
            held_symbols.update(position_symbols(positions))

        quotes = self.get_equity_quotes(set(quote_symbols) | held_symbols)
        normalized_accounts: list[NormalizedAccount] = []
        for account_number, portfolio, positions in raw_accounts:
            normalized = normalize_account(portfolio, positions, quotes)
            normalized_accounts.append({
                "net_liquidation_value": normalized["net_liquidation_value"],
                "cash": normalized["cash"],
                "positions": normalized["positions"],
                "account_number": account_number,
            })
        return {"accounts": normalized_accounts, "prices": normalize_quotes(quotes)}


def normalize_account(
    portfolio: JsonValue, positions: JsonValue, quotes: JsonValue
) -> NormalizedAccountWithPrices:
    """Normalize Robinhood tool responses into stable JSON-compatible fields."""
    value_fields = (
        "net_liquidation_value", "netLiquidationValue", "net_liquidation",
        "netLiquidation", "total_value", "totalValue", "total_equity",
        "totalEquity", "portfolio_value", "portfolioValue", "portfolio_equity",
        "portfolioEquity", "equity",
    )
    portfolio_record = find_record_with_field(portfolio, value_fields)
    if portfolio_record is None:
        raise ValueError(
            "could not find net liquidation/total value in get_portfolio response. "
            f"Response shape (values omitted): {response_shape(portfolio)}"
        )
    net_value = money_value(first(portfolio_record, *value_fields))
    if net_value is None:
        raise ValueError(
            "could not find net liquidation/total value in get_portfolio response. "
            f"Response shape (values omitted): {response_shape(portfolio)}"
        )
    cash = money_value(first(portfolio_record, "cash"))
    if cash is None:
        raise ValueError(
            "could not find broker-reported cash in get_portfolio response. "
            f"Response shape (values omitted): {response_shape(portfolio)}"
        )

    quote_map = normalize_quotes(quotes)
    price_fields = price_field_names()
    normalized_positions: list[NormalizedPosition] = []
    missing_prices: list[str] = []
    for position in position_records(positions):
        symbol = str(first(position, "symbol") or "").upper()
        quantity = money_value(first(position, "quantity", "shares"))
        price = quote_map.get(symbol) or money_value(
            first(position, *price_fields, "market_price", "marketPrice")
        )
        if symbol and quantity is not None:
            if price is None:
                missing_prices.append(symbol)
            else:
                normalized_positions.append(
                    {"symbol": symbol, "quantity": quantity, "price": price}
                )
    if missing_prices:
        raise ValueError(
            "Robinhood returned positions without usable quotes for: "
            + ", ".join(sorted(missing_prices))
        )
    return {
        "net_liquidation_value": net_value,
        "cash": cash,
        "positions": normalized_positions,
        "prices": quote_map,
    }


def normalize_quotes(quotes: JsonValue) -> dict[str, MoneyValue]:
    quote_map: dict[str, MoneyValue] = {}
    fields = price_field_names()
    for quote in find_records_with_fields(quotes, ("symbol",), fields):
        symbol = first(quote, "symbol")
        price = money_value(first(quote, *fields))
        if symbol and price is not None:
            quote_map[str(symbol).upper()] = price
    return quote_map


def price_field_names() -> tuple[str, ...]:
    return (
        "price", "mark_price", "markPrice", "last_trade_price", "lastTradePrice",
        "last_price", "lastPrice", "current_price", "currentPrice",
    )


def first(record: JsonObject, *keys: str) -> JsonValue:
    return next((record[key] for key in keys if record.get(key) is not None), None)


def find_record_with_field(payload: JsonValue, fields: tuple[str, ...]) -> JsonObject | None:
    if isinstance(payload, dict):
        if any(payload.get(field) is not None for field in fields):
            return payload
        for value in payload.values():
            found = find_record_with_field(value, fields)
            if found is not None:
                return found
    elif isinstance(payload, list):
        for value in payload:
            found = find_record_with_field(value, fields)
            if found is not None:
                return found
    return None


def find_records_with_fields(
    payload: JsonValue, required: tuple[str, ...], alternatives: tuple[str, ...]
) -> list[JsonObject]:
    found: list[JsonObject] = []
    if isinstance(payload, dict):
        if (all(payload.get(field) is not None for field in required)
                and any(payload.get(field) is not None for field in alternatives)):
            found.append(payload)
        else:
            for value in payload.values():
                found.extend(find_records_with_fields(value, required, alternatives))
    elif isinstance(payload, list):
        for value in payload:
            found.extend(find_records_with_fields(value, required, alternatives))
    return found


def position_records(payload: JsonValue) -> list[JsonObject]:
    return find_records_with_fields(payload, ("symbol",), ("quantity", "shares"))


def position_symbols(payload: JsonValue) -> list[str]:
    return sorted({
        str(first(position, "symbol")).upper()
        for position in position_records(payload) if first(position, "symbol")
    })


def money_value(value: JsonValue) -> MoneyValue | None:
    if isinstance(value, dict):
        value = first(value, "amount", "value", "decimal", "units")
    if isinstance(value, (str, int, float)) and not isinstance(value, bool):
        return value
    return None


def response_shape(payload: JsonValue, depth: int = 0) -> JsonValue:
    """Return keys and container types without leaking financial values."""
    if depth >= 5:
        return "..."
    if isinstance(payload, dict):
        return {key: response_shape(value, depth + 1) for key, value in payload.items()}
    if isinstance(payload, list):
        return [response_shape(payload[0], depth + 1)] if payload else []
    return type(payload).__name__
