from decimal import Decimal
import unittest

from rb_rebalance.core import Position, Target, calculate


class CalculateTest(unittest.TestCase):
    def test_rebalances_to_positive_cash(self):
        result = calculate(
            net_liquidation_value=Decimal("10000"),
            target_cash=Decimal("1000"),
            targets=[Target("VTI", Decimal("0.60"), "stock"),
                     Target("BND", Decimal("0.40"), "bond")],
            positions={
                "VTI": Position("VTI", Decimal("20"), Decimal("250")),
                "BND": Position("BND", Decimal("50"), Decimal("80")),
            },
            prices={"VTI": Decimal("250"), "BND": Decimal("80")},
        )
        self.assertEqual({r.symbol: r.amount for r in result},
                         {"BND": Decimal("-400.00"), "VTI": Decimal("400.00")})

    def test_negative_cash_creates_margin_exposure(self):
        result = calculate(
            net_liquidation_value=Decimal("10000"), target_cash=Decimal("-2000"),
            targets=[Target("VTI", Decimal("0.75"), "stock"),
                     Target("BND", Decimal("0.25"), "bond")],
            positions={}, prices={"VTI": Decimal("250"), "BND": Decimal("75")},
        )
        self.assertEqual(sum(r.target_value for r in result), Decimal("12000.00"))
        self.assertEqual(sum(r.amount for r in result), Decimal("12000.00"))

    def test_minimum_trade_is_suppressed(self):
        result = calculate(
            net_liquidation_value=Decimal("100"), target_cash=Decimal(0),
            targets=[Target("VTI", Decimal(1), "stock")],
            positions={"VTI": Position("VTI", Decimal("0.99"), Decimal("100"))},
            prices={"VTI": Decimal("100")}, minimum_trade=Decimal("5"),
        )
        self.assertEqual(result[0].action, "HOLD")

    def test_weights_must_sum_to_one(self):
        with self.assertRaisesRegex(ValueError, "sum to 1"):
            calculate(net_liquidation_value=Decimal(10), target_cash=Decimal(0),
                      targets=[Target("VTI", Decimal("0.9"), "stock")],
                      positions={}, prices={"VTI": Decimal(1)})


if __name__ == "__main__":
    unittest.main()

