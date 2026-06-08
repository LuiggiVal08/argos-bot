"""Domain entity: CircuitBreaker.

Pure-domain. Stateless except for the configured threshold. The
application layer feeds it a `DrawdownSnapshot` and gets back
a `DrawdownState`.

Verdict logic (matches the opencode `risk_drawdown_check` tool):
  - dd >= threshold     → TRIP
  - dd >= 0.6 * threshold → WARN
  - else                → SAFE

The "0.6 * threshold" WARN line is the spec's calibration hook:
it gives the operator a soft warning at 3% (with a 5% trip)
without being too chatty. We don't bake the 0.6 magic number
in — it's a default the application layer can override.

Sad path: TRIP triggers a `TripAction.canonical()` which the
application use case materialises (cancel orders, close
positions, set PASIVO, halt).
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from ..value_objects.drawdown_snapshot import (
    DrawdownSnapshot,
    InvalidDrawdownSnapshotError,
)
from ..value_objects.drawdown_state import DrawdownState
from ..value_objects.trip_action import TripAction, TripStep

# Default WARN ratio: 60% of the trip threshold. The opencode tool
# uses the same ratio so the two stay aligned.
DEFAULT_WARN_RATIO = Decimal("0.6")


class InvalidThresholdError(ValueError):
    """Raised when threshold is not in (0, 1]."""


class CircuitBreaker:
    """Pure-domain. Thread-safe and stateless.

    Constructor args:
      threshold: trip threshold as a decimal (e.g. 0.05 for 5%).
      warn_ratio: ratio of `threshold` at which WARN fires
        (default 0.6, matching the opencode tool).
    """

    def __init__(
        self,
        threshold: Decimal | float = Decimal("0.05"),
        warn_ratio: Decimal | float = DEFAULT_WARN_RATIO,
    ) -> None:
        t = Decimal(str(threshold))
        w = Decimal(str(warn_ratio))
        if not (Decimal("0") < t <= Decimal("1")):
            raise InvalidThresholdError(
                f"threshold must be in (0, 1], got {t}"
            )
        if not (Decimal("0") < w <= Decimal("1")):
            raise InvalidThresholdError(
                f"warn_ratio must be in (0, 1], got {w}"
            )
        # warn_ratio is a fraction of `threshold` (e.g. 0.6 = WARN at
        # 60% of the trip). It is NOT compared directly to threshold.
        self._threshold = t
        self._warn_ratio = w

    @property
    def threshold(self) -> Decimal:
        return self._threshold

    @property
    def warn_threshold(self) -> Decimal:
        return self._threshold * self._warn_ratio

    def evaluate(
        self, snapshot: DrawdownSnapshot, current_state: DrawdownState | None = None
    ) -> DrawdownState:
        """Return the verdict for a snapshot. If the bot is already
        HALTED, return HALTED (don't downgrade) so the use case
        doesn't accidentally re-arm the breaker."""
        if current_state is DrawdownState.HALTED:
            return DrawdownState.HALTED
        dd = snapshot.drawdown_pct
        if dd >= self._threshold:
            return DrawdownState.TRIP
        if dd >= self.warn_threshold:
            return DrawdownState.WARN
        return DrawdownState.SAFE

    def trip_action(self) -> TripAction:
        """The canonical trip action for this breaker. Always returns
        the same ordered list (cancel → close → set PASIVO → halt)."""
        return TripAction.canonical()

    def should_reset_utc(self, now_utc: datetime) -> bool:
        """True when the current UTC time is exactly at midnight
        (00:00:00) — the daily reset boundary. The use case calls
        this on a tick (e.g. once per minute) and triggers an
        OpenDay when it fires.

        We test for `hour == 0 and minute == 0` rather than just
        `hour == 0` so we don't fire every minute from 00:00 to
        00:59 if the scheduler granularity is coarser than 1 min.
        For a 1-minute tick this would fire once at 00:00.
        """
        if now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=timezone.utc)
        return (
            now_utc.hour == 0
            and now_utc.minute == 0
            and now_utc.second < 60
        )
