"""Unit tests for H3 domain: CircuitBreaker + VOs."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.domain.entities.circuit_breaker import (
    CircuitBreaker,
    InvalidThresholdError,
)
from app.domain.value_objects.drawdown_snapshot import (
    DrawdownSnapshot,
    InvalidDrawdownSnapshotError,
)
from app.domain.value_objects.drawdown_state import DrawdownState
from app.domain.value_objects.trip_action import TripAction, TripStep


def _snap(loss_pct: Decimal, starting: Decimal = Decimal("10000")) -> DrawdownSnapshot:
    """Build a snapshot with a given drawdown percentage (0.05 = 5% loss)."""
    current = starting * (Decimal("1") - loss_pct)
    return DrawdownSnapshot(
        starting_balance=starting,
        current_balance=current,
        taken_at=datetime.now(tz=timezone.utc),
    )


# --- CircuitBreaker.evaluate ---

class TestCircuitBreakerEvaluate:
    def test_safe_below_warn(self) -> None:
        cb = CircuitBreaker(threshold=Decimal("0.05"))
        assert cb.evaluate(_snap(Decimal("0.01"))) is DrawdownState.SAFE

    def test_warn_at_warn_threshold(self) -> None:
        cb = CircuitBreaker(threshold=Decimal("0.05"))
        # 0.6 * 0.05 = 0.03
        assert cb.evaluate(_snap(Decimal("0.03"))) is DrawdownState.WARN

    def test_warn_below_trip(self) -> None:
        cb = CircuitBreaker(threshold=Decimal("0.05"))
        assert cb.evaluate(_snap(Decimal("0.04"))) is DrawdownState.WARN

    def test_trip_at_threshold(self) -> None:
        cb = CircuitBreaker(threshold=Decimal("0.05"))
        assert cb.evaluate(_snap(Decimal("0.05"))) is DrawdownState.TRIP

    def test_trip_above_threshold(self) -> None:
        cb = CircuitBreaker(threshold=Decimal("0.05"))
        assert cb.evaluate(_snap(Decimal("0.10"))) is DrawdownState.TRIP

    def test_profitable_is_safe(self) -> None:
        cb = CircuitBreaker(threshold=Decimal("0.05"))
        snap = DrawdownSnapshot(
            starting_balance=Decimal("10000"),
            current_balance=Decimal("11000"),
            taken_at=datetime.now(tz=timezone.utc),
        )
        assert cb.evaluate(snap) is DrawdownState.SAFE

    def test_halted_is_sticky(self) -> None:
        cb = CircuitBreaker(threshold=Decimal("0.05"))
        assert (
            cb.evaluate(_snap(Decimal("0.0")), current_state=DrawdownState.HALTED)
            is DrawdownState.HALTED
        )

    def test_halted_sticky_even_if_recovered(self) -> None:
        cb = CircuitBreaker(threshold=Decimal("0.05"))
        # Recovery: profitable snapshot, but we're HALTED.
        snap = DrawdownSnapshot(
            starting_balance=Decimal("10000"),
            current_balance=Decimal("12000"),
            taken_at=datetime.now(tz=timezone.utc),
        )
        assert (
            cb.evaluate(snap, current_state=DrawdownState.HALTED)
            is DrawdownState.HALTED
        )


# --- CircuitBreaker constructor ---

class TestCircuitBreakerConstructor:
    def test_default_threshold_is_5pct(self) -> None:
        cb = CircuitBreaker()
        assert cb.threshold == Decimal("0.05")
        assert cb.warn_threshold == Decimal("0.03")

    def test_threshold_zero_rejected(self) -> None:
        with pytest.raises(InvalidThresholdError):
            CircuitBreaker(threshold=Decimal("0"))

    def test_threshold_above_one_rejected(self) -> None:
        with pytest.raises(InvalidThresholdError):
            CircuitBreaker(threshold=Decimal("1.01"))

    def test_threshold_one_accepted(self) -> None:
        cb = CircuitBreaker(threshold=Decimal("1"))
        assert cb.threshold == Decimal("1")

    def test_warn_ratio_above_one_rejected(self) -> None:
        with pytest.raises(InvalidThresholdError):
            CircuitBreaker(threshold=Decimal("0.05"), warn_ratio=Decimal("1.5"))

    def test_warn_ratio_zero_rejected(self) -> None:
        with pytest.raises(InvalidThresholdError):
            CircuitBreaker(threshold=Decimal("0.05"), warn_ratio=Decimal("0"))

    def test_accepts_float(self) -> None:
        cb = CircuitBreaker(threshold=0.05)
        assert cb.threshold == Decimal("0.05")


# --- CircuitBreaker.should_reset_utc ---

class TestCircuitBreakerResetBoundary:
    def test_midnight_triggers_reset(self) -> None:
        cb = CircuitBreaker()
        assert cb.should_reset_utc(datetime(2026, 6, 7, 0, 0, 0, tzinfo=timezone.utc))

    def test_00_30_does_not_trigger(self) -> None:
        cb = CircuitBreaker()
        assert not cb.should_reset_utc(
            datetime(2026, 6, 7, 0, 30, 0, tzinfo=timezone.utc)
        )

    def test_01_00_does_not_trigger(self) -> None:
        cb = CircuitBreaker()
        assert not cb.should_reset_utc(
            datetime(2026, 6, 7, 1, 0, 0, tzinfo=timezone.utc)
        )

    def test_naive_datetime_treated_as_utc(self) -> None:
        cb = CircuitBreaker()
        assert cb.should_reset_utc(datetime(2026, 6, 7, 0, 0, 0))


# --- CircuitBreaker.trip_action ---

class TestTripAction:
    def test_canonical_order(self) -> None:
        a = TripAction.canonical()
        assert a.steps == (
            TripStep.CANCEL_ORDERS,
            TripStep.CLOSE_POSITIONS,
            TripStep.SET_PASIVO,
            TripStep.HALT,
        )

    def test_circuit_breaker_returns_canonical(self) -> None:
        cb = CircuitBreaker()
        assert cb.trip_action() == TripAction.canonical()

    def test_empty_steps_rejected(self) -> None:
        with pytest.raises(ValueError):
            TripAction(steps=())

    def test_step_out_of_order_rejected(self) -> None:
        with pytest.raises(ValueError):
            TripAction(
                steps=(
                    TripStep.CLOSE_POSITIONS,
                    TripStep.CANCEL_ORDERS,
                    TripStep.SET_PASIVO,
                    TripStep.HALT,
                )
            )

    def test_step_omitted_rejected(self) -> None:
        with pytest.raises(ValueError):
            TripAction(steps=(TripStep.CANCEL_ORDERS, TripStep.HALT))


# --- DrawdownSnapshot ---

class TestDrawdownSnapshot:
    def test_drawdown_pct_loss(self) -> None:
        snap = DrawdownSnapshot(
            starting_balance=Decimal("10000"),
            current_balance=Decimal("9500"),
            taken_at=datetime.now(tz=timezone.utc),
        )
        assert snap.drawdown_pct == Decimal("0.05")

    def test_drawdown_pct_profit_is_zero(self) -> None:
        snap = DrawdownSnapshot(
            starting_balance=Decimal("10000"),
            current_balance=Decimal("11000"),
            taken_at=datetime.now(tz=timezone.utc),
        )
        assert snap.drawdown_pct == Decimal("0")

    def test_is_profitable(self) -> None:
        profit = DrawdownSnapshot(
            starting_balance=Decimal("10000"),
            current_balance=Decimal("11000"),
            taken_at=datetime.now(tz=timezone.utc),
        )
        loss = DrawdownSnapshot(
            starting_balance=Decimal("10000"),
            current_balance=Decimal("9000"),
            taken_at=datetime.now(tz=timezone.utc),
        )
        flat = DrawdownSnapshot(
            starting_balance=Decimal("10000"),
            current_balance=Decimal("10000"),
            taken_at=datetime.now(tz=timezone.utc),
        )
        assert profit.is_profitable
        assert not loss.is_profitable
        assert not flat.is_profitable

    def test_at_open_factory(self) -> None:
        snap = DrawdownSnapshot.at_open(Decimal("10000"))
        assert snap.starting_balance == snap.current_balance == Decimal("10000")
        assert snap.drawdown_pct == Decimal("0")

    def test_zero_starting_rejected(self) -> None:
        with pytest.raises(InvalidDrawdownSnapshotError):
            DrawdownSnapshot(
                starting_balance=Decimal("0"),
                current_balance=Decimal("0"),
                taken_at=datetime.now(tz=timezone.utc),
            )

    def test_negative_current_rejected(self) -> None:
        with pytest.raises(InvalidDrawdownSnapshotError):
            DrawdownSnapshot(
                starting_balance=Decimal("10000"),
                current_balance=Decimal("-1"),
                taken_at=datetime.now(tz=timezone.utc),
            )
