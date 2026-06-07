"""RiskPct value object.

Risk per trade, expressed as a decimal. Per spec invariant #1, the
default is 0.01 (1%) and the hard cap is 0.02 (2%) — the domain
rejects anything above the cap with `InvalidRiskPctError`.

Why a cap at 2%? Spec section 5 Historia 2 says: "la pérdida máxima
potencial nunca supere el 1% por operación". The cap leaves headroom
for system calibration (1.5%, 1.8%) while making it impossible to
silently configure 5% or 10% trades.
"""
from __future__ import annotations

from decimal import Decimal

# Hard cap from spec §5 Historia 2 (risk_pct > 2% violates the spec).
MAX_RISK_PCT = Decimal("0.02")

# Default from spec: 1% per trade.
DEFAULT_RISK_PCT = Decimal("0.01")


class InvalidRiskPctError(ValueError):
    """Raised when RiskPct is not in the (0, MAX_RISK_PCT] interval."""


class RiskPct:
    __slots__ = ("_value",)

    def __init__(self, value: Decimal | float | int | str) -> None:
        d = Decimal(str(value)) if not isinstance(value, Decimal) else value
        if d <= 0:
            raise InvalidRiskPctError(f"RiskPct must be > 0, got {d}")
        if d > MAX_RISK_PCT:
            raise InvalidRiskPctError(
                f"RiskPct {d} exceeds the {MAX_RISK_PCT} spec cap "
                f"(spec section 5 Historia 2)"
            )
        self._value = d

    @property
    def value(self) -> Decimal:
        return self._value

    @classmethod
    def default(cls) -> "RiskPct":
        return cls(DEFAULT_RISK_PCT)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, RiskPct) and self._value == other._value

    def __hash__(self) -> int:
        return hash(self._value)

    def __repr__(self) -> str:
        return f"RiskPct({self._value})"
