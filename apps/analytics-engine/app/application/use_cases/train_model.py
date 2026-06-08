"""TrainModelUseCase.

Orquesta el pipeline completo de entrenamiento de NovaQuant:

  1. Obtener OHLCV historico (OhlcvSource)
  2. Calcular features (DataPreprocessor)
  3. Analizar correlacion y filtrar features ruidosas (FeatureAnalyzer)
  4. Normalizar + ventanear (DataPreprocessor)
  5. Generar targets (DataPreprocessor)
  6. Dividir train/val/test
  7. Entrenar red LSTM (ModelTrainer)
  8. Persistir checkpoint (CheckpointRepository)
  9. Retornar metricas + modelo

Sad paths:
  - OhlcvSourceError: datos insuficientes, exchange caido
  - InsufficientDataError: pocas velas para el lookback
  - AnalysisError: fallo en correlacion
  - TrainingError: fallo en entrenamiento
  - CheckpointIOError: no se pudo guardar el modelo
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

from ...domain.entities.nova_quant_model import (
    FeatureMismatchError,
    NovaQuantModel,
)
from ...domain.value_objects.model_config import ModelConfig
from ..ports.checkpoint_repository import (
    CheckpointIOError,
    CheckpointRepository,
)
from ..ports.data_preprocessor import (
    DataPreprocessor,
    InsufficientDataError,
    PreprocessingError,
)
from ..ports.feature_analyzer import AnalysisError, FeatureAnalyzer
from ..ports.model_trainer import ModelTrainer, TrainingError
from ..ports.ohlcv_source import OhlcvSource, OhlcvSourceError


class TrainModelError(RuntimeError):
    """Raised when the training pipeline fails at any step."""


@dataclass(frozen=True)
class TrainModelResult:
    model: NovaQuantModel
    metrics: dict
    features_used: tuple[str, ...]
    correlations: dict[str, float]
    train_samples: int
    val_samples: int
    test_samples: int
    trained_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class TrainModelUseCase:
    """Orquesta el entrenamiento completo de NovaQuant.

    Uso:
        use_case = TrainModelUseCase(ohlcv_source, preprocessor, analyzer, trainer, repo)
        result = await use_case.execute(symbol="BTC/USDT", config=ModelConfig())
    """

    def __init__(
        self,
        ohlcv_source: OhlcvSource,
        preprocessor: DataPreprocessor,
        analyzer: FeatureAnalyzer,
        trainer: ModelTrainer,
        repo: CheckpointRepository,
    ) -> None:
        self._ohlcv = ohlcv_source
        self._preprocessor = preprocessor
        self._analyzer = analyzer
        self._trainer = trainer
        self._repo = repo

    async def execute(
        self,
        symbol: str,
        config: ModelConfig | None = None,
        timeframe: str = "1h",
        limit: int = 5000,
        val_split: float = 0.1,
        test_split: float = 0.1,
    ) -> TrainModelResult:
        """Ejecuta el pipeline completo de entrenamiento.

        Args:
            symbol: par ejemplo BTC/USDT.
            config: config del modelo. Usa default si None.
            timeframe: temporalidad de las velas.
            limit: max velas a descargar.
            val_split: fraccion para validacion.
            test_split: fraccion para test.

        Returns:
            TrainModelResult con modelo entrenado + metricas.

        Raises TrainModelError si algun paso falla.
        """
        cfg = config or ModelConfig()

        # 1. Obtener OHLCV
        try:
            ohlcv = await self._ohlcv.fetch_ohlcv(
                symbol=symbol,
                timeframe=timeframe,
                limit=limit,
            )
        except OhlcvSourceError as e:
            raise TrainModelError(f"ohlcv_fetch_failed: {e}") from e

        if len(ohlcv) < cfg.lookback + cfg.target_lookahead + 10:
            raise TrainModelError(
                f"insufficient_data: got {len(ohlcv)} candles, "
                f"need at least {cfg.lookback + cfg.target_lookahead + 10}"
            )

        # 2. Calcular features crudas
        try:
            features_raw = await self._preprocessor.build_features(ohlcv, cfg)
        except PreprocessingError as e:
            raise TrainModelError(f"feature_build_failed: {e}") from e

        # 3. Generar targets
        try:
            targets = await self._preprocessor.create_targets(ohlcv, cfg)
        except PreprocessingError as e:
            raise TrainModelError(f"target_gen_failed: {e}") from e

        # 4. Alinear features y targets (primeros target_lookahead se pierden)
        min_len = min(len(features_raw), len(targets))
        features_raw = features_raw[-min_len:]
        targets = targets[-min_len:]

        # 5. Analizar correlacion y filtrar features ruidosas
        try:
            correlations = await self._analyzer.compute_correlations(
                features_raw, targets, cfg.features
            )
            features_filtered, feature_names = await self._analyzer.filter_features(
                features_raw, targets, cfg.features, min_correlation=0.05
            )
        except AnalysisError as e:
            raise TrainModelError(f"feature_analysis_failed: {e}") from e

        # 6. Normalizar
        features_norm, means, stds = await self._preprocessor.normalize(
            features_filtered
        )

        # 7. Crear ventanas
        try:
            windows = await self._preprocessor.create_windows(
                features_norm, cfg.lookback
            )
        except InsufficientDataError as e:
            raise TrainModelError(f"windowing_failed: {e}") from e

        # 8. Alinear targets con ventanas (las primeras lookback-1 no tienen ventana completa)
        targets_aligned = targets[cfg.lookback - 1 :]
        targets_aligned = targets_aligned[: len(windows)]

        # 9. Dividir train/val/test
        n = len(windows)
        n_test = int(n * test_split)
        n_val = int(n * val_split)
        n_train = n - n_test - n_val

        x_train, y_train = windows[:n_train], targets_aligned[:n_train]
        x_val, y_val = windows[n_train : n_train + n_val], targets_aligned[n_train : n_train + n_val]
        x_test, y_test = windows[-n_test:], targets_aligned[-n_test:]

        # 10. Entrenar
        try:
            metrics = await self._trainer.train(
                cfg, x_train, y_train, x_val, y_val
            )
        except TrainingError as e:
            raise TrainModelError(f"training_failed: {e}") from e

        # 11. Construir entidad de dominio
        model_version = f"1.0.{_epoch_ts()}"
        model = NovaQuantModel(
            config=cfg,
            model_version=model_version,
            trained_at=datetime.now(timezone.utc),
            weights_hash="",  # se asigna al persistir
            feature_means=tuple(means),
            feature_stds=tuple(stds),
            metrics=metrics,
        )

        # 12. Persistir (aun sin pesos reales, es placeholder)
        # Los pesos se asignan en el adapter de ModelTrainer
        # y se pasan al repo junto con el modelo.
        try:
            await self._repo.save(model, b"")
        except CheckpointIOError as e:
            raise TrainModelError(f"checkpoint_save_failed: {e}") from e

        return TrainModelResult(
            model=model,
            metrics=metrics,
            features_used=feature_names,
            correlations=correlations,
            train_samples=len(x_train),
            val_samples=len(x_val),
            test_samples=len(x_test),
        )


def _epoch_ts() -> int:
    """Timestamp Unix en segundos para versionado."""
    return int(datetime.now(timezone.utc).timestamp())
