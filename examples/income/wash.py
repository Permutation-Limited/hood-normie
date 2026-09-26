"""Flag loss sales that a purchase within 30 days may turn into wash sales.

A loss is disallowed to the extent substantially identical shares were bought
within 30 days before or after the sale — in any account, DRIP included. When
the replacement is in an IRA the loss is gone for good; otherwise it moves into
the replacement's basis. Only the same ticker is checked, and only equities:
the rule does not currently reach crypto.

These are flags, not adjustments. Robinhood's realized gain may already
account for a wash sale, and the MCP server does not say whether it does.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Callable, Iterable

from examples.income.core import EQUITY, Replacement, Sale, WashSale


WASH_WINDOW = timedelta(days=30)


@dataclass
class Purchase:
    """Shares bought, with how many are still free to replace a later loss."""

    symbol: str
    when: date
    account_number: str
    account_label: str
    tax_advantaged: bool
    quantity: Decimal
    unused: Decimal = field(init=False)

    def __post_init__(self) -> None:
        self.unused = self.quantity


@dataclass(frozen=True)
class LossSale:
    account_number: str
    account_label: str
    sale: Sale


# Shares of a symbol an account still held after the end of a given day.
HeldAfter = Callable[[str, str, date], Decimal]


def find_wash_sales(loss_sales: Iterable[LossSale], purchases: Iterable[Purchase],
                    held_after: HeldAfter) -> list[WashSale]:
    """Match each equity loss to purchases inside its window, earliest first.

    A purchase replaces at most its own shares once across all losses. A buy
    in the selling account on or before the sale day may be the very shares
    sold, so those count only up to what the account still held afterwards.
    """
    pool = sorted(purchases, key=lambda item: item.when)
    found: list[WashSale] = []
    for loss in sorted(loss_sales, key=lambda item: item.sale.when):
        sale = loss.sale
        if sale.gain >= 0 or sale.asset != EQUITY or sale.quantity <= 0:
            continue
        needed = sale.quantity
        own_allowance = held_after(loss.account_number, sale.symbol, sale.when)
        used: list[Replacement] = []
        permanent = Decimal(0)
        for purchase in pool:
            if needed <= 0:
                break
            if (purchase.symbol != sale.symbol or purchase.unused <= 0
                    or abs(purchase.when - sale.when) > WASH_WINDOW):
                continue
            available = purchase.unused
            same_account_before = (purchase.account_number == loss.account_number
                                   and purchase.when <= sale.when)
            if same_account_before:
                available = min(available, own_allowance)
            take = min(available, needed)
            if take <= 0:
                continue
            purchase.unused -= take
            needed -= take
            if same_account_before:
                own_allowance -= take
            if purchase.tax_advantaged:
                permanent += take
            used.append(Replacement(purchase.when, purchase.account_label,
                                    purchase.tax_advantaged, take))
        if not used:
            continue
        replaced = sale.quantity - needed
        loss_per_share = -sale.gain / sale.quantity
        found.append(WashSale(
            account_label=loss.account_label, sale=sale,
            replacements=tuple(used), replaced=replaced,
            disallowed=(loss_per_share * replaced).quantize(Decimal("0.01")),
            permanent=(loss_per_share * permanent).quantize(Decimal("0.01")),
        ))
    return found
