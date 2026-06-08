"""FeatureAnalyzer port.

Analiza la correlacion de cada feature con el target para
seleccionar automaticamente las features mas relevantes.

El adapter concreto usa pandas/scipy para calcular:
  - Matriz de correlacion feature vs target
  - Features con |corr| < threshold se descartan
  - Ranking de features por importancia

Sad paths:
  - AnalysisError: datos insuficientes o fallo en el calculo
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np


class AnalysisError(RuntimeError):
    """Raised when feature analysis fails."""


@runtime_checkable
class FeatureAnalyzer(Protocol):
    """Analiza correlacion features -> target para seleccion."""

    async def compute_correlations(
        self,
        features: np.ndarray,
        targets: np.ndarray,
        feature_names: tuple[str, ...],
    ) -> dict[str, float]:
        """Calcula correlacion de cada feature con el target.

        Para targets one-hot, correlaciona con la clase BUY (columna 0).
        Retorna dict {nombre_feature: correlacion}.

        Raises AnalysisError si falla.
        """
        ...

    async def filter_features(
        self,
        features: np.ndarray,
        targets: np.ndarray,
        feature_names: tuple[str, ...],
        min_correlation: float = 0.05,
    ) -> tuple[np.ndarray, tuple[str, ...]]:
        """Descartes features con |corr| < min_correlation.

        Returns:
            (features_filtradas, nombres_features_filtrados).

        Raises AnalysisError si falla.
        """
        ...
