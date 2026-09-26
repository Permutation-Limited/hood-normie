from datetime import date
from decimal import Decimal
import unittest

from examples.income.core import (
    REPLAYED, IncomeConfig, classify_sales, equity_sell_times, split_by_lots,
)
from examples.income.lots import closed_portions, replay_fifo, sell_fills
from hood_normie.types import JsonObject


def order(order_id: str, side: str, stamp: str, quantity: str, price: str,
          symbol: str = "TGT") -> JsonObject:
    return {
        "id": order_id, "symbol": symbol, "side": side, "state": "filled",
        "cumulative_quantity": quantity, "average_price": price, "created_at": stamp,
        "executions": [{"timestamp": stamp, "quantity": quantity, "price": price}],
    }


HISTORY = [
    order("b1", "buy", "2024-03-01T15:00:00Z", "10", "100"),
    order("b2", "buy", "2025-06-01T15:00:00Z", "10", "120"),
    order("s1", "sell", "2025-07-11T15:00:00Z", "15", "130"),
]


class ReplayTest(unittest.TestCase):
    def test_sales_consume_the_oldest_shares_first(self):
        closed = replay_fifo(HISTORY, "TGT", Decimal("5"))
        assert closed is not None
        self.assertEqual([(p.quantity, p.cost_per_share) for p in closed["s1"]],
                         [(Decimal("10"), Decimal("100")), (Decimal("5"), Decimal("120"))])

    def test_refuses_a_history_that_does_not_explain_the_position(self):
        # Shares arrived or left some other way: a transfer.
        self.assertIsNone(replay_fifo(HISTORY, "TGT", Decimal("7")))
        self.assertIsNone(replay_fifo(HISTORY[2:], "TGT", Decimal("0")))

    def test_sell_fills_are_dated_in_eastern_time(self):
        self.assertEqual(sell_fills(HISTORY, "tgt"), [(date(2025, 7, 11), Decimal("15"))])


class SplitByLotsTest(unittest.TestCase):
    def test_splits_a_mixed_sale_and_keeps_robinhoods_total(self):
        portions = closed_portions(HISTORY, "TGT", Decimal("5"))
        assert portions is not None
        sales = split_by_lots(date(2025, 7, 11), "TGT", Decimal("15"),
                              Decimal("130"), Decimal("349.00"), portions["s1"])
        by_term = {sale.term: sale for sale in sales}
        self.assertEqual(by_term["long"].quantity, Decimal("10"))
        self.assertEqual(by_term["short"].quantity, Decimal("5"))
        # Implied gains 300 and 50; the missing $1 is shared by quantity.
        self.assertEqual(by_term["long"].gain, Decimal("299.33"))
        self.assertEqual(by_term["short"].gain, Decimal("49.67"))
        self.assertTrue(all(sale.reason == REPLAYED for sale in sales))

    def test_classify_uses_the_replay_when_open_lots_cannot_settle_it(self):
        trade: JsonObject = {"symbol": "TGT", "timestamp": "2025-07-11T15:00:00Z",
                 "quantity": "15", "price": "130", "realized_gain": "350"}
        sales = classify_sales(
            [trade], 2025, equity_sell_times(HISTORY), {"TGT": []}, IncomeConfig(),
            closed_lots=closed_portions(HISTORY, "TGT", Decimal("5")),
        )
        self.assertEqual(sorted(sale.term for sale in sales), ["long", "short"])
        self.assertEqual(sum(sale.gain for sale in sales), Decimal("350"))


if __name__ == "__main__":
    unittest.main()
