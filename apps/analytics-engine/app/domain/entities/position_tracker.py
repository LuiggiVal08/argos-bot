"""Domain entity: PositionTracker.

Monitors open positions for SL/TP hits and computes P&L snapshots.
Pure-domain: receives a price tick and a LivePosition, returns a
TrackerVerdict (HOLD / SL_HIT / TP_HIT).

The application layer feeds ticks into this entity and acts on the
verdict (close position, log P&L, etc.).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from ..value_objects.live_position import LivePosition


class TrackerVerdict(str, Enum):
    HOLD = "HOLD"
    SL_HIT = "SL_HIT"
    TP_HIT = "TP_HIT"


@dataclass(frozen=True)
class TrackResult:
    """Result of checking a position against a price tick.

    Attributes:
        verdict:   HOLD | SL_HIT | TP_HIT.
        pnl:       Realized P&L if closed, unrealized if HOLD.
        pnl_pct:   P&L as fraction of entry (decimal).
        price:     The tick price that triggered the verdict.
    """
    verdict: TrackerVerdict
    pnl: Decimal = Decimal("0")
    pnl_pct: Decimal = Decimal("0")
    price: Decimal = Decimal("0")


class PositionTracker:
    """Pure-domain tracker. Thread-safe, stateless.

    Methods receive a LivePosition + price, return a verdict.
    No I/O, no side effects.
    """

    @staticmethod
    def check(position: LivePosition, price: Decimal) -> TrackResult:
        """Check a position against a price tick.

        Returns HOLD if neither SL nor TP is hit, otherwise
        SL_HIT or TP_HIT with the realized P&L.
        """
        is_sl = position.is_sl_hit(price)
        is_tp = position.is_tp_hit(price)

        if is_sl:
            pnl = position.compute_pnl_at(price)
            return TrackResult(
                verdict=TrackerVerdict.SL_HIT,
                pnl=pnl,
                pnl_pct=pnl / (position.entry_price * position.units)
                if position.entry_price * position.units > 0
                else Decimal("0"),
                price=price,
            )

        if is_tp:
            pnl = position.compute_pnl_at(price)
            return TrackResult(
                verdict=TrackerVerdict.TP_HIT,
                pnl=pnl,
                pnl_pct=pnl / (position.entry_price * position.units)
                if position.entry_price * position.units > 0
                else Decimal("0"),
                price=price,
            )

        pnl = position.compute_pnl_at(price)
        return TrackResult(
            verdict=TrackerVerdict.HOLD,
            pnl=pnl,
            pnl_pct=position.pnl_pct,
            price=price,
        )
