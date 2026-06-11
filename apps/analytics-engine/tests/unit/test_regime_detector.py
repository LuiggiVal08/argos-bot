"""Tests for Regime Detector (H23)."""
from __future__ import annotations

import numpy as np
import pytest

from app.domain.entities.market_context import MarketContext
from app.domain.value_objects.market_regime import RegimeType
from app.infrastructure.analysis.regime_detector import (
    RuleBasedRegimeDetector,
)


class TestRegimeType:
    def test_enum_values(self):
        assert RegimeType.TRENDING.value == "TRENDING"
        assert RegimeType.RANGING.value == "RANGING"
        assert RegimeType.HIGH_VOLATILITY.value == "HIGH_VOLATILITY"
        assert RegimeType.LOW_VOLATILITY.value == "LOW_VOLATILITY"
        assert RegimeType.UNKNOWN.value == "UNKNOWN"

    def test_str(self):
        assert str(RegimeType.TRENDING) == "TRENDING"


class TestMarketContext:
    def test_create(self):
        ctx = MarketContext(
            regime=RegimeType.TRENDING,
            adx=30.0,
            bbw=0.5,
            atr=100.0,
            ema_slope=0.01,
        )
        assert ctx.regime == RegimeType.TRENDING
        assert ctx.is_actionable()

    def test_unknown_not_actionable(self):
        ctx = MarketContext(
            regime=RegimeType.UNKNOWN,
            adx=0.0,
            bbw=0.0,
            atr=0.0,
            ema_slope=0.0,
        )
        assert not ctx.is_actionable()

    def test_features_dict(self):
        ctx = MarketContext(
            regime=RegimeType.RANGING,
            adx=15.0,
            bbw=0.3,
            atr=50.0,
            ema_slope=-0.005,
        )
        feats = ctx.features
        assert feats["adx"] == 15.0
        assert feats["bbw"] == 0.3
        assert feats["atr"] == 50.0
        assert feats["ema_slope"] == -0.005


class TestRuleBasedRegimeDetector:
    @pytest.fixture
    def detector(self):
        return RuleBasedRegimeDetector()

    def test_trending_high_adx(self, detector):
        result = detector.detect({
            "adx": 35.0,
            "bbw": 0.4,
            "atr": 100.0,
            "ema_slope": 0.02,
        })
        assert result.regime == RegimeType.TRENDING
        assert result.is_actionable()

    def test_ranging_low_adx(self, detector):
        result = detector.detect({
            "adx": 15.0,
            "bbw": 0.2,
            "atr": 50.0,
            "ema_slope": 0.003,
        })
        assert result.regime == RegimeType.RANGING

    def test_low_volatility(self, detector):
        """Warm up with neutral values first, then detect low vol."""
        for _ in range(20):
            detector.detect({
                "adx": 20.0,
                "bbw": 0.3,
                "atr": 100.0,
                "ema_slope": 0.0,
            })
        result = detector.detect({
            "adx": 12.0,
            "bbw": 0.04,
            "atr": 8.0,
            "ema_slope": 0.001,
        })
        assert result.regime == RegimeType.LOW_VOLATILITY

    def test_high_volatility_no_trend(self, detector):
        """BBW high + ADX low = HIGH_VOLATILITY, with warmup."""
        for _ in range(20):
            detector.detect({
                "adx": 15.0,
                "bbw": 0.3,
                "atr": 100.0,
                "ema_slope": 0.0,
            })
        result = detector.detect({
            "adx": 15.0,
            "bbw": 0.9,
            "atr": 350.0,
            "ema_slope": -0.01,
        })
        assert result.regime == RegimeType.HIGH_VOLATILITY

    def test_unknown_on_nan(self, detector):
        result = detector.detect({
            "adx": float("nan"),
            "bbw": 0.3,
            "atr": 50.0,
            "ema_slope": 0.01,
        })
        assert result.regime == RegimeType.UNKNOWN

    def test_unknown_on_missing_keys(self, detector):
        from app.application.ports.regime_detector import (
            RegimeDetectionError,
        )
        with pytest.raises(RegimeDetectionError, match="missing"):
            detector.detect({"adx": 20.0, "bbw": 0.3, "atr": 50.0})

    def test_unknown_on_negative(self, detector):
        result = detector.detect({
            "adx": -1.0,
            "bbw": 0.3,
            "atr": 50.0,
            "ema_slope": 0.01,
        })
        assert result.regime == RegimeType.UNKNOWN

    def test_trending_high_vol(self, detector):
        """Trending + high ATR/BBW should still classify as TRENDING
        (direction dominates volatility overlay)."""
        for _ in range(20):
            detector.detect({
                "adx": 30.0,
                "bbw": 0.3,
                "atr": 100.0,
                "ema_slope": 0.02,
            })
        result = detector.detect({
            "adx": 35.0,
            "bbw": 0.9,
            "atr": 250.0,
            "ema_slope": 0.05,
        })
        assert result.regime == RegimeType.TRENDING

    def test_reset_history(self, detector):
        for i in range(50):
            detector.detect({
                "adx": 20.0 + i * 0.5,
                "bbw": 0.3,
                "atr": 50.0,
                "ema_slope": 0.001,
            })
        assert len(detector._bbw_history) > 0
        assert len(detector._atr_history) > 0
        detector.reset()
        assert len(detector._bbw_history) == 0
        assert len(detector._atr_history) == 0
