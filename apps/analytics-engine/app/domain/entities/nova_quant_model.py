"""Domain entity: NovaQuantModel — red neuronal versionada.

Representa un modelo entrenado de NovaQuant en la capa de dominio.
Contiene la configuracion (ModelConfig), metadatos de entrenamiento,
parametros de normalizacion (z-score: medias y stds por feature),
y un resumen de metricas (val_loss, sharpe, etc.).

La entidad NO ejecuta el forward pass (eso es responsabilidad de la
infraestructura con Keras). En cambio, provee validacion de dominio:
- Coincidencia de features (que el input tenga las columnas esperadas)
- Control de versiones (que los pesos correspondan a la config)
- Chequeo de staleness (que el modelo no tenga mas de N dias)

INVARIANTE: si cambia ModelConfig, se invalida el modelo existente
(los pesos no son compatibles con otra configuracion).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..value_objects.model_config import ModelConfig

# Maximo tiempo sin reentrenar antes de considerar el modelo stale
MAX_MODEL_AGE_DAYS: int = 7


class ModelVersionMismatchError(ValueError):
    """El version del modelo no coincide con lo esperado."""


class FeatureMismatchError(ValueError):
    """El numero de features del input no coincide con la config."""


class StaleModelError(ValueError):
    """El modelo supero MAX_MODEL_AGE_DAYS sin reentrenar."""


class NovaQuantModel:
    """Entidad de dominio: modelo neuronal versionado.

    Args:
        config:         Configuracion del modelo (lookback, layers, features...).
        model_version:  Version semantica del modelo (ej: '1.0.0').
        trained_at:     Timestamp UTC de cuando se entreno.
        weights_hash:   SHA256 de los pesos serializados (para integridad).
        feature_means:  Media de cada feature calculada en entrenamiento.
        feature_stds:   Desviacion estandar de cada feature (z-score).
        metrics:        Dict con metricas de validacion (val_loss, val_accuracy, sharpe).
    """

    def __init__(
        self,
        config: ModelConfig,
        model_version: str,
        trained_at: datetime,
        weights_hash: str,
        feature_means: tuple[float, ...],
        feature_stds: tuple[float, ...],
        metrics: dict[str, Any] | None = None,
    ) -> None:
        if len(feature_means) != len(config.features):
            raise FeatureMismatchError(
                f"feature_means ({len(feature_means)}) must match "
                f"config.features ({len(config.features)})"
            )
        if len(feature_stds) != len(config.features):
            raise FeatureMismatchError(
                f"feature_stds ({len(feature_stds)}) must match "
                f"config.features ({len(config.features)})"
            )
        if any(s <= 0 for s in feature_stds):
            raise FeatureMismatchError(
                "feature_stds must be positive (got a zero or negative std)"
            )
        if not weights_hash:
            raise ValueError("weights_hash cannot be empty")
        if not model_version:
            raise ValueError("model_version cannot be empty")

        self._config = config
        self._model_version = model_version
        self._trained_at = trained_at
        self._weights_hash = weights_hash
        self._feature_means = feature_means
        self._feature_stds = feature_stds
        self._metrics = metrics or {}

    # ── Propiedades publicas ──────────────────────────────────────

    @property
    def config(self) -> ModelConfig:
        return self._config

    @property
    def model_version(self) -> str:
        return self._model_version

    @property
    def trained_at(self) -> datetime:
        return self._trained_at

    @property
    def weights_hash(self) -> str:
        return self._weights_hash

    @property
    def feature_means(self) -> tuple[float, ...]:
        return self._feature_means

    @property
    def feature_stds(self) -> tuple[float, ...]:
        return self._feature_stds

    @property
    def metrics(self) -> dict[str, Any]:
        return dict(self._metrics)  # copia defensiva

    @property
    def age_days(self) -> float:
        """Dias desde el entrenamiento hasta ahora."""
        delta = datetime.now(timezone.utc) - self._trained_at
        return delta.total_seconds() / 86400.0

    @property
    def is_stale(self) -> bool:
        """True si el modelo supero MAX_MODEL_AGE_DAYS sin reentrenar."""
        return self.age_days > MAX_MODEL_AGE_DAYS

    # ── Metodos de dominio ────────────────────────────────────────

    def validate_input(self, n_features: int) -> None:
        """Lanza FeatureMismatchError si n_features no coincide con la config.

        Se llama desde el preprocesador ANTES de normalizar, para
        detectar errores de feature engineering temprano.
        """
        expected = len(self._config.features)
        if n_features != expected:
            raise FeatureMismatchError(
                f"input has {n_features} features, "
                f"model expects {expected} "
                f"(check config.features list)"
            )

    def assert_not_stale(self) -> None:
        """Lanza StaleModelError si el modelo esta vencido.

        Se llama antes de predecir en produccion. Si el modelo esta
        stale, el use case debe decidir si reentrenar o abortar.
        """
        if self.is_stale:
            raise StaleModelError(
                f"model {self._model_version} was trained "
                f"{self.age_days:.1f} days ago (max {MAX_MODEL_AGE_DAYS})"
            )

    def assert_version(self, expected_version: str) -> None:
        """Lanza ModelVersionMismatchError si la version no coincide.

        Util para verificar que el checkpoint cargado corresponde
        al modelo que esperamos en memoria.
        """
        if self._model_version != expected_version:
            raise ModelVersionMismatchError(
                f"expected version {expected_version}, "
                f"got {self._model_version}"
            )

    def __repr__(self) -> str:
        return (
            f"NovaQuantModel(version={self._model_version}, "
            f"features={len(self._config.features)}, "
            f"lookback={self._config.lookback}, "
            f"trained={self._trained_at.date()})"
        )
