from decimal import Decimal
import unittest

from examples.unrealized.core import (
    AccountUnrealized, Holding, UnrealizedReport, combine, cost_basis, holding, totals,
)
from examples.unrealized.report import build_unrealized_report
from hood_normie.types import JsonObject, JsonValue


D = Decimal


class CostBasisTest(unittest.TestCase):
    def test_uses_the_tax_lots_when_they_cover_the_position(self):
        lots: list[JsonObject] = [
            {"quantity": "7.979368", "tax_cost_basis": "561.03"},
            {"quantity": "10", "tax_cost_basis": "690.00"},
        ]
        position: JsonObject = {"symbol": "BNDW", "average_buy_price": "68.00"}
        self.assertEqual(cost_basis(lots, position, D("17.979368")),
                         (D("1251.03"), "tax lots"))

    def test_falls_back_to_average_cost_when_a_lot_is_pending(self):
        lots: list[JsonObject] = [{"quantity": "1", "tax_cost_basis": None}]
        position: JsonObject = {"average_buy_price": "50.005"}
        self.assertEqual(cost_basis(lots, position, D("2")), (D("100.01"), "average cost"))
        self.assertEqual(cost_basis([], {}, D("2")), (None, "unavailable"))


class HoldingTest(unittest.TestCase):
    def test_marks_against_the_quote(self):
        item = holding({"symbol": "vt", "quantity": "10"},
                       [{"quantity": "10", "tax_cost_basis": "1000"}], {"VT": "158.735"})
        self.assertEqual(item.market_value, D("1587.35"))
        self.assertEqual(item.unrealized, D("587.35"))
        self.assertEqual(item.return_rate, D("0.58735"))

    def test_missing_price_or_basis_leaves_gains_unknown_and_totals_say_so(self):
        priced = Holding("VT", D(1), D(100), D(50), "tax lots")
        unpriced = Holding("XX", D(1), None, D(50), "tax lots")
        self.assertIsNone(unpriced.unrealized)
        total = totals([priced, unpriced])
        self.assertEqual((total.market_value, total.cost_basis, total.incomplete),
                         (D(100), D(50), 1))
        self.assertEqual(total.return_rate, D(1))


class CombineTest(unittest.TestCase):
    def test_merges_symbols_across_accounts(self):
        merged = combine([
            Holding("VT", D(10), D(100), D(800), "tax lots"),
            Holding("BND", D(5), D(70), D(360), "tax lots"),
            Holding("VT", D(5), D(100), D(450), "average cost"),
        ])
        self.assertEqual([item.symbol for item in merged], ["BND", "VT"])
        self.assertEqual(merged[1].quantity, D(15))
        self.assertEqual(merged[1].cost_basis, D(1250))
        self.assertEqual(merged[1].basis_source, "average cost")

    def test_report_combines_only_taxable_accounts(self):
        def account(number: str, ira: bool, basis: str) -> AccountUnrealized:
            return AccountUnrealized(number, number, ira, (
                Holding("VT", D(1), D(100), D(basis), "tax lots"),))

        report = UnrealizedReport((account("1", False, "60"), account("2", False, "70"),
                                   account("3", True, "10")))
        self.assertEqual(report.combined, (Holding("VT", D(2), D(100), D(130), "tax lots"),))
        self.assertEqual(report.taxable_totals.unrealized, D(70))


class FakeSource:
    def __init__(self) -> None:
        self.quoted: list[list[str]] = []

    def connect(self) -> None:
        pass

    def get_accounts(self) -> JsonValue:
        return {"data": {"accounts": [
            {"account_number": "111", "brokerage_account_type": "individual"},
            {"account_number": "222", "brokerage_account_type": "ira_roth"},
        ]}}

    def equity_positions(self, account_number: str) -> list[JsonObject]:
        return [{"symbol": "VT", "quantity": "2", "average_buy_price": "90"}]

    def get_equity_quotes(self, symbols) -> JsonValue:
        self.quoted.append(sorted(symbols))
        return {"data": {"results": [{"symbol": "VT", "last_trade_price": "120"}]}}

    def equity_tax_lots(self, account_number: str, symbol: str) -> list[JsonObject]:
        return [{"quantity": "2", "tax_cost_basis": "200"}]


class BuildReportTest(unittest.TestCase):
    def test_quotes_once_and_labels_retirement_accounts(self):
        source = FakeSource()
        report = build_unrealized_report(source)
        self.assertEqual(source.quoted, [["VT"]])
        self.assertEqual([item.tax_advantaged for item in report.accounts], [False, True])
        self.assertEqual(report.taxable_totals.unrealized, D(40))


if __name__ == "__main__":
    unittest.main()
