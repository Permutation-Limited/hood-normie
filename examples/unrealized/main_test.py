from decimal import Decimal
import io
import unittest
from contextlib import redirect_stdout

from datetime import date

from examples.unrealized.core import Holding, Lot, totals
from examples.unrealized.main import print_holdings


D = Decimal


class PrintHoldingsTest(unittest.TestCase):
    def render(self, holdings: tuple[Holding, ...]) -> str:
        output = io.StringIO()
        with redirect_stdout(output):
            print_holdings(holdings, totals(holdings))
        return output.getvalue()

    def test_columns_and_total_line_up(self):
        rendered = self.render((
            Holding("VT", D("10"), D("158.735"), D("1000"), "tax lots"),
            Holding("BYND", D("10.4"), D("7.73"), D("3260.38"), "average cost"),
        )).splitlines()
        header, vt, bynd, total = rendered[:4]
        self.assertTrue(vt.startswith("VT "))
        self.assertIn("$587.35", vt)
        self.assertIn("+58.7%", vt)
        self.assertIn("(average cost)", bynd)
        self.assertIn("-$3,179.99", bynd)
        # Values end where their headers do.
        self.assertEqual(total.index("$1,667.74") + len("$1,667.74"),
                         header.index("VALUE") + len("VALUE"))

    def test_lots_print_beneath_their_holding_with_term_dates(self):
        lots = (Lot(date(2021, 5, 1), D(6), D(600), "long"),
                Lot(date(2026, 9, 1), D(4), D(520), "short"))
        item = Holding("VT", D(10), D(150), D(1120), "tax lots", lots)
        output = io.StringIO()
        with redirect_stdout(output):
            print_holdings((item,), totals((item,)), show_lots=True)
        rendered = output.getvalue().splitlines()
        self.assertTrue(rendered[2].startswith("  2021-05-01 LONG"))
        self.assertIn("long-term 2027-09-02", rendered[3])
        # Lot dollar columns end where the holding row's do.
        self.assertEqual(rendered[2].index("$900.00") + 7,
                         rendered[0].index("VALUE") + 5)
        self.assertIn("$80.00", rendered[1])   # short-term part
        self.assertIn("$300.00", rendered[1])  # long-term part

    def test_unpriced_holdings_are_called_out(self):
        rendered = self.render((Holding("XX", D(1), None, D(5), "tax lots"),))
        self.assertIn("—", rendered)
        self.assertIn("left out of the total", rendered)

    def test_empty_account(self):
        self.assertIn("(no equity positions)", self.render(()))


if __name__ == "__main__":
    unittest.main()
