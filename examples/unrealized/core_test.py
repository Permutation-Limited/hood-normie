from decimal import Decimal
import unittest

from datetime import date

from examples.unrealized.core import (
    AccountUnrealized, Holding, Lot, UnrealizedReport, combine, cost_basis, holding,
    parse_lots, totals,
)
from examples.unrealized.report import build_holding_lots, build_unrealized_report
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


class LotTest(unittest.TestCase):
    def test_parses_robinhoods_terms_oldest_first(self):
        lots = parse_lots([
            {"open_date": "2026-03-05", "quantity": "7.979368",
             "tax_cost_basis": "561.00", "term": "lt"},
            {"open_date": "2021-10-18", "quantity": "210", "tax_cost_basis": "16000",
             "term": "lt"},
            {"open_date": "2026-09-04", "quantity": "7", "tax_cost_basis": None,
             "term": "st"},
        ], "111")
        self.assertEqual([lot.acquired for lot in lots],
                         [date(2021, 10, 18), date(2026, 3, 5), date(2026, 9, 4)])
        # A wash-sale replacement keeps Robinhood's inherited long term.
        self.assertEqual(lots[1].term, "long")
        self.assertIsNone(lots[1].long_term_on)
        self.assertEqual(lots[2].long_term_on, date(2027, 9, 5))
        self.assertIsNone(lots[2].cost_basis)
        self.assertEqual(lots[0].account_number, "111")

    def test_leap_day_lot(self):
        lot = Lot(date(2024, 2, 29), D(1), D(1), "short")
        self.assertEqual(lot.long_term_on, date(2025, 3, 2))

    def test_gain_splits_by_term_and_adds_up(self):
        lots = (Lot(date(2020, 1, 2), D("1"), D("50"), "long"),
                Lot(date(2026, 6, 1), D("2"), D("210"), "short"))
        # At this price the holding rounds to $300.02 but its lots to $100.00
        # and $200.01; the stray cent goes to the larger (long-term) part.
        item = Holding("VT", D("3"), D("100.005"), D("260"), "tax lots", lots)
        split = item.by_term
        self.assertEqual(split["long"] + split["short"], item.unrealized)
        self.assertEqual((split["long"], split["short"]), (D("50.01"), D("-9.99")))
        self.assertEqual(item.next_long_term, date(2027, 6, 2))
        total = totals([item])
        self.assertEqual((total.short_term, total.long_term),
                         (split["short"], split["long"]))

    def test_average_cost_holdings_have_no_term(self):
        item = Holding("VT", D(1), D(100), D(60), "average cost")
        self.assertEqual(item.by_term["unknown"], D(40))


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

    def test_lots_on_demand_span_accounts_and_mark_at_a_fresh_quote(self):
        source = FakeSource()
        found = build_holding_lots(source, ["111", "222"], "vt")
        self.assertEqual(found.symbol, "VT")
        self.assertEqual(found.price, D(120))
        self.assertEqual([lot.account_number for lot in found.lots], ["111", "222"])
        with self.assertRaises(ValueError):
            build_holding_lots(source, [], "VT")


if __name__ == "__main__":
    unittest.main()
