"""Replay an account's order history to recover the lots each sale closed.

The open tax lots only bound a sale's holding period. When the account's own
buys and sells explain the whole position — every share bought here, none
transferred in or out — replaying them first-in-first-out recovers exactly
which acquisitions each sale consumed, even for a position since closed.
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Iterable

from examples.income.core import ClosedPortion, decimal, eastern_date, text_field
from hood_normie.types import JsonObject


# Share quantities are reported to six decimal places.
QUANTITY_TOLERANCE = Decimal("0.000001")


@dataclass(frozen=True)
class Portion:
    """Some shares of one acquisition, closed by one sell order."""

    acquired: datetime
    quantity: Decimal
    cost_per_share: Decimal


Fill = tuple[datetime, str, str, Decimal, Decimal]


def fills(orders: Iterable[JsonObject], symbol: str) -> list[Fill]:
    """Every execution of the symbol, oldest first: (when, order id, side, qty, price)."""
    found: list[Fill] = []
    for order in orders:
        if str(order.get("symbol") or "").upper() != symbol:
            continue
        order_id = text_field(order, "id") or ""
        side = text_field(order, "side") or ""
        executions = order.get("executions")
        if not isinstance(executions, list):
            continue
        for execution in executions:
            if not isinstance(execution, dict):
                continue
            stamp = text_field(execution, "timestamp")
            quantity = execution.get("quantity")
            price = execution.get("price") or order.get("average_price")
            if stamp is None or quantity is None or price is None:
                continue
            moment = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            found.append((moment, order_id, side, decimal(quantity), decimal(price)))
    return sorted(found, key=lambda item: item[0])


def replay_fifo(
    orders: Iterable[JsonObject], symbol: str, current_quantity: Decimal
) -> dict[str, list[Portion]] | None:
    """Map each sell order to the acquisitions it closed, or None.

    None means the history does not explain the position — a sale outran the
    buys before it, or what remains differs from what the account holds — so
    shares moved in or out some other way and the replay cannot be trusted.
    """
    queue: list[Portion] = []
    closed: dict[str, list[Portion]] = {}
    for moment, order_id, side, quantity, price in fills(orders, symbol.upper()):
        if side == "buy":
            queue.append(Portion(moment, quantity, price))
            continue
        if side != "sell":
            continue
        remaining = quantity
        while remaining > QUANTITY_TOLERANCE:
            if not queue:
                return None
            lot = queue[0]
            used = min(lot.quantity, remaining)
            closed.setdefault(order_id, []).append(
                Portion(lot.acquired, used, lot.cost_per_share)
            )
            remaining -= used
            if lot.quantity - used > QUANTITY_TOLERANCE:
                queue[0] = Portion(lot.acquired, lot.quantity - used, lot.cost_per_share)
            else:
                queue.pop(0)
    left = sum((lot.quantity for lot in queue), Decimal(0))
    if abs(left - current_quantity) > QUANTITY_TOLERANCE:
        return None
    return closed


def acquired_date(portion: Portion) -> date:
    return eastern_date(portion.acquired.isoformat())


def closed_portions(
    orders: Iterable[JsonObject], symbol: str, current_quantity: Decimal
) -> dict[str, list[ClosedPortion]] | None:
    """`replay_fifo` in the shape `classify_sales` takes."""
    replayed = replay_fifo(orders, symbol, current_quantity)
    if replayed is None:
        return None
    return {
        order_id: [(acquired_date(item), item.quantity, item.cost_per_share)
                   for item in portions]
        for order_id, portions in replayed.items()
    }


def sell_fills(orders: Iterable[JsonObject], symbol: str) -> list[tuple[date, Decimal]]:
    """When and how many shares of a symbol were sold, by US Eastern date."""
    return [
        (eastern_date(moment.isoformat()), quantity)
        for moment, _, side, quantity, _ in fills(orders, symbol.upper())
        if side == "sell"
    ]
