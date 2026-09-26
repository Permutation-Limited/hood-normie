from datetime import date
from decimal import Decimal
import unittest

from examples.income.core import INFERRED_LONG, Sale
from examples.income.wash import LossSale, Purchase, find_wash_sales


D = Decimal


def loss(when: date, quantity: str, gain: str, symbol: str = "BNDW",
         asset: str = "equity") -> LossSale:
    return LossSale("111", "individual · 111", Sale(
        when, symbol, D(quantity), D("68"), D(gain), asset, "long", INFERRED_LONG))


def buy(when: date, quantity: str, account: str = "111", ira: bool = False,
        symbol: str = "BNDW") -> Purchase:
    return Purchase(symbol, when, account, f"acct {account}", ira, D(quantity))


def held(amount: str = "1000"):
    return lambda account, symbol, day: D(amount)


class WashSaleTest(unittest.TestCase):
    def test_drip_after_a_loss_disallows_its_share(self):
        [wash] = find_wash_sales([loss(date(2026, 4, 2), "100", "-500")],
                                 [buy(date(2026, 4, 7), "10")], held())
        self.assertEqual(wash.replaced, D(10))
        self.assertEqual(wash.disallowed, D("50.00"))
        self.assertEqual(wash.permanent, D("0.00"))

    def test_window_is_thirty_days_either_side(self):
        purchases = [buy(date(2026, 3, 3), "1"), buy(date(2026, 3, 2), "1"),
                     buy(date(2026, 5, 2), "1"), buy(date(2026, 5, 3), "1")]
        [wash] = find_wash_sales([loss(date(2026, 4, 2), "100", "-100")],
                                 purchases, held())
        self.assertEqual([item.when for item in wash.replacements],
                         [date(2026, 3, 3), date(2026, 5, 2)])

    def test_ira_replacement_is_permanent(self):
        [wash] = find_wash_sales([loss(date(2026, 4, 2), "10", "-100")],
                                 [buy(date(2026, 4, 3), "4", account="222", ira=True)],
                                 held())
        self.assertEqual(wash.permanent, D("40.00"))

    def test_each_purchase_replaces_only_once(self):
        washes = find_wash_sales(
            [loss(date(2026, 4, 2), "5", "-50"), loss(date(2026, 4, 3), "5", "-50")],
            [buy(date(2026, 4, 5), "6")], held(),
        )
        self.assertEqual([item.replaced for item in washes], [D(5), D(1)])

    def test_earlier_buys_in_the_same_account_may_be_the_shares_sold(self):
        # Everything was sold: the buy two weeks before was part of the sale.
        found = find_wash_sales([loss(date(2026, 4, 2), "100", "-100")],
                                [buy(date(2026, 3, 20), "10")], held("0"))
        self.assertEqual(found, [])

    def test_gains_and_crypto_are_ignored(self):
        found = find_wash_sales(
            [loss(date(2026, 4, 2), "1", "5"),
             loss(date(2026, 4, 2), "1", "-5", symbol="ADA", asset="other")],
            [buy(date(2026, 4, 3), "1"), buy(date(2026, 4, 3), "1", symbol="ADA")],
            held(),
        )
        self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()
