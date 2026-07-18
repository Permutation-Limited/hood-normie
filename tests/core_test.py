from decimal import Decimal
import unittest

from rb_rebalance.core import ClassTarget, Position, calculate, calculate_cash
from rb_rebalance.paths import workspace_path
from rb_rebalance.accounts import select_account


class CalculateTest(unittest.TestCase):
    def test_rebalances_to_positive_cash(self):
        result = calculate(
            net_liquidation_value=Decimal("10000"),
            target_cash=Decimal("1000"),
            targets=[ClassTarget("stocks", Decimal("0.60")),
                     ClassTarget("bonds", Decimal("0.40"))],
            asset_classes={"VTI": "stocks", "BND": "bonds"},
            positions={
                "VTI": Position("VTI", Decimal("20"), Decimal("250")),
                "BND": Position("BND", Decimal("50"), Decimal("80")),
            },
        )
        self.assertEqual({r.asset_class: r.amount for r in result},
                         {"bonds": Decimal("-400.00"), "stocks": Decimal("400.00")})

    def test_negative_cash_creates_margin_exposure(self):
        result = calculate(
            net_liquidation_value=Decimal("10000"), target_cash=Decimal("-2000"),
            targets=[ClassTarget("stocks", Decimal("0.75")),
                     ClassTarget("bonds", Decimal("0.25"))],
            asset_classes={"VTI": "stocks", "BND": "bonds"}, positions={},
        )
        self.assertEqual(sum(r.target_value for r in result), Decimal("12000.00"))
        self.assertEqual(sum(r.amount for r in result), Decimal("12000.00"))

    def test_minimum_trade_is_suppressed(self):
        result = calculate(
            net_liquidation_value=Decimal("100"), target_cash=Decimal(0),
            targets=[ClassTarget("stocks", Decimal(1))],
            asset_classes={"VTI": "stocks"},
            positions={"VTI": Position("VTI", Decimal("0.99"), Decimal("100"))},
            minimum_trade=Decimal("5"),
        )
        self.assertEqual(result[0].action, "HOLD")

    def test_weights_must_sum_to_one(self):
        with self.assertRaisesRegex(ValueError, "sum to 1"):
            calculate(net_liquidation_value=Decimal(10), target_cash=Decimal(0),
                      targets=[ClassTarget("stocks", Decimal("0.9"))],
                      asset_classes={"VTI": "stocks"}, positions={})

    def test_aggregates_multiple_symbols_into_one_class(self):
        result = calculate(
            net_liquidation_value=Decimal("1000"), target_cash=Decimal(0),
            targets=[ClassTarget("stocks", Decimal("0.5")),
                     ClassTarget("bonds", Decimal("0.5"))],
            asset_classes={"VTI": "stocks", "VXUS": "stocks", "BND": "bonds"},
            positions={
                "VTI": Position("VTI", Decimal("1"), Decimal("300")),
                "VXUS": Position("VXUS", Decimal("2"), Decimal("100")),
                "BND": Position("BND", Decimal("5"), Decimal("100")),
            },
        )
        self.assertEqual({r.asset_class: r.current_value for r in result},
                         {"bonds": Decimal("500.00"), "stocks": Decimal("500.00")})
        self.assertTrue(all(r.action == "HOLD" for r in result))

    def test_unmapped_symbol_is_ignored_from_balance_and_allocation_base(self):
        result = calculate(
            net_liquidation_value=Decimal("100"), target_cash=Decimal(0),
            targets=[ClassTarget("stocks", Decimal(1))], asset_classes={},
            positions={"TSLA": Position("TSLA", Decimal(1), Decimal("100"))},
        )
        self.assertEqual(result[0].current_value, Decimal("0.00"))
        self.assertEqual(result[0].target_value, Decimal("0.00"))
        self.assertEqual(result[0].amount, Decimal("0.00"))

    def test_explicit_ignored_class_is_removed_from_allocation_base(self):
        result = calculate(
            net_liquidation_value=Decimal("1000"), target_cash=Decimal("100"),
            targets=[ClassTarget("stocks", Decimal(1)),
                     ClassTarget("legacy", ignore=True)],
            asset_classes={"VTI": "stocks", "OLD": "legacy"},
            positions={
                "VTI": Position("VTI", Decimal(1), Decimal("600")),
                "OLD": Position("OLD", Decimal(1), Decimal("300")),
            },
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].asset_class, "stocks")
        self.assertEqual(result[0].target_value, Decimal("600.00"))
        self.assertEqual(result[0].action, "HOLD")

    def test_fixed_dollar_target_overrides_weight(self):
        result = calculate(
            net_liquidation_value=Decimal("1000"), target_cash=Decimal("100"),
            targets=[
                ClassTarget("stocks", Decimal("0.8")),
                ClassTarget("bonds", Decimal("0.2"), Decimal("300")),
            ],
            asset_classes={"VTI": "stocks", "BND": "bonds"},
            positions={
                "VTI": Position("VTI", Decimal(1), Decimal("500")),
                "BND": Position("BND", Decimal(1), Decimal("200")),
            },
        )
        by_class = {item.asset_class: item for item in result}
        self.assertEqual(by_class["bonds"].target_value, Decimal("300.00"))
        self.assertEqual(by_class["bonds"].amount, Decimal("100.00"))
        self.assertEqual(by_class["stocks"].target_value, Decimal("600.00"))
        self.assertEqual(by_class["stocks"].amount, Decimal("100.00"))

    def test_multiple_percentage_classes_split_remainder_proportionally(self):
        result = calculate(
            net_liquidation_value=Decimal("1000"), target_cash=Decimal(0),
            targets=[
                ClassTarget("us_stocks", Decimal("0.6")),
                ClassTarget("intl_stocks", Decimal("0.2")),
                ClassTarget("bonds", Decimal("0.2"), Decimal("200")),
            ],
            asset_classes={}, positions={},
        )
        targets = {item.asset_class: item.target_value for item in result}
        self.assertEqual(targets, {
            "bonds": Decimal("200.00"),
            "intl_stocks": Decimal("200.00"),
            "us_stocks": Decimal("600.00"),
        })

    def test_cash_buy_means_cash_increases(self):
        result = calculate_cash(
            current_cash=Decimal("100"), target_cash=Decimal("200"),
        )
        self.assertEqual(result.current_value, Decimal("100.00"))
        self.assertEqual(result.target_value, Decimal("200.00"))
        self.assertEqual(result.amount, Decimal("100.00"))
        self.assertEqual(result.action, "BUY")

    def test_cash_sell_means_cash_decreases(self):
        result = calculate_cash(
            current_cash=Decimal("100"), target_cash=Decimal("-100"),
        )
        self.assertEqual(result.amount, Decimal("-200.00"))
        self.assertEqual(result.action, "SELL")


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
