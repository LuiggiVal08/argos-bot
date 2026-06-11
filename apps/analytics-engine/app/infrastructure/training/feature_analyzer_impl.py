"""Feature analyzer: correlacion features vs target para seleccion.

Usa numpy para calcular correlacion de Pearson entre cada feature
y el target (clase BUY). Features con |correlacion| < threshold
se descartan automaticamente.

Stack: numpy.
"""
from __future__ import annotations

import numpy as np

from ...application.ports.feature_analyzer import (
    AnalysisError,
    FeatureAnalyzer,
)


class CorrelationFeatureAnalyzer:
    """Implementacion de FeatureAnalyzer basada en correlacion de Pearson.

    Analiza la correlacion lineal entre cada feature y el target BUY
    (columna 0 del one-hot). Features con baja correlacion se descartan
    porque anaden ruido sin poder predictivo.
    """

    async def compute_correlations(
        self,
        features: np.ndarray,
        targets: np.ndarray,
        feature_names: tuple[str, ...],
    ) -> dict[str, float]:
        """Calcula correlacion de Pearson de cada feature vs target BUY.

        Args:
            features: (n_muestras, n_features).
            targets: (n_muestras, 3) one-hot.
            feature_names: nombre de cada feature.

        Returns:
            Dict {nombre_feature: correlacion}.
        """
        try:
            if features.shape[0] != targets.shape[0]:
                raise AnalysisError(
                    f"features rows ({features.shape[0]}) != "
                    f"targets rows ({targets.shape[0]})"
                )
            if len(feature_names) != features.shape[1]:
                raise AnalysisError(
                    f"{len(feature_names)} feature names but "
                    f"{features.shape[1]} feature columns"
                )

            n_features = features.shape[1]
            target_buy = targets[:, 0]  # clase BUY

            correlations: dict[str, float] = {}
            for i in range(n_features):
                corr = _pearson(features[:, i], target_buy)
                correlations[feature_names[i]] = round(float(corr), 4)

            return correlations

        except Exception as e:
            if isinstance(e, AnalysisError):
                raise
            raise AnalysisError(f"compute_correlations failed: {e}") from e

    async def filter_features(
        self,
        features: np.ndarray,
        targets: np.ndarray,
        feature_names: tuple[str, ...],
        min_correlation: float = 0.05,
    ) -> tuple[np.ndarray, tuple[str, ...]]:
        """Descarta features con |corr| < min_correlation.

        Returns:
            (features_filtradas, nombres_features_filtrados).
        """
        try:
            corrs = await self.compute_correlations(
                features, targets, feature_names
            )

            keep_indices = [
                i
                for i, name in enumerate(feature_names)
                if abs(corrs.get(name, 0)) >= min_correlation
            ]

            if not keep_indices:
                # Si todas se descartan, mantener las mejores 3
                sorted_names = sorted(corrs, key=lambda n: abs(corrs[n]), reverse=True)
                keep_names = sorted_names[:3]
                keep_indices = [feature_names.index(n) for n in keep_names]
            else:
                keep_names = tuple(feature_names[i] for i in keep_indices)

            filtered = features[:, keep_indices]
            return filtered, tuple(keep_names)

        except Exception as e:
            if isinstance(e, AnalysisError):
                raise
            raise AnalysisError(f"filter_features failed: {e}") from e


def _pearson(x: np.ndarray, y: np.ndarray) -> float:
    """Pearson correlation coefficient manual (evita dependencia scipy)."""
    x_mean = x.mean()
    y_mean = y.mean()
    x_std = x.std(ddof=0)
    y_std = y.std(ddof=0)
    if x_std == 0 or y_std == 0:
        return 0.0
    cov = ((x - x_mean) * (y - y_mean)).mean()
    return cov / (x_std * y_std)
