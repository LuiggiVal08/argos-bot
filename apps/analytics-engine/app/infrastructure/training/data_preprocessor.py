"""Feature engineering pipeline for NovaQuant.

Convierte OHLCV crudo en ventanas normalizadas con features
tecnicas listas para la red LSTM.

Pipeline completo:
  1. build_features:  calcula 15 features (RSI, MACD, BB, ATR, etc.)
  2. normalize:       z-score con medias/std dadas o calculadas
  3. create_windows:  sliding window de tamano lookback
  4. create_targets:  etiquetas BUY/SELL/HOLD segun return forward

Stack: pandas, numpy, ta (Technical Analysis Library).
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import ta

from ...application.ports.data_preprocessor import (
    DataPreprocessor,
    InsufficientDataError,
    PreprocessingError,
)
from ...domain.value_objects.model_config import ModelConfig


class TaDataPreprocessor:
    """Preprocesador de OHLCV usando pandas + ta + numpy.

    Implementa el port DataPreprocessor.
    """

    # Features esperadas en orden (coincide con ModelConfig.features default)
    FEATURE_NAMES: tuple[str, ...] = (
        "return_1",
        "return_5",
        "rsi_14",
        "rsi_21",
        "macd_line",
        "macd_signal",
        "macd_histogram",
        "bb_position",
        "bb_width",
        "atr_14",
        "volume_sma_20",
        "volume_ratio",
        "stoch_k",
        "stoch_d",
        "obv",
    )

    async def build_features(
        self,
        ohlcv: list[dict],
        config: ModelConfig,
    ) -> np.ndarray:
        """Calcula todas las features desde OHLCV.

        Args:
            ohlcv: lista de dicts con keys timestamp, open, high, low, close, volume.
            config: config del modelo (features list, etc.).

        Returns:
            Array (n_velas, n_features).
        """
        try:
            df = pd.DataFrame(ohlcv)
            df = _ensure_numeric(df)

            features = []

            # Retornos
            close = df["close"]
            features.append(close.pct_change(1))     # return_1
            features.append(close.pct_change(5))     # return_5

            # RSI
            features.append(ta.momentum.RSIIndicator(close, window=14).rsi())
            features.append(ta.momentum.RSIIndicator(close, window=21).rsi())

            # MACD
            macd = ta.trend.MACD(close)
            features.append(macd.macd())              # macd_line
            features.append(macd.macd_signal())       # macd_signal
            features.append(macd.macd_diff())         # macd_histogram

            # Bollinger Bands
            bb = ta.volatility.BollingerBands(close, window=20, window_dev=2)
            bb_pct = (close - bb.bollinger_mavg()) / (bb.bollinger_hband() - bb.bollinger_lband())
            bb_width = (bb.bollinger_hband() - bb.bollinger_lband()) / close
            features.append(bb_pct)                  # bb_position
            features.append(bb_width)                # bb_width

            # ATR
            atr = ta.volatility.AverageTrueRange(
                df["high"], df["low"], close, window=14
            ).average_true_range()
            features.append(atr)

            # Volumen
            volume = df["volume"]
            vol_sma = volume.rolling(20).mean()
            features.append(vol_sma)                 # volume_sma_20
            vol_ratio = volume / vol_sma.replace(0, np.nan)
            features.append(vol_ratio)               # volume_ratio

            # Stochastic
            stoch = ta.momentum.StochasticOscillator(
                df["high"], df["low"], close, window=14, smooth_window=3
            )
            features.append(stoch.stoch())           # stoch_k
            features.append(stoch.stoch_signal())    # stoch_d

            # OBV
            obv = ta.volume.OnBalanceVolumeIndicator(close, volume).on_balance_volume()
            features.append(obv)

            # Combinar
            result = pd.concat(features, axis=1)
            result.columns = self.FEATURE_NAMES[: len(features)]

            # Rellenar NaN (primeros valores donde los indicadores no tienen historia)
            result = result.bfill().ffill()

            return result.values.astype(np.float64)

        except Exception as e:
            raise PreprocessingError(f"build_features failed: {e}") from e

    async def normalize(
        self,
        features: np.ndarray,
        means: tuple[float, ...] | None = None,
        stds: tuple[float, ...] | None = None,
    ) -> tuple[np.ndarray, tuple[float, ...], tuple[float, ...]]:
        """Normaliza features con z-score.

        Si means/stds son None, los calcula del array.
        Retorna (normalized, means, stds).
        """
        if means is None or stds is None:
            means = tuple(float(v) for v in features.mean(axis=0))
            stds = tuple(float(v) for v in features.std(axis=0).clip(min=1e-10))

        means_arr = np.array(means, dtype=np.float64)
        stds_arr = np.array(stds, dtype=np.float64)

        normalized = (features - means_arr) / stds_arr
        return normalized, means, stds

    async def create_windows(
        self,
        features: np.ndarray,
        lookback: int,
    ) -> np.ndarray:
        """Crea ventanas deslizantes.

        Returns:
            Array (n_ventanas, lookback, n_features).

        Raises InsufficientDataError si features es muy corto.
        """
        n = len(features)
        if n < lookback + 1:
            raise InsufficientDataError(
                f"need at least {lookback + 1} rows, got {n}"
            )

        windows = np.lib.stride_tricks.sliding_window_view(
            features, window_shape=lookback, axis=0
        )
        # sliding_window_view da (n - lookback + 1, lookback, n_features)
        # pero transpuesto: queremos (n_muestras, lookback, n_features)
        return windows.transpose(0, 2, 1)

    async def create_targets(
        self,
        ohlcv: list[dict],
        config: ModelConfig,
    ) -> np.ndarray:
        """Genera targets one-hot: BUY=[1,0,0], SELL=[0,1,0], HOLD=[0,0,1].

        Usa config.target_lookahead y config.target_return_pct.
        Retorna array (n_muestras, 3).
        """
        try:
            df = pd.DataFrame(ohlcv)
            df = _ensure_numeric(df)
            close = df["close"].values

            n = len(close)
            lookahead = config.target_lookahead
            threshold = config.target_return_pct / 100.0

            targets = np.zeros((n, 3), dtype=np.float64)

            for i in range(n - lookahead):
                ret = (close[i + lookahead] - close[i]) / close[i]
                if ret > threshold:
                    targets[i] = [1.0, 0.0, 0.0]   # BUY
                elif ret < -threshold:
                    targets[i] = [0.0, 1.0, 0.0]  # SELL
                else:
                    targets[i] = [0.0, 0.0, 1.0]  # HOLD

            # Ultimos lookahead elementos no tienen target -> HOLD
            targets[-lookahead:] = [0.0, 0.0, 1.0]

            return targets

        except Exception as e:
            raise PreprocessingError(f"create_targets failed: {e}") from e


def _ensure_numeric(df: pd.DataFrame) -> pd.DataFrame:
    """Convierte columnas numericas a float64, maneja nulos."""
    numeric_cols = ["open", "high", "low", "close", "volume"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    return df
