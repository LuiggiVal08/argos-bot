"""PositionSize value object.

The output of the RiskCalculator domain entity. It carries:
  - units: how many contracts/coins to buy.
  - sl_distance: stop-loss distance in quote currency per unit (the
    ATR at the time of calculation, per spec invariant #2).
  - entry_price: market price at the time the calculator ran. Stored
    so the executor can place a market order at the intended level
    and verify it was filled within tolerance.
  - notional_value: units * entry_price (total exposure in quote).
  - risk_amount: units * sl_distance (= free_balance * risk_pct; the
    actual money at risk if the SL is hit).

All amounts are Decimal to avoid float drift; the contract is that
each PositionSize is constructed with already-validated inputs, so
the value object itself does not re-validate (the domain entity
that builds it does).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class PositionSize:
    units: Decimal
    sl_distance: Decimal
    entry_price: Decimal
    notional_value: Decimal
    risk_amount: Decimal
    risk_pct: Decimal

    def __post_init__(self) -> None:
        if self.units < 0:
            raise ValueError(f"units must be >= 0, got {self.units}")
        if self.sl_distance < 0:
            raise ValueError(f"sl_distance must be >= 0, got {self.sl_distance}")
        if self.entry_price < 0:
            raise ValueError(f"entry_price must be >= 0, got {self.entry_price}")

    def to_dict(self) -> dict:
        return {
            "units": str(self.units),
            "sl_distance": str(self.sl_distance),
            "entry_price": str(self.entry_price),
            "notional_value": str(self.notional_value),
            "risk_amount": str(self.risk_amount),
            "risk_pct": str(self.risk_pct),
        }
