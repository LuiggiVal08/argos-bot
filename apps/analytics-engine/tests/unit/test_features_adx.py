"""Tests for features.py — ADX and BBW computation."""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.infrastructure.data.features import (
    _compute_adx,
    _compute_bb,
)


class TestAdxComputation:
    def test_adx_returns_series(self):
        np.random.seed(42)
        n = 100
        high = pd.Series(np.cumsum(np.random.randn(n)) + 100)
        low = high - np.abs(np.random.randn(n))
        close = (high + low) / 2

        adx = _compute_adx(high, low, close, period=14)
        assert isinstance(adx, pd.Series)
        assert len(adx) == n

    def test_adx_values_between_0_and_100(self):
        np.random.seed(42)
        n = 100
        high = pd.Series(np.cumsum(np.random.randn(n)) + 100)
        low = high - np.abs(np.random.randn(n))
        close = (high + low) / 2

        adx = _compute_adx(high, low, close, period=14)
        valid = adx.dropna()
        assert (valid >= 0).all()
        assert (valid <= 100).all()


class TestBbwDerivation:
    def test_bbw_from_bb(self):
        np.random.seed(42)
        close = pd.Series(np.cumsum(np.random.randn(100)) + 100)
        bb_upper, bb_middle, bb_lower = _compute_bb(close)

        bbw = (bb_upper - bb_lower) / bb_middle
        assert isinstance(bbw, pd.Series)
        assert len(bbw) == 100
        valid = bbw.dropna()
        assert (valid >= 0).all()
