from decimal import Decimal
import unittest

from rb_rebalance.core import Position, Target, calculate
from rb_rebalance.paths import workspace_path
from rb_rebalance.accounts import select_account


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


class WorkspacePathTest(unittest.TestCase):
    def test_relative_path_uses_bazel_workspace(self):
        self.assertEqual(
            workspace_path("config.json", {"BUILD_WORKSPACE_DIRECTORY": "/repo"}),
            "/repo/config.json",
        )

    def test_absolute_path_is_unchanged(self):
        self.assertEqual(workspace_path("/tmp/config.json", {}), "/tmp/config.json")

    def test_direct_execution_keeps_relative_path(self):
        self.assertEqual(workspace_path("config.json", {}), "config.json")


class AccountSelectionTest(unittest.TestCase):
    def test_selects_only_numbered_account_through_nested_wrapper(self):
        payload = {"accounts": {"results": [
            {"displayName": "Retirement", "accountNumber": "ABC123"},
        ]}}
        self.assertEqual(select_account(payload), "ABC123")

    def test_lists_names_and_numbers_when_ambiguous(self):
        payload = {"accounts": [
            {"nickname": "Individual", "account_number": "111"},
            {"accountType": "Agentic", "number": "222"},
        ]}
        with self.assertRaises(SystemExit) as caught:
            select_account(payload)
        message = str(caught.exception)
        self.assertIn("Individual: 111", message)
        self.assertIn("Agentic: 222", message)
        self.assertIn("--account NUMBER", message)

    def test_missing_number_lists_account_fields(self):
        payload = {"data": {"accounts": [{"name": "Brokerage", "account_id": "id-1"}]}}
        with self.assertRaises(SystemExit) as caught:
            select_account(payload)
        message = str(caught.exception)
        self.assertIn("Brokerage: (number unavailable)", message)
        self.assertIn("account_id", message)


if __name__ == "__main__":
    unittest.main()
