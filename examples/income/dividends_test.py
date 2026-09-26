from datetime import date
from decimal import Decimal
import unittest

from examples.income.core import Dividend, IncomeConfig
from examples.income.dividends import (
    DividendEvent, dividend_events, estimated_cash_dividends, shares_entitled,
    unreinvested_events,
)


def event(symbol: str, day: date, per_share: str) -> DividendEvent:
    return DividendEvent(symbol, day, Decimal(per_share))


def drip(symbol: str, day: date, amount: str = "1") -> Dividend:
    return Dividend(day, symbol, Decimal(amount), None)


class DividendEventsTest(unittest.TestCase):
    def test_reads_exact_amounts_from_the_adjustment_gap(self):
        # DFAW around its June 2026 ex-date: the gap drops by the dividend.
        split = {"2026-06-18": "83.300000", "2026-06-22": "83.350000",
                 "2026-06-23": "81.740000", "2026-06-24": "81.770000"}
        full = {"2026-06-18": "82.666394", "2026-06-22": "82.716394",
                "2026-06-23": "81.482048", "2026-06-24": "81.512048"}
        self.assertEqual(dividend_events("dfaw", split, full),
                         [event("DFAW", date(2026, 6, 23), "0.375654")])

    def test_rounding_noise_and_days_missing_from_one_series_are_ignored(self):
        split = {"2026-01-02": "10.00", "2026-01-05": "10.00", "2026-01-06": "10.00"}
        full = {"2026-01-02": "9.50", "2026-01-05": "9.49995", "2026-01-07": "9.0"}
        self.assertEqual(dividend_events("X", split, full), [])


class SharesEntitledTest(unittest.TestCase):
    def test_counts_older_lots_and_shares_sold_since(self):
        lots = [(date(2020, 1, 2), Decimal("10")), (date(2026, 6, 15), Decimal("5")),
                (date(2026, 6, 20), Decimal("3"))]
        sales = [(date(2026, 6, 1), Decimal("4")), (date(2026, 6, 15), Decimal("2"))]
        # The lot opened on the ex-date is not entitled; the sale that day is.
        self.assertEqual(shares_entitled(date(2026, 6, 15), lots, sales), Decimal("12"))


class UnreinvestedEventsTest(unittest.TestCase):
    def test_a_missing_month_does_not_shift_later_pairings(self):
        events = [event("BNDW", date(2026, month, 2), "0.2") for month in (2, 3, 4)]
        drips = [drip("BNDW", date(2026, 3, 5)), drip("BNDW", date(2026, 4, 7))]
        self.assertEqual(unreinvested_events(events, drips), [events[0]])

    def test_pairs_only_within_the_window_and_symbol(self):
        events = [event("VT", date(2026, 3, 20), "0.3")]
        self.assertEqual(unreinvested_events(events, [drip("VT", date(2026, 6, 1))]),
                         events)
        self.assertEqual(unreinvested_events(events, [drip("VXUS", date(2026, 3, 25))]),
                         events)
        self.assertEqual(unreinvested_events(events, [drip("VT", date(2026, 3, 25))]),
                         [])


class EstimatedCashTest(unittest.TestCase):
    def test_matches_a_robinhood_cash_payment(self):
        # "Because you owned 39.724 shares of VSS ... on 9/18, you've received
        # a dividend payment of $11.72."
        [paid] = estimated_cash_dividends(
            [event("VSS", date(2026, 9, 18), "0.2951")], 2026,
            {"VSS": [(date(2023, 4, 28), Decimal("21.0395")),
                     (date(2025, 7, 31), Decimal("18.6845"))]},
            {}, IncomeConfig(qualified_fractions={"VSS": Decimal("0.8")}),
        )
        self.assertEqual(paid.amount, Decimal("11.72"))
        self.assertFalse(paid.reinvested)
        self.assertEqual(paid.qualified_fraction, Decimal("0.8"))

    def test_skips_other_years_and_unheld_symbols(self):
        paid = estimated_cash_dividends(
            [event("VT", date(2025, 12, 19), "1.1"), event("VT", date(2026, 3, 20), "0.3")],
            2026, {}, {}, IncomeConfig(),
        )
        self.assertEqual(paid, [])


if __name__ == "__main__":
    unittest.main()
