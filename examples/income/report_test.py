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
             "created_at": "2026-06-20T02:00:00Z",
             "dollar_based_amount": {"amount": "12.34", "currency_code": "USD"}},
        ]

    def equity_tax_lots(self, account_number: str, symbol: str) -> list[JsonObject]:
        self.lot_lookups.append((account_number, symbol))
        if symbol == "DELISTED":
            raise McpError("instrument not found")
        return [{"open_date": "2020-01-02", "term": "lt"}]


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

    def test_this_year_uses_ytd_and_skips_lots_for_retirement_accounts(self):
        source = FakeSource()
        build_income_report(source, 2026, IncomeConfig(), today=date(2026, 9, 26))
        self.assertEqual(source.spans, ["ytd", "ytd"])
        self.assertEqual({number for number, _ in source.lot_lookups}, {"111"})
        self.assertEqual(source.order_filters[0], {"created_at_gte": "2025-10-01"})

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
