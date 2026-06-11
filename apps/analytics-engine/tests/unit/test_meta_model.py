"""Tests for MetaModel (H26) stacking ensemble."""
from __future__ import annotations

import numpy as np
import pytest

from app.application.ports.meta_model import MetaModelInput


class TestMetaModelInput:
    def test_to_vector_shape(self):
        inp = MetaModelInput(
            lstm_probs=np.array([0.7, 0.1, 0.2]),
            xgb_probs=np.array([0.6, 0.2, 0.2]),
            context={"adx": 30.0, "bbw": 0.5, "atr": 100.0, "rsi": 65.0, "volume": 500.0},
        )
        vec = inp.to_vector()
        # 3 + 3 + 5 = 11
        assert vec.shape == (11,)
        assert vec[0] == 0.7  # lstm buy
        assert vec[3] == 0.6  # xgb buy
        assert vec[6] == 30.0  # adx

    def test_to_vector_defaults(self):
        inp = MetaModelInput(
            lstm_probs=np.array([0.4, 0.3, 0.3]),
            xgb_probs=np.array([0.4, 0.3, 0.3]),
            context={"adx": 25.0},
        )
        vec = inp.to_vector()
        # 3 + 3 + 5 = 11, missing context keys -> 0
        assert vec.shape == (11,)
        assert vec[7] == 0.0  # bbw defaults to 0

    def test_n_features(self):
        inp = MetaModelInput(
            lstm_probs=np.array([0.5, 0.3, 0.2]),
            xgb_probs=np.array([0.5, 0.3, 0.2]),
            context={"adx": 20.0, "bbw": 0.3, "atr": 50.0, "rsi": 55.0, "volume": 1000.0},
        )
        assert inp.n_features == 11
