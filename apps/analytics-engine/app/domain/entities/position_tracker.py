"""Domain entity: PositionTracker.

Monitors open positions for SL/TP hits and computes P&L snapshots.
Pure-domain: receives a price tick and a LivePosition, returns a
TrackerVerdict (HOLD / SL_HIT / TP_HIT / PARTIAL_TP_HIT / BREAK_EVEN_ACTIVATED).
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
    PARTIAL_TP_HIT = "PARTIAL_TP_HIT"
    BREAK_EVEN_ACTIVATED = "BREAK_EVEN_ACTIVATED"
    TRAIL_ACTIVATED = "TRAIL_ACTIVATED"


@dataclass(frozen=True)
class TrackResult:
    """Result of checking a position against a price tick.

    Attributes:
        verdict:   HOLD | SL_HIT | TP_HIT | PARTIAL_TP_HIT.
        pnl:       Realized P&L if closed, unrealized if HOLD.
        pnl_pct:   P&L as fraction of entry (decimal).
        price:     The tick price that triggered the verdict.
        close_pct: Fraction of position to close (for partial TP).
        tp_level:  Which TP level was hit (1, 2, 3).
        new_sl_price: New SL price (for BE/trail activation).
    """
    verdict: TrackerVerdict
    pnl: Decimal = Decimal("0")
    pnl_pct: Decimal = Decimal("0")
    price: Decimal = Decimal("0")
    close_pct: Decimal = Decimal("0")
    tp_level: int = 0
    new_sl_price: Decimal | None = None


class PositionTracker:
    """Pure-domain tracker. Thread-safe, stateless.

    Methods receive a LivePosition + price, return a verdict.
    No I/O, no side effects.
    """

    @staticmethod
    def check(position: LivePosition, price: Decimal) -> TrackResult:
        """Check a position against a price tick.

        Returns HOLD if neither SL nor TP is hit, otherwise
        SL_HIT, TP_HIT, or PARTIAL_TP_HIT with the realized P&L.
        """
        is_sl = position.is_sl_hit(price)
        is_tp = position.is_tp_hit(price)
        is_tp2 = position.is_tp_hit(price, tp_level=2)
        is_tp3 = position.is_tp_hit(price, tp_level=3)

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

        if (
            is_tp
            and not is_tp2
            and not is_tp3
            and position.tp1_pct < Decimal("1")
            and (position.tp2_price is not None or position.tp3_price is not None)
        ):
            pnl = position.compute_pnl_at(price)
            return TrackResult(
                verdict=TrackerVerdict.PARTIAL_TP_HIT,
                pnl=pnl,
                pnl_pct=pnl / (position.entry_price * position.units)
                if position.entry_price * position.units > 0
                else Decimal("0"),
                price=price,
                close_pct=position.tp1_pct,
                tp_level=1,
            )

        if is_tp2:
            pnl = position.compute_pnl_at(price)
            return TrackResult(
                verdict=TrackerVerdict.PARTIAL_TP_HIT,
                pnl=pnl,
                pnl_pct=pnl / (position.entry_price * position.units)
                if position.entry_price * position.units > 0
                else Decimal("0"),
                price=price,
                close_pct=position.tp2_pct,
                tp_level=2,
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

    @staticmethod
    def check_partial_tp(
        position: LivePosition, price: Decimal
    ) -> TrackResult | None:
        """Check specifically for multi-level TP hits.

        Returns TrackResult with PARTIAL_TP_HIT if TP1 or TP2 is hit
        and position still has units to close at that level.
        None if no partial TP opportunity.
        """
        if position.tp_price is not None and position.is_tp_hit(price, tp_level=1):
            if position.status == "PARTIALLY_CLOSED" or position.tp1_pct >= Decimal("1"):
                return None
            pnl = position.compute_pnl_at(price)
            return TrackResult(
                verdict=TrackerVerdict.PARTIAL_TP_HIT,
                pnl=pnl,
                pnl_pct=pnl / (position.entry_price * position.units)
                if position.entry_price * position.units > 0
                else Decimal("0"),
                price=price,
                close_pct=position.tp1_pct,
                tp_level=1,
            )

        if position.tp2_price is not None and position.is_tp_hit(price, tp_level=2):
            pnl = position.compute_pnl_at(price)
            return TrackResult(
                verdict=TrackerVerdict.PARTIAL_TP_HIT,
                pnl=pnl,
                pnl_pct=pnl / (position.entry_price * position.units)
                if position.entry_price * position.units > 0
                else Decimal("0"),
                price=price,
                close_pct=position.tp2_pct,
                tp_level=2,
            )

        return None
