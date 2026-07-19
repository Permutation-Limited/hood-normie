import io
import unittest
from contextlib import redirect_stdout

from examples.list_holdings import _account_label, _all_account_numbers, print_holdings
from examples.terminal import Style


class ListHoldingsTest(unittest.TestCase):
    def test_extracts_all_account_numbers(self) -> None:
        self.assertEqual(
            _all_account_numbers({"accounts": [
                {"accountNumber": "111"},
                {"brokerage_account_number": "222"},
            ]}),
            ["111", "222"],
        )

    def test_prints_sorted_holdings_and_values(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            print_holdings("ABC123", [
                {"symbol": "VTI", "quantity": "2", "price": "250.50"},
                {"symbol": "BND", "quantity": "3.5", "price": "72"},
            ], "100")
        rendered = output.getvalue()
        self.assertIn("HOLDINGS — ABC123", rendered)
        self.assertLess(rendered.index("BND"), rendered.index("VTI"))
        self.assertIn("$     252.00", rendered)
        self.assertIn("$     501.00", rendered)
        self.assertIn("$     100.00", rendered)
        self.assertIn("$     853.00", rendered)

    def test_prints_empty_account(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            print_holdings("ABC123", [], "25")
        self.assertIn("(no equity positions)", output.getvalue())
        self.assertIn("$      25.00", output.getvalue())

    def test_builds_descriptive_account_label(self) -> None:
        self.assertEqual(
            _account_label("ABC123", {
                "brokerageAccountType": "Roth IRA",
                "nickname": "Retirement",
            }),
            "Roth IRA · Retirement · ABC123",
        )

    def test_colorizes_heading_and_header(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            print_holdings("Individual · Main · ABC123", [], 0, Style(True))
        rendered = output.getvalue()
        self.assertIn("\033[1m\033[36m◆ HOLDINGS", rendered)
        self.assertIn("\033[2mSYMBOL", rendered)


if __name__ == "__main__":
    unittest.main()
