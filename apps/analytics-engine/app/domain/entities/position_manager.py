"""Domain entity: PositionManager.

Gestión inteligente de posiciones abiertas (H30):

1. Break Even: cuando profit >= 1R, migrar SL a entry price.
2. Trailing Stop: cuando profit >= 2R, activar trailing (SL sigue al precio).
3. Dynamic SL: si ATR se expande, ajustar SL dinámicamente.
4. Partial TP: cierres parciales en niveles TP1/TP2/TP3.

Invariantes:
- SL distance = 1.5 × ATR (configurable)
- BE activation at 1R
- Trail activation at 2R
- TP1 = 50%, TP2 = 25%, TP3 = 25% trailing (configurable)
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from ..value_objects.live_position import LivePosition
from ..value_objects.order import OrderSide


class PositionAction(Enum):
    HOLD = "HOLD"
    CLOSE = "CLOSE"
    PARTIAL_CLOSE = "PARTIAL_CLOSE"
    UPDATE_SL = "UPDATE_SL"
    ACTIVATE_BREAK_EVEN = "ACTIVATE_BREAK_EVEN"
    ACTIVATE_TRAIL = "ACTIVATE_TRAIL"


@dataclass(frozen=True)
class PositionDecision:
    action: PositionAction
    close_pct: Decimal = Decimal("0")
    new_sl_price: Decimal | None = None
    reason: str = ""
    tp_level: int = 0


class PositionManager:
    """Pure-domain entity for intelligent position management.

    Stateless — all methods receive position + market data,
    return a PositionDecision.
    """

    SL_MULTIPLE: Decimal = Decimal("1.5")
    BE_ACTIVATION_R: Decimal = Decimal("1.0")
    TRAIL_ACTIVATION_R: Decimal = Decimal("2.0")
    TRAIL_OFFSET_MULTIPLE: Decimal = Decimal("1.5")

    def evaluate(
        self,
        position: LivePosition,
        current_price: Decimal,
        atr: Decimal | None = None,
    ) -> PositionDecision:
        """Evaluate position and return next action.

        Priority order:
          1. Check SL/TP hit (close or partial close)
          2. Check Break Even activation
          3. Check Trailing Stop activation
          4. Update trailing SL if active
          5. HOLD
        """
        if not position.is_open:
            return PositionDecision(action=PositionAction.HOLD, reason="position_closed")

        # 1. SL hit → close full position
        if position.is_sl_hit(current_price):
            return PositionDecision(
                action=PositionAction.CLOSE,
                reason="stop_loss_hit",
            )

        # 2. TP1 hit → partial close (50%)
        # Skip if position is already partially closed (TP1 was already hit)
        if position.status != "PARTIALLY_CLOSED":
            if position.is_tp_hit(current_price, tp_level=1) and position.units > 0:
                close_amount = position.tp1_pct
                if close_amount >= Decimal("1"):
                    return PositionDecision(
                        action=PositionAction.CLOSE,
                        reason="tp1_full_close",
                    )
                return PositionDecision(
                    action=PositionAction.PARTIAL_CLOSE,
                    close_pct=close_amount,
                    tp_level=1,
                    reason="tp1_hit_partial_close",
                )

        # 3. TP2 hit → partial close (25%)
        if position.is_tp_hit(current_price, tp_level=2) and position.units > 0:
            close_amount = position.tp2_pct
            return PositionDecision(
                action=PositionAction.PARTIAL_CLOSE,
                close_pct=close_amount,
                tp_level=2,
                reason="tp2_hit_partial_close",
            )

        # 4. TP3 hit → close remaining
        if position.is_tp_hit(current_price, tp_level=3) and position.units > 0:
            return PositionDecision(
                action=PositionAction.CLOSE,
                reason="tp3_hit_full_close",
            )

        # 5. Check Break Even (1R)
        if not position.break_even_activated:
            r_multiple = self._compute_risk_multiple(position, current_price)
            if r_multiple >= self.BE_ACTIVATION_R:
                new_sl = position.entry_price
                return PositionDecision(
                    action=PositionAction.ACTIVATE_BREAK_EVEN,
                    new_sl_price=new_sl,
                    reason=f"break_even_at_{r_multiple:.1f}R",
                )

        # 6. Check Trailing Stop activation (2R)
        if not position.trail_activated:
            r_multiple = self._compute_risk_multiple(position, current_price)
            if r_multiple >= self.TRAIL_ACTIVATION_R:
                offset = self._compute_trail_offset(position, atr)
                new_sl = self._compute_trailing_sl(position, current_price, offset)
                return PositionDecision(
                    action=PositionAction.ACTIVATE_TRAIL,
                    new_sl_price=new_sl,
                    reason=f"trail_activated_at_{r_multiple:.1f}R",
                )

        # 7. Update trailing SL if active
        if position.trail_activated:
            offset = position.trail_offset or self._compute_trail_offset(position, atr)
            new_sl = self._compute_trailing_sl(position, current_price, offset)
            if position.sl_price is None or (
                position.side == OrderSide.BUY and new_sl > position.sl_price
            ) or (
                position.side == OrderSide.SELL and new_sl < position.sl_price
            ):
                return PositionDecision(
                    action=PositionAction.UPDATE_SL,
                    new_sl_price=new_sl,
                    reason="trailing_stop_update",
                )

        return PositionDecision(action=PositionAction.HOLD, reason="no_action")

    def _compute_risk_multiple(
        self, position: LivePosition, current_price: Decimal
    ) -> Decimal:
        """Compute current profit as multiple of risk (R)."""
        risk_amount = position.compute_risk_amount()
        if risk_amount is None or risk_amount <= 0:
            return Decimal("0")
        pnl = position.compute_pnl_at(current_price)
        if risk_amount == 0:
            return Decimal("0")
        return pnl / risk_amount

    def _compute_trail_offset(
        self, position: LivePosition, atr: Decimal | None
    ) -> Decimal:
        if atr is not None and atr > 0:
            return atr * self.TRAIL_OFFSET_MULTIPLE
        if position.atr_at_entry is not None and position.atr_at_entry > 0:
            return position.atr_at_entry * self.TRAIL_OFFSET_MULTIPLE
        return Decimal("0")

    @staticmethod
    def _compute_trailing_sl(
        position: LivePosition, current_price: Decimal, offset: Decimal
    ) -> Decimal:
        if position.side == OrderSide.BUY:
            return current_price - offset
        return current_price + offset
