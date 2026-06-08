"""DrawdownSnapshot VO: a frozen view of the day's P&L state.

Constructed at "open day" (UTC 00:00) with `starting_balance` and
captured again at any point with `current_balance` and the implied
drawdown. The CircuitBreaker entity is the only place that
combines these two into a verdict.

Validation rules (per spec invariant #3 — drawdown circuit breaker):
  - starting_balance > 0 (no division by zero in the dd formula).
  - current_balance >= 0 (a negative balance is a hard error;
    means the journal is corrupt, not that the bot is bankrupt).
  - The drawdown percentage is derived, not stored, so it cannot
    drift from the balances.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal


class InvalidDrawdownSnapshotError(ValueError):
    """Raised when balances are invalid (zero / negative starting
    or negative current)."""


@dataclass(frozen=True)
class DrawdownSnapshot:
    starting_balance: Decimal
    current_balance: Decimal
    taken_at: datetime

    def __post_init__(self) -> None:
        if self.starting_balance <= 0:
            raise InvalidDrawdownSnapshotError(
                f"starting_balance must be > 0, got {self.starting_balance}"
            )
        if self.current_balance < 0:
            raise InvalidDrawdownSnapshotError(
                f"current_balance must be >= 0, got {self.current_balance}"
            )

    @property
    def drawdown_pct(self) -> Decimal:
        """Decimal in [0, 1]. 0 = no loss; 0.05 = 5% loss."""
        if self.current_balance >= self.starting_balance:
            return Decimal("0")
        return (
            self.starting_balance - self.current_balance
        ) / self.starting_balance

    @property
    def is_profitable(self) -> bool:
        return self.current_balance > self.starting_balance

    @classmethod
    def at_open(cls, starting_balance: Decimal) -> "DrawdownSnapshot":
        """Snapshot taken at UTC 00:00 (open day). current_balance
        equals starting_balance, drawdown is 0."""
        return cls(
            starting_balance=starting_balance,
            current_balance=starting_balance,
            taken_at=datetime.now(tz=timezone.utc),
        )
