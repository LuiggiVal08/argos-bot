"""Domain entity: CalculadorRiesgo (RiskCalculator).

Spec section 5 Historia 2: "la capa de Dominio calcule el tamaño
de la posición basándose en el balance libre y el ATR, para que la
pérdida máxima potencial nunca supere el 1% por operación."

Pure domain. No I/O. The application layer feeds it inputs (free
balance, current ATR, current price) and gets back a PositionSize
with units, SL distance, and the implied risk amount.

The formula is the standard fractional position sizing:

    units       = (free_balance * risk_pct) / sl_distance
    risk_amount = free_balance * risk_pct          (capped at 1% of balance)
    notional    = units * entry_price              (total exposure)

The SL distance is set to the ATR (per spec invariant #2: SL
distance is derived from ATR, not from a fixed percentage). This
makes the position size automatically shrink when volatility rises,
which is the entire point of the rule.
"""
from __future__ import annotations

from decimal import Decimal

from ..value_objects.atr import Atr
from ..value_objects.position_size import PositionSize
from ..value_objects.risk_pct import RiskPct


class InvalidFreeBalanceError(ValueError):
    """Raised when free_balance is non-positive. The use case must
    surface this as a critical abort per spec sad path."""


class InvalidEntryPriceError(ValueError):
    """Raised when entry_price is non-positive."""


class RiskCalculator:
    """Pure domain entity. Stateless and thread-safe."""

    def calculate(
        self,
        free_balance: Decimal,
        atr: Atr,
        entry_price: Decimal,
        risk_pct: RiskPct,
    ) -> PositionSize:
        if free_balance <= 0:
            raise InvalidFreeBalanceError(
                f"free_balance must be > 0, got {free_balance}"
            )
        if entry_price <= 0:
            raise InvalidEntryPriceError(
                f"entry_price must be > 0, got {entry_price}"
            )

        sl_distance = atr.value
        risk_amount = free_balance * risk_pct.value
        # units = risk_amount / sl_distance
        # We round DOWN to the lot step (the use case is responsible
        # for further rounding to the exchange's lot step if needed).
        units = (risk_amount / sl_distance).quantize(Decimal("0.00000001"))
        notional_value = units * entry_price

        return PositionSize(
            units=units,
            sl_distance=sl_distance,
            entry_price=entry_price,
            notional_value=notional_value,
            risk_amount=risk_amount,
            risk_pct=risk_pct.value,
        )
