from datetime import date
from decimal import Decimal
import io
import unittest
from contextlib import redirect_stdout

from examples.income.core import (
    INFERRED_LONG, NOT_EQUITY, AccountIncome, Dividend, IncomeTotals, Sale,
)
from examples.income.main import print_account, print_taxable_totals
from examples.terminal import Style


ACCOUNT = AccountIncome(
    label="individual · 111", account_number="111", tax_advantaged=False,
    sales=(
        Sale(date(2026, 7, 15), "CRBN", Decimal("5.3481"), Decimal("253.52"),
             Decimal("383.45"), "equity", "long", INFERRED_LONG),
        Sale(date(2026, 9, 2), "ADA", Decimal("1"), Decimal("0.19"),
             Decimal("-0.01"), "other", "unknown", NOT_EQUITY),
    ),
    dividends=(
        Dividend(date(2026, 3, 1), "VT", Decimal("100"), Decimal("0.9")),
        Dividend(date(2026, 6, 1), "VT", Decimal("50"), Decimal("0.9")),
        Dividend(date(2026, 6, 1), "BNDW", Decimal("20"), None),
    ),
)


class PrintAccountTest(unittest.TestCase):
    def render(self, account: AccountIncome) -> str:
        output = io.StringIO()
        with redirect_stdout(output):
            print_account(account, 2026)
        return output.getvalue()

    def test_lists_sales_with_term_and_basis(self):
        rendered = self.render(ACCOUNT)
        self.assertIn("INCOME 2026 — individual · 111", rendered)
        self.assertIn("CRBN", rendered)
        self.assertIn("$383.45  LONG", rendered)
        self.assertIn(INFERRED_LONG, rendered)
        self.assertIn("-$0.01  ?", rendered)

    def test_groups_dividends_by_symbol(self):
        rendered = self.render(ACCOUNT)
        vt = next(line for line in rendered.splitlines() if line.startswith("VT "))
        self.assertIn("$150.00", vt)
        self.assertIn("$135.00", vt)
        self.assertIn("$15.00", vt)
        self.assertLess(rendered.index("BNDW "), rendered.index("VT "))

    def test_summary_splits_every_bucket(self):
        rendered = self.render(ACCOUNT)
        self.assertIn("Long-term gains                 $383.45", rendered)
        self.assertIn("Unknown-term gains               -$0.01", rendered)
        self.assertIn("Qualified dividends             $135.00", rendered)
        self.assertIn("Unclassified dividends           $20.00", rendered)

    def test_marks_retirement_accounts(self):
        rendered = self.render(AccountIncome(
            label="ira_roth · 222", account_number="222", tax_advantaged=True,
            sales=(), dividends=()))
        self.assertIn("tax-advantaged", rendered)
        self.assertIn("(no closing trades)", rendered)
        self.assertIn("(no reinvested dividends)", rendered)
        self.assertIn("Realized gains", rendered)
        self.assertNotIn("Long-term gains", rendered)

    def test_quantities_drop_trailing_zeros(self):
        account = AccountIncome(
            label="x", account_number="1", tax_advantaged=False,
            sales=(Sale(date(2026, 9, 2), "ADA", Decimal("1.000000000000000000"),
                        Decimal("0.19"), Decimal("-0.01"), "other", "unknown",
                        NOT_EQUITY),),
            dividends=())
        line = next(row for row in self.render(account).splitlines()
                    if row.startswith("2026-09-02"))
        self.assertNotIn("1.0", line)

    def test_taxable_total_points_at_config_when_something_is_unknown(self):
        output = io.StringIO()
        with redirect_stdout(output):
            print_taxable_totals(IncomeTotals(unclassified=Decimal(1)), 2026,
                                 Style(False))
        self.assertIn("income.yaml", output.getvalue())


if __name__ == "__main__":
    unittest.main()
