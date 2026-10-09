from decimal import Decimal
import io
import unittest
from contextlib import redirect_stdout

from examples.unrealized.core import Holding, totals
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
        header, vt, bynd, total = rendered
        self.assertTrue(vt.startswith("VT "))
        self.assertIn("$587.35", vt)
        self.assertIn("+58.7%", vt)
        self.assertIn("(average cost)", bynd)
        self.assertIn("-$3,179.99", bynd)
        # Values end where their headers do.
        self.assertEqual(total.index("$1,667.74") + len("$1,667.74"),
                         header.index("VALUE") + len("VALUE"))

    def test_unpriced_holdings_are_called_out(self):
        rendered = self.render((Holding("XX", D(1), None, D(5), "tax lots"),))
        self.assertIn("—", rendered)
        self.assertIn("left out of the total", rendered)

    def test_empty_account(self):
        self.assertIn("(no equity positions)", self.render(()))


if __name__ == "__main__":
    unittest.main()
