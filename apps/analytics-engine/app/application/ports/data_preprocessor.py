"""DataPreprocessor port.

Transforma velas OHLCV crudas en ventanas normalizadas listas para
entrenar o predecir con la red LSTM.

Pipeline:
  1. Calcular features (RSI, MACD, BB, ATR, returns, etc.)
  2. Normalizar (z-score) con medias/std dadas o calcularlas
  3. Ventanear (sliding window de tamano lookback)
  4. Generar targets (BUY/SELL/HOLD segun return forward)

Sad paths:
  - InsufficientDataError: no hay suficientes velas para el lookback
  - PreprocessingError: fallo en calculo de features
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np

from ...domain.value_objects.model_config import ModelConfig


class InsufficientDataError(RuntimeError):
    """Raised when not enough candles for the lookback window."""


class PreprocessingError(RuntimeError):
    """Raised when feature computation fails."""


@runtime_checkable
class DataPreprocessor(Protocol):
    """Preprocesa OHLCV para entrenamiento o inferencia."""

    async def build_features(
        self,
        ohlcv: list[dict],
        config: ModelConfig,
    ) -> np.ndarray:
        """Calcula todas las features desde OHLCV.

        Retorna array (n_velas, n_features) con valores crudos
        (sin normalizar ni ventanear).

        Raises PreprocessingError si falla el calculo.
        """
        ...

    async def normalize(
        self,
        features: np.ndarray,
        means: tuple[float, ...] | None = None,
        stds: tuple[float, ...] | None = None,
    ) -> tuple[np.ndarray, tuple[float, ...], tuple[float, ...]]:
        """Normaliza features con z-score.

        Si means/stds son None, los calcula del array.
        Retorna (normalized, means, stds) para persistir.
        """
        ...

    async def create_windows(
        self,
        features: np.ndarray,
        lookback: int,
    ) -> np.ndarray:
        """Crea ventanas deslizantes de tamano lookback.

        Retorna array (n_ventanas, lookback, n_features).
        Raises InsufficientDataError si features es muy corto.
        """
        ...

    async def create_targets(
        self,
        ohlcv: list[dict],
        config: ModelConfig,
    ) -> np.ndarray:
        """Genera targets one-hot: BUY=[1,0,0], SELL=[0,1,0], HOLD=[0,0,1].

        Usa config.target_lookahead y config.target_return_pct.
        Retorna array (n_muestras, 3).
        """
        ...
