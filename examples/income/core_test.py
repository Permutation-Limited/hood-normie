from datetime import date
from decimal import Decimal
import os
import tempfile
import unittest

from examples.income.core import (
    CONFIGURED, INFERRED_LONG, NO_OLDER_LOT, NOT_EQUITY, TAX_ADVANTAGED,
    YOUNG_OLDEST_LOT, AccountIncome, Dividend, IncomeConfig, IncomeReport,
    classify_sales, eastern_date, equity_sell_times, infer_term, is_long_term,
    load_income_config, parse_income_config, reinvested_dividends,
)


def sell_order(symbol: str, created: str, executed: str | None = None,
               filled: str = "10") -> dict:
    return {
        "symbol": symbol, "side": "sell", "state": "filled",
        "cumulative_quantity": filled, "created_at": created,
        "last_transaction_at": executed or created,
        "executions": [{"timestamp": executed or created}],
    }


def trade(symbol: str, timestamp: str, gain: str) -> dict:
    return {"symbol": symbol, "timestamp": timestamp, "side": "sell",
            "quantity": "10", "price": "100", "realized_gain": gain}


def drip(symbol: str, created: str, amount: str | None, state: str = "filled") -> dict:
    return {
        "symbol": symbol, "side": "buy", "state": state, "placed_agent": "drip",
        "created_at": created,
        "dollar_based_amount": None if amount is None else {
            "amount": amount, "currency_code": "USD"},
        "cumulative_quantity": "2", "average_price": "10.005",
    }


class HoldingPeriodTest(unittest.TestCase):
    def test_long_term_needs_more_than_a_year(self):
        self.assertFalse(is_long_term(date(2025, 3, 10), date(2026, 3, 10)))
        self.assertTrue(is_long_term(date(2025, 3, 10), date(2026, 3, 11)))

    def test_leap_day_anniversary(self):
        self.assertFalse(is_long_term(date(2024, 2, 29), date(2025, 3, 1)))
        self.assertTrue(is_long_term(date(2024, 2, 29), date(2025, 3, 2)))

    def test_older_open_lot_proves_long_term(self):
        term, reason = infer_term(date(2026, 7, 15),
                                  [date(2026, 1, 5), date(2021, 10, 8)])
        self.assertEqual((term, reason), ("long", INFERRED_LONG))

    def test_young_oldest_lot_proves_nothing(self):
        term, reason = infer_term(date(2026, 7, 15), [date(2026, 1, 5)])
        self.assertEqual((term, reason), ("unknown", YOUNG_OLDEST_LOT))

    def test_lots_acquired_after_the_sale_are_ignored(self):
        term, reason = infer_term(date(2026, 7, 15), [date(2026, 8, 1)])
        self.assertEqual((term, reason), ("unknown", NO_OLDER_LOT))

    def test_closed_position_is_unknown(self):
        self.assertEqual(infer_term(date(2026, 7, 15), []), ("unknown", NO_OLDER_LOT))


class DatesTest(unittest.TestCase):
    def test_dates_are_eastern(self):
        # 03:00 UTC on January 1 is still New Year's Eve in New York.
        self.assertEqual(eastern_date("2026-01-01T03:00:00Z"), date(2025, 12, 31))
        self.assertEqual(eastern_date("2026-01-01T06:00:00.123Z"), date(2026, 1, 1))


class ClassifySalesTest(unittest.TestCase):
    def classify(self, trades, orders, lots, config=IncomeConfig(), **kwargs):
        return classify_sales(trades, 2026, equity_sell_times(orders), lots, config,
                              **kwargs)

    def test_equity_sale_matches_its_order_by_execution_time(self):
        orders = [sell_order("CRBN", "2026-07-15T14:41:24.39Z",
                             "2026-07-15T14:41:24.537Z")]
        [sale] = self.classify([trade("CRBN", "2026-07-15T14:41:24Z", "383.45")],
                               orders, {"CRBN": [date(2021, 10, 8)]})
        self.assertEqual(sale.asset, "equity")
        self.assertEqual(sale.term, "long")
        self.assertEqual(sale.gain, Decimal("383.45"))

    def test_ticker_shared_with_a_coin_is_told_apart_by_time(self):
        # SUI is also a REIT; its equity sale happened on another day.
        orders = [sell_order("SUI", "2025-01-29T15:00:00Z")]
        [sale] = self.classify([trade("SUI", "2026-06-04T12:00:00Z", "-0.09")],
                               orders, {})
        self.assertEqual(sale.asset, "other")
        self.assertEqual((sale.term, sale.reason), ("unknown", NOT_EQUITY))

    def test_partly_filled_order_still_counts_but_an_empty_one_does_not(self):
        orders = [
            sell_order("BNDW", "2026-03-19T20:34:01Z", "2026-03-19T21:47:04.146Z",
                       filled="2"),
            sell_order("VTI", "2026-03-19T21:47:04Z", filled="0"),
        ]
        sales = self.classify([trade("BNDW", "2026-03-19T21:47:04Z", "-0.69"),
                               trade("VTI", "2026-03-19T21:47:04Z", "1")],
                              orders, {"BNDW": [date(2024, 5, 15)]})
        self.assertEqual([sale.asset for sale in sales], ["equity", "other"])

    def test_config_settles_only_unknown_terms(self):
        orders = [sell_order("DFGR", "2026-03-20T14:00:00Z"),
                  sell_order("VT", "2026-03-20T14:00:00Z")]
        config = IncomeConfig(holding_periods={"DFGR": "short", "VT": "short"})
        sales = self.classify(
            [trade("DFGR", "2026-03-20T14:00:00Z", "5"),
             trade("VT", "2026-03-20T14:00:00Z", "7")],
            orders, {"DFGR": [], "VT": [date(2020, 1, 1)]}, config,
        )
        by_symbol = {sale.symbol: sale for sale in sales}
        self.assertEqual((by_symbol["DFGR"].term, by_symbol["DFGR"].reason),
                         ("short", CONFIGURED))
        self.assertEqual(by_symbol["VT"].term, "long")

    def test_other_years_are_dropped(self):
        sales = self.classify([trade("VT", "2025-12-31T15:00:00Z", "1")], [], {})
        self.assertEqual(sales, [])

    def test_tax_advantaged_sales_are_not_classified(self):
        orders = [sell_order("VT", "2026-01-27T20:40:20Z")]
        [sale] = self.classify([trade("VT", "2026-01-27T20:40:20Z", "8522.65")],
                               orders, {}, IncomeConfig(holding_periods={"VT": "long"}),
                               tax_advantaged=True)
        self.assertEqual((sale.term, sale.reason), ("unknown", TAX_ADVANTAGED))


class DividendsTest(unittest.TestCase):
    def test_reads_drip_purchases_as_dividends(self):
        orders = [
            drip("VT", "2026-09-23T02:01:55Z", "880.90"),
            drip("BND", "2026-09-04T01:02:13Z", None),
            drip("VT", "2026-09-01T02:00:00Z", "5", state="cancelled"),
            {**drip("VT", "2026-09-01T02:00:00Z", "5"), "placed_agent": "user"},
            # Eastern date is still 2025.
            drip("VT", "2026-01-01T03:00:00Z", "12"),
        ]
        dividends = reinvested_dividends(orders, 2026, IncomeConfig())
        self.assertEqual([(item.symbol, item.amount) for item in dividends],
                         [("BND", Decimal("20.01")), ("VT", Decimal("880.90"))])

    def test_splits_by_configured_qualified_share(self):
        item = Dividend(date(2026, 3, 1), "VT", Decimal("100.01"), Decimal("0.85"))
        self.assertEqual(item.qualified, Decimal("85.01"))
        self.assertEqual(item.nonqualified, Decimal("15.00"))
        self.assertEqual(item.unclassified, Decimal(0))

    def test_unconfigured_symbol_is_unclassified(self):
        item = Dividend(date(2026, 3, 1), "VT", Decimal("10"), None)
        self.assertEqual((item.qualified, item.nonqualified, item.unclassified),
                         (Decimal(0), Decimal(0), Decimal("10")))


class TotalsTest(unittest.TestCase):
    def test_taxable_totals_leave_out_retirement_accounts(self):
        from examples.income.core import Sale

        def account(tax_advantaged: bool) -> AccountIncome:
            return AccountIncome(
                label="x", account_number="1", tax_advantaged=tax_advantaged,
                sales=(Sale(date(2026, 1, 2), "VT", Decimal(1), Decimal(1),
                            Decimal("10"), "equity", "long", INFERRED_LONG),
                       Sale(date(2026, 1, 2), "ADA", Decimal(1), Decimal(1),
                            Decimal("-1"), "other", "unknown", NOT_EQUITY)),
                dividends=(Dividend(date(2026, 1, 2), "VT", Decimal("4"),
                                    Decimal("0.5")),),
            )

        report = IncomeReport(2026, (account(False), account(True)))
        totals = report.taxable_totals
        self.assertEqual(totals.long_term, Decimal("10"))
        self.assertEqual(totals.unknown_term, Decimal("-1"))
        self.assertEqual(totals.qualified, Decimal("2.00"))
        self.assertEqual(totals.nonqualified, Decimal("2.00"))
        self.assertEqual(totals.realized, Decimal("9"))


class ConfigTest(unittest.TestCase):
    def test_parses_fractions_and_words(self):
        config = parse_income_config({
            "qualified_dividends": {"vt": 0.85, "BND": "nonqualified",
                                    "AAPL": "qualified"},
            "holding_periods": {"dfgr": "long"},
        })
        self.assertEqual(config.qualified_fractions,
                         {"VT": Decimal("0.85"), "BND": Decimal(0), "AAPL": Decimal(1)})
        self.assertEqual(config.holding_periods, {"DFGR": "long"})

    def test_rejects_bad_values(self):
        raw: object
        for raw in ({"qualified_dividends": {"VT": 1.5}},
                    {"qualified_dividends": {"VT": True}},
                    {"qualified_dividends": {"VT": "most"}},
                    {"holding_periods": {"VT": "forever"}},
                    {"holding_period": {}}):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                parse_income_config(raw)  # type: ignore[arg-type]

    def test_loads_the_example_file_and_empty_files(self):
        example = os.path.join(os.path.dirname(__file__), "income.example.yaml")
        self.assertIn("VTI", load_income_config(example).qualified_fractions)
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as stream:
            stream.write("")
        self.addCleanup(os.unlink, stream.name)
        self.assertEqual(load_income_config(stream.name), IncomeConfig())


if __name__ == "__main__":
    unittest.main()
