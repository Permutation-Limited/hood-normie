from decimal import Decimal
import unittest

from examples.income.core import IncomeTotals
from examples.income.treatment import (
    Treatment, net_capital, period_treatments, treat, treatment_range,
)


D = Decimal


class NetCapitalTest(unittest.TestCase):
    def test_gains_in_both_terms_keep_their_character(self):
        self.assertEqual(net_capital(D(100), D(200)), (D(100), D(200), D(0)))

    def test_a_short_term_loss_offsets_long_term_gains_first(self):
        self.assertEqual(net_capital(D(-300), D(1000)), (D(0), D(700), D(0)))

    def test_a_long_term_loss_offsets_short_term_gains(self):
        self.assertEqual(net_capital(D(1000), D(-300)), (D(700), D(0), D(0)))

    def test_an_overall_loss_is_a_net_loss(self):
        self.assertEqual(net_capital(D(-300), D(100)), (D(0), D(0), D(200)))
        self.assertEqual(net_capital(D(-300), D(-100)), (D(0), D(0), D(400)))


class TreatTest(unittest.TestCase):
    def test_groups_dividends_with_their_matching_gains(self):
        self.assertEqual(treat(D(100), D(200), D(50), D(25)),
                         Treatment(ordinary=D(125), preferential=D(250)))

    def test_net_loss_offsets_ordinary_income_up_to_the_limit(self):
        result = treat(D(-2000), D(-4000), qualified=D(500), nonqualified=D(800))
        self.assertEqual(result, Treatment(
            ordinary=D(800) - D(3000), preferential=D(500),
            deductible_loss=D(3000), carryforward=D(3000),
        ))

    def test_losses_never_absorb_qualified_dividends(self):
        result = treat(D(0), D(-1000), qualified=D(5000), nonqualified=D(0))
        self.assertEqual(result.preferential, D(5000))
        self.assertEqual(result.ordinary, D(-1000))


class RangeTest(unittest.TestCase):
    def test_unresolved_amounts_bound_both_groups(self):
        totals = IncomeTotals(long_term=D(1000), unknown_term=D(400),
                              qualified=D(100), unclassified=D(50))
        result = treatment_range(totals)
        self.assertFalse(result.resolved)
        self.assertEqual((result.known.ordinary, result.known.preferential),
                         (D(0), D(1100)))
        self.assertEqual((result.all_ordinary.ordinary,
                          result.all_ordinary.preferential), (D(450), D(1100)))
        self.assertEqual((result.all_preferential.ordinary,
                          result.all_preferential.preferential), (D(0), D(1550)))

    def test_carryover_enters_as_a_loss_of_its_own_character(self):
        result = treatment_range(IncomeTotals(long_term=D(1000)),
                                 carryover_short=D(1500))
        self.assertEqual(result.known.deductible_loss, D(500))
        self.assertEqual(result.known.preferential, D(0))


class PeriodTreatmentsTest(unittest.TestCase):
    def test_each_period_is_the_change_in_the_running_treatment(self):
        running_totals = [IncomeTotals(long_term=D(-5000)),
                          IncomeTotals(long_term=D(-5000), short_term=D(4000)),
                          IncomeTotals(long_term=D(-5000), short_term=D(4000)),
                          IncomeTotals(long_term=D(-5000), short_term=D(4000),
                                       qualified=D(10))]
        running, own = period_treatments(running_totals)
        self.assertEqual(running[0].known.deductible_loss, D(3000))
        self.assertEqual(running[0].known.carryforward, D(2000))
        # The short-term gain in period two eats the loss the first one deducted.
        self.assertEqual(own[1].known.ordinary, D(2000))
        self.assertEqual(sum((item.known.ordinary for item in own), D(0)),
                         running[-1].known.ordinary)
        self.assertEqual(own[3].known.preferential, D(10))

    def test_carryover_lands_in_the_first_period(self):
        running, own = period_treatments([IncomeTotals()] * 4, carryover_long=D(100))
        self.assertEqual(own[0].known.ordinary, D(-100))
        self.assertEqual(own[1].known.ordinary, D(0))


if __name__ == "__main__":
    unittest.main()
