from datetime import date
from decimal import Decimal
import unittest

from examples.income.core import IncomeConfig
from examples.income.report import build_income_report
from hood_normie.mcp import McpError
from hood_normie.types import JsonObject, JsonValue


class FakeSource:
    """Stands in for RobinhoodClient, recording what the report asked for."""

    def __init__(self) -> None:
        self.spans: list[str] = []
        self.order_filters: list[dict[str, str]] = []
        self.lot_lookups: list[tuple[str, str]] = []
        self.close_requests: list[tuple[list[str], str, str]] = []

    def connect(self) -> None:
        pass

    def get_accounts(self) -> JsonValue:
        return {"data": {"accounts": [
            {"account_number": "111", "brokerage_account_type": "individual"},
            {"account_number": "222", "brokerage_account_type": "ira_roth"},
        ]}}

    def realized_trades(self, account_number: str, span: str) -> list[JsonObject]:
        self.spans.append(span)
        return [
            {"symbol": "VT", "timestamp": "2026-03-02T15:00:00Z", "side": "sell",
             "quantity": "1", "price": "100", "realized_gain": "40"},
            {"symbol": "DELISTED", "timestamp": "2026-03-02T15:00:00Z",
             "side": "sell", "quantity": "1", "price": "1", "realized_gain": "-3"},
            {"symbol": "VT", "timestamp": "2025-06-02T15:00:00Z", "side": "sell",
             "quantity": "1", "price": "100", "realized_gain": "1000"},
        ]

    def equity_orders(self, account_number: str, **filters: str) -> list[JsonObject]:
        self.order_filters.append(filters)
        sell: list[JsonValue] = [{"timestamp": "2026-03-02T15:00:00Z"}]
        return [
            {"symbol": "VT", "side": "sell", "state": "filled",
             "cumulative_quantity": "1", "created_at": "2026-03-02T15:00:00Z",
             "executions": sell},
            {"symbol": "DELISTED", "side": "sell", "state": "filled",
             "cumulative_quantity": "1", "created_at": "2026-03-02T15:00:00Z",
             "executions": sell},
            {"symbol": "VT", "side": "buy", "state": "filled", "placed_agent": "drip",
             "cumulative_quantity": "0.1", "created_at": "2026-06-20T02:00:00Z",
             "dollar_based_amount": {"amount": "12.34", "currency_code": "USD"}},
        ]

    def equity_positions(self, account_number: str) -> list[JsonObject]:
        return [{"symbol": "VT", "quantity": "5"}, {"symbol": "CASHCO", "quantity": "10"}]

    def daily_closes(self, symbols, start_time, adjustment_type):
        self.close_requests.append((sorted(symbols), start_time, adjustment_type))
        # VT reinvests its June dividend; CASHCO pays $0.50 in cash on May 1.
        full = adjustment_type == "all"
        return {
            "VT": {"2026-06-17": "99.70" if full else "100",
                   "2026-06-18": "100" if full else "100"},
            "CASHCO": {"2026-04-30": "49.50" if full else "50",
                       "2026-05-01": "50" if full else "50"},
        }

    def equity_tax_lots(self, account_number: str, symbol: str) -> list[JsonObject]:
        self.lot_lookups.append((account_number, symbol))
        if symbol == "DELISTED":
            raise McpError("instrument not found")
        return [{"open_date": "2020-01-02", "term": "lt", "quantity": "10"}]


class BuildIncomeReportTest(unittest.TestCase):
    def test_classifies_each_account(self):
        source = FakeSource()
        report = build_income_report(
            source, 2026, IncomeConfig(qualified_fractions={"VT": Decimal(1)}),
            today=date(2026, 9, 26),
        )
        taxable, ira = report.accounts
        self.assertFalse(taxable.tax_advantaged)
        self.assertTrue(ira.tax_advantaged)
        self.assertEqual([(sale.symbol, sale.term) for sale in taxable.sales],
                         [("DELISTED", "unknown"), ("VT", "long")])
        self.assertEqual(taxable.totals.qualified, Decimal("12.34"))
        self.assertEqual(report.taxable_totals.long_term, Decimal(40))
        self.assertEqual(report.taxable_totals.unknown_term, Decimal(-3))

    def test_this_year_uses_ytd_and_the_whole_order_history(self):
        source = FakeSource()
        build_income_report(source, 2026, IncomeConfig(), today=date(2026, 9, 26))
        self.assertEqual(source.spans, ["ytd", "ytd"])
        self.assertEqual(source.order_filters, [{}, {}])

    def test_estimates_cash_dividends_but_not_reinvested_ones(self):
        source = FakeSource()
        report = build_income_report(source, 2026, IncomeConfig(),
                                     today=date(2026, 9, 26))
        taxable = report.accounts[0]
        cash = [item for item in taxable.dividends if not item.reinvested]
        self.assertEqual([(item.symbol, item.when, item.amount) for item in cash],
                         [("CASHCO", date(2026, 5, 1), Decimal("5.00"))])
        self.assertEqual(taxable.totals.estimated_cash, Decimal("5.00"))
        self.assertEqual(taxable.totals.dividends, Decimal("17.34"))
        # One pair of price-history requests covers every account.
        self.assertEqual([request[2] for request in source.close_requests],
                         ["split", "all"])
        self.assertEqual(source.close_requests[0][1], "2025-12-01T00:00:00Z")

    def test_an_earlier_year_reads_the_full_history(self):
        source = FakeSource()
        report = build_income_report(source, 2025, IncomeConfig(),
                                     account_numbers=["111"], today=date(2026, 9, 26))
        self.assertEqual(source.spans, ["all"])
        self.assertEqual([sale.gain for sale in report.accounts[0].sales],
                         [Decimal(1000)])

    def test_rejects_a_future_year(self):
        with self.assertRaises(ValueError):
            build_income_report(FakeSource(), 2027, IncomeConfig(),
                                today=date(2026, 9, 26))


if __name__ == "__main__":
    unittest.main()
