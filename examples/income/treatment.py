"""Group income by how federal tax treats it: ordinary or preferential rates.

Short-term gains and non-qualified dividends are taxed like wages; long-term
gains and qualified dividends at the 0/15/20% rates. The buckets do not simply
add, though. Gains and losses net within each term first, then across terms
(Schedule D), and a net loss offsets only $3,000 of ordinary income a year,
carrying the rest forward. Dividends never absorb capital losses.

Nothing here is a tax figure. It groups income so that rates can be applied;
special cases (28% collectibles, REIT dividends' 199A deduction, the 3.8% net
investment income tax, state tax) are left to the reader.
"""

from dataclasses import dataclass
from decimal import Decimal

from examples.income.core import IncomeTotals


# The yearly cap on net capital losses against ordinary income ($1,500 when
# married filing separately).
LOSS_LIMIT = Decimal(3000)


@dataclass(frozen=True)
class Treatment:
    """Income by tax rate after netting capital gains and losses.

    `ordinary` is already reduced by `deductible_loss`, which is shown
    separately as a positive amount so the reader can see it was applied.
    """

    ordinary: Decimal = Decimal(0)
    preferential: Decimal = Decimal(0)
    deductible_loss: Decimal = Decimal(0)
    carryforward: Decimal = Decimal(0)

    def __sub__(self, other: "Treatment") -> "Treatment":
        return Treatment(
            ordinary=self.ordinary - other.ordinary,
            preferential=self.preferential - other.preferential,
            deductible_loss=self.deductible_loss - other.deductible_loss,
            carryforward=self.carryforward - other.carryforward,
        )


@dataclass(frozen=True)
class TreatmentRange:
    """What is known, and where the unresolved amounts could land.

    Unknown-term gains may be short or long; unclassified dividends may be
    qualified or not. `all_ordinary` puts every unresolved amount at ordinary
    rates and `all_preferential` at preferential ones. For gains that is the
    worst and best case; unresolved losses reverse it.
    """

    known: Treatment
    all_ordinary: Treatment
    all_preferential: Treatment
    unresolved_gains: Decimal
    unresolved_dividends: Decimal

    @property
    def resolved(self) -> bool:
        return self.unresolved_gains == 0 and self.unresolved_dividends == 0

    def __sub__(self, other: "TreatmentRange") -> "TreatmentRange":
        return TreatmentRange(
            known=self.known - other.known,
            all_ordinary=self.all_ordinary - other.all_ordinary,
            all_preferential=self.all_preferential - other.all_preferential,
            unresolved_gains=self.unresolved_gains - other.unresolved_gains,
            unresolved_dividends=self.unresolved_dividends - other.unresolved_dividends,
        )


def net_capital(short: Decimal, long: Decimal) -> tuple[Decimal, Decimal, Decimal]:
    """Schedule D netting: (net short-term gain, net long-term gain, net loss).

    When one term is a loss and the other a larger gain, what is left keeps
    the gain's character. At most one of the three is non-zero.
    """
    if short >= 0 and long >= 0:
        return short, long, Decimal(0)
    total = short + long
    if total <= 0:
        return Decimal(0), Decimal(0), -total
    return (total, Decimal(0), Decimal(0)) if short > 0 else (Decimal(0), total, Decimal(0))


def treat(short: Decimal, long: Decimal, qualified: Decimal,
          nonqualified: Decimal) -> Treatment:
    short_gain, long_gain, loss = net_capital(short, long)
    deductible = min(LOSS_LIMIT, loss)
    return Treatment(
        ordinary=short_gain + nonqualified - deductible,
        preferential=long_gain + qualified,
        deductible_loss=deductible,
        carryforward=loss - deductible,
    )


def treatment_range(totals: IncomeTotals, carryover_short: Decimal = Decimal(0),
                    carryover_long: Decimal = Decimal(0)) -> TreatmentRange:
    """Group a year's (or a year-to-date's) totals by rate.

    Last year's carried-over losses enter as losses of their own character.
    """
    short = totals.short_term - carryover_short
    long = totals.long_term - carryover_long
    unknown = totals.unknown_term
    unclassified = totals.unclassified
    return TreatmentRange(
        known=treat(short, long, totals.qualified, totals.nonqualified),
        all_ordinary=treat(short + unknown, long, totals.qualified,
                           totals.nonqualified + unclassified),
        all_preferential=treat(short, long + unknown, totals.qualified + unclassified,
                               totals.nonqualified),
        unresolved_gains=unknown,
        unresolved_dividends=unclassified,
    )


def period_treatments(cumulative_totals: list[IncomeTotals],
                      carryover_short: Decimal = Decimal(0),
                      carryover_long: Decimal = Decimal(0),
                      ) -> tuple[list[TreatmentRange], list[TreatmentRange]]:
    """Year-to-date treatment through each period, and each period's share.

    Netting only makes sense over a running total, so a period's own figure is
    the change in the year-to-date one; the four add up to the year.
    """
    running = [treatment_range(item, carryover_short, carryover_long)
               for item in cumulative_totals]
    # Measured from nothing, so a carried-over loss lands in the first period.
    zero = treatment_range(IncomeTotals())
    own = [current - previous for previous, current in zip([zero, *running], running)]
    return running, own
