"""Tests para SignalValidator entity."""
from datetime import datetime, timedelta, timezone

import pytest

from app.domain.entities.signal_validator import (
    SignalValidator, ValidationResult, RejectionReason,
)
from app.domain.value_objects.execution_signal import ExecutionSignal
from app.domain.value_objects.signal_side import SignalSide


class TestSignalValidator:
    def test_accepts_valid_signal(self):
        sv = SignalValidator(min_confidence=0.7, cooldown_seconds=0)
        sig = ExecutionSignal(
            side=SignalSide.BUY, confidence=0.85, symbol="BTC/USDT",
        )
        result = sv.validate(sig)
        assert result.valid

    def test_rejects_low_confidence(self):
        sv = SignalValidator(min_confidence=0.7, cooldown_seconds=0)
        sig = ExecutionSignal(
            side=SignalSide.BUY, confidence=0.5, symbol="BTC/USDT",
        )
        result = sv.validate(sig)
        assert not result.valid
        assert result.reason == RejectionReason.CONFIDENCE_TOO_LOW

    def test_rejects_duplicate(self):
        sv = SignalValidator(min_confidence=0.0, cooldown_seconds=0)
        sig = ExecutionSignal(
            side=SignalSide.BUY, confidence=0.5, symbol="BTC/USDT",
        )
        assert sv.validate(sig).valid
        result = sv.validate(sig)
        assert not result.valid
        assert result.reason == RejectionReason.DUPLICATE_SIGNAL_ID

    def test_rejects_expired(self):
        sv = SignalValidator(min_confidence=0.0, max_age_seconds=10)
        old = datetime.now(timezone.utc) - timedelta(seconds=30)
        sig = ExecutionSignal(
            side=SignalSide.BUY, confidence=0.5, symbol="BTC/USDT",
            timestamp=old,
        )
        result = sv.validate(sig)
        assert not result.valid
        assert result.reason == RejectionReason.SIGNAL_EXPIRED

    def test_respects_cooldown(self):
        sv = SignalValidator(min_confidence=0.0, cooldown_seconds=60)
        s1 = ExecutionSignal(
            side=SignalSide.BUY, confidence=0.5, symbol="BTC/USDT",
        )
        s2 = ExecutionSignal(
            side=SignalSide.SELL, confidence=0.5, symbol="BTC/USDT",
        )
        assert sv.validate(s1).valid
        result = sv.validate(s2)
        assert not result.valid
        assert result.reason == RejectionReason.COOLDOWN_ACTIVE

    def test_allows_different_symbols_during_cooldown(self):
        sv = SignalValidator(min_confidence=0.0, cooldown_seconds=60)
        s1 = ExecutionSignal(
            side=SignalSide.BUY, confidence=0.5, symbol="BTC/USDT",
        )
        s2 = ExecutionSignal(
            side=SignalSide.SELL, confidence=0.5, symbol="ETH/USDT",
        )
        assert sv.validate(s1).valid
        assert sv.validate(s2).valid  # different symbol, no cooldown

    def test_rejects_invalid_constructor_args(self):
        with pytest.raises(ValueError, match="min_confidence must be in"):
            SignalValidator(min_confidence=-0.1)
        with pytest.raises(ValueError, match="cooldown_seconds must be"):
            SignalValidator(cooldown_seconds=-1)
        with pytest.raises(ValueError, match="max_age_seconds must be"):
            SignalValidator(max_age_seconds=-1)

    def test_validation_result_ok(self):
        r = ValidationResult.ok()
        assert r.valid

    def test_validation_result_rejected(self):
        r = ValidationResult.rejected(RejectionReason.CONFIDENCE_TOO_LOW, "test")
        assert not r.valid
        assert r.reason == RejectionReason.CONFIDENCE_TOO_LOW
        assert r.message == "test"
