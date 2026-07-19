import io
import unittest
from contextlib import redirect_stdout

from examples.list_accounts import print_accounts


class PrintAccountsTest(unittest.TestCase):
    def test_prints_common_field_variants(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            print_accounts([
                {
                    "taxStatus": "Individual",
                    "accountType": "cash",
                    "accountNumber": "ABC123",
                    "displayName": "Main",
                },
                {
                    "retirement_account_type": "Roth IRA",
                    "account_type": "margin",
                    "brokerage_account_number": "XYZ789",
                    "nickname": "Retirement",
                },
            ])
        rendered = output.getvalue()
        self.assertIn("TAX STATUS", rendered)
        self.assertIn("CASH", rendered)
        self.assertIn("ACCOUNT NUMBER", rendered)
        self.assertIn("NICKNAME", rendered)
        self.assertIn("Individual", rendered)
        self.assertIn("Roth IRA", rendered)
        self.assertIn("margin", rendered)
        self.assertIn("XYZ789", rendered)
        self.assertIn("Retirement", rendered)

    def test_handles_no_accounts(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            print_accounts([])
        self.assertEqual(output.getvalue(), "No Robinhood accounts found.\n")


if __name__ == "__main__":
    unittest.main()
