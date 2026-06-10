"""Extract regime features from OHLCV + preprocessed feature array.

Bridges the gap between the existing feature pipeline (TaDataPreprocessor
with 19 features) and the RegimeDetector (needs adx, bbw, atr, ema_slope).

The extractor computes:
    - ADX(14) from raw OHLCV (high, low, close)
    - BBW from bb_upper, bb_middle, bb_lower
    - ATR from feature array
    - EMA slope from ema_fast

Calling code:
    extractor = RegimeFeatureExtractor()
    regime_features = extractor.extract(ohlcv, features_np)
    context = regime_detector.detect(regime_features)
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import ta

from ...application.ports.regime_detector import RegimeDetectionError

# Standard feature indices for TaDataPreprocessor.FEATURE_NAMES:
#   0: open, 1: high, 2: low, 3: close, 4: volume,
#   5: rsi, 6: ema_fast, 7: ema_medium, 8: ema_slow,
#   9: macd, 10: macd_signal, 11: macd_hist,
#   12: bb_upper, 13: bb_middle, 14: bb_lower,
#   15: atr, 16: obv, 17: volume_sma, 18: pct_change
_BB_UPPER_IDX = 12
_BB_MIDDLE_IDX = 13
_BB_LOWER_IDX = 14
_ATR_IDX = 15
_EMA_FAST_IDX = 6


class RegimeFeatureExtractor:
    """Extracts regime detection features from OHLCV + feature array.

    Computes ADX from raw OHLCV using the `ta` library and derives
    BBW and EMA slope from existing feature columns.
    """

    def extract(
        self,
        ohlcv: list[dict],
        features: np.ndarray,
    ) -> dict[str, float]:
        """Extract named regime features for the latest timestep.

        Args:
            ohlcv: raw OHLCV data (list of dicts with high, low, close).
            features: (n_timesteps, n_features) array from build_features().

        Returns:
            dict with keys: adx, bbw, atr, ema_slope.

        Raises RegimeDetectionError if data is insufficient.
        """
        if len(ohlcv) < 28:
            raise RegimeDetectionError(
                f"need at least 28 candles for ADX, got {len(ohlcv)}"
            )

        if features.shape[0] < 2:
            raise RegimeDetectionError(
                f"need at least 2 timesteps in features, got {features.shape[0]}"
            )

        df = pd.DataFrame(ohlcv)
        close = df["close"]

        # 1. ADX from raw OHLCV
        adx_indicator = ta.trend.ADXIndicator(
            df["high"], df["low"], close, window=14,
        )
        adx = float(adx_indicator.adx().iloc[-1])

        # 2. BBW from feature array
        bb_upper = features[-1, _BB_UPPER_IDX]
        bb_middle = features[-1, _BB_MIDDLE_IDX]
        bb_lower = features[-1, _BB_LOWER_IDX]
        bbw = float((bb_upper - bb_lower) / bb_middle) if bb_middle != 0 else 0.0

        # 3. ATR from feature array
        atr = float(features[-1, _ATR_IDX])

        # 4. EMA slope (rate of change of ema_fast)
        ema_current = features[-1, _EMA_FAST_IDX]
        ema_prev = features[-2, _EMA_FAST_IDX]
        ema_slope = float((ema_current - ema_prev) / ema_prev) if ema_prev != 0 else 0.0

        return {
            "adx": adx,
            "bbw": bbw,
            "atr": atr,
            "ema_slope": ema_slope,
        }
