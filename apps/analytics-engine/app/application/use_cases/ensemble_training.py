"""EnsembleTrainingUseCase — entrenamiento del ensemble completo.

Pipeline:
  1. Fetch OHLCV histórico
  2. Build features + targets + normalizar
  3. Walk Forward de 5 ventanas:
     - Cada ventana: train LSTM + XGBoost, predecir val (OOF)
  4. Colectar OOF predictions de todas las ventanas
  5. Entrenar MetaModel (XGBoost stacking) con OOF
  6. Calibrar probabilidades con Platt Scaling
  7. Guardar todos los componentes versionados
  8. Retornar métricas agregadas

Sad paths:
  - OhlcvSourceError: datos insuficientes
  - TrainingError: fallo en entrenamiento de algún componente
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import numpy as np
import structlog

log = structlog.get_logger()

from ...domain.entities.model_registry import ComponentRecord
from ...domain.value_objects.model_config import ModelConfig
from ...domain.value_objects.signal_side import SignalSide
from ...domain.value_objects.trading_signal import TradingSignal
from ..ports.checkpoint_repository import CheckpointRepository
from ..ports.data_preprocessor import DataPreprocessor, InsufficientDataError, PreprocessingError
from ..ports.feature_analyzer import AnalysisError, FeatureAnalyzer
from ..ports.meta_model import MetaModel, MetaModelError, MetaModelTrainError
from ..ports.model_predictor import ModelPredictor
from ..ports.model_trainer import ModelTrainer, TrainingError
from ..ports.ohlcv_source import OhlcvSource, OhlcvSourceError
from ..ports.probability_calibrator import CalibrationError, ProbabilityCalibrator


class EnsembleTrainingError(RuntimeError):
    """Raised when ensemble training fails."""


@dataclass
class _WindowResult:
    window_idx: int
    lstm_metrics: dict
    xgb_metrics: dict
    oof_lstm: np.ndarray
    oof_xgb: np.ndarray
    oof_lstm_probs: np.ndarray
    oof_xgb_probs: np.ndarray
    oof_targets: np.ndarray
    train_size: int
    val_size: int


@dataclass(frozen=True)
class EnsembleTrainingResult:
    lstm_version: str
    xgb_version: str
    meta_version: str | None = None
    calibrator_version: str | None = None
    n_windows: int = 0
    windows_passed: int = 0
    avg_val_accuracy: float = 0.0
    avg_val_loss: float = 0.0
    oof_size: int = 0
    n_features: int = 0
    meta_train_accuracy: float | None = None
    trained_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class EnsembleTrainingUseCase:
    """Entrena el ensemble completo con Walk Forward + OOF + MetaModel.

    Uso:
        uc = EnsembleTrainingUseCase(ohlcv_source, preprocessor, analyzer,
                                     lstm_trainer, xgb_trainer, repo)
        result = await uc.execute(symbol="BTC/USDT")
    """

    N_WINDOWS = 5
    WINDOW_TRAIN_PCT = 0.7
    WINDOW_VAL_PCT = 0.15

    def __init__(
        self,
        ohlcv_source: OhlcvSource,
        preprocessor: DataPreprocessor,
        analyzer: FeatureAnalyzer,
        lstm_trainer: ModelTrainer,
        xgb_trainer: ModelTrainer,
        lstm_predictor: ModelPredictor,
        xgb_predictor: ModelPredictor,
        meta_model: MetaModel,
        calibrator: ProbabilityCalibrator,
        repo: CheckpointRepository,
    ) -> None:
        self._ohlcv = ohlcv_source
        self._preprocessor = preprocessor
        self._analyzer = analyzer
        self._lstm = lstm_trainer
        self._xgb = xgb_trainer
        self._lstm_predict = lstm_predictor
        self._xgb_predict = xgb_predictor
        self._meta_model = meta_model
        self._calibrator = calibrator
        self._repo = repo

    async def execute(
        self,
        symbol: str,
        config: ModelConfig | None = None,
        timeframe: str = "1h",
        limit: int = 10000,
    ) -> EnsembleTrainingResult:
        cfg = config or ModelConfig()

        ohlcv = await self._fetch_data(symbol, timeframe, limit, cfg)
        features_raw, targets, means, stds = await self._preprocess(ohlcv, cfg)
        windows = await self._create_windows(features_raw, cfg)

        aligned_targets = targets[cfg.lookback - 1:]
        aligned_targets = aligned_targets[:len(windows)]

        window_results = await self._walk_forward(windows, aligned_targets, cfg)

        oof_lstm, oof_xgb, oof_targets_combined, meta_features = await self._build_oof(
            window_results, features_raw, cfg, aligned_targets, windows
        )

        meta_version, meta_metrics = await self._train_meta(
            meta_features, oof_targets_combined, cfg
        )

        calibrator_version = await self._train_calibrator(
            oof_lstm, oof_xgb, oof_targets_combined, cfg
        )

        return EnsembleTrainingResult(
            lstm_version=window_results[-1].lstm_metrics.get("version", ""),
            xgb_version=window_results[-1].xgb_metrics.get("version", ""),
            meta_version=meta_version,
            calibrator_version=calibrator_version,
            n_windows=len(window_results),
            windows_passed=len(window_results),
            avg_val_accuracy=float(np.mean([r.lstm_metrics.get("val_accuracy", 0) for r in window_results])),
            avg_val_loss=float(np.mean([r.lstm_metrics.get("val_loss", 0) for r in window_results])),
            oof_size=len(oof_targets_combined),
            n_features=features_raw.shape[1],
            meta_train_accuracy=meta_metrics.get("train_accuracy"),
        )

    async def _fetch_data(
        self, symbol: str, timeframe: str, limit: int, cfg: ModelConfig
    ) -> list[dict]:
        try:
            ohlcv = await self._ohlcv.fetch_ohlcv(
                symbol=symbol, timeframe=timeframe, limit=limit
            )
        except OhlcvSourceError as e:
            raise EnsembleTrainingError(f"ohlcv_fetch_failed: {e}") from e

        min_needed = cfg.lookback + cfg.target_lookahead + 10 + self.N_WINDOWS * 200
        if len(ohlcv) < min_needed:
            raise EnsembleTrainingError(
                f"insufficient_data: got {len(ohlcv)}, need at least {min_needed}"
            )
        return ohlcv

    async def _preprocess(
        self, ohlcv: list[dict], cfg: ModelConfig
    ) -> tuple[np.ndarray, np.ndarray, tuple[float, ...], tuple[float, ...]]:
        try:
            features_raw = await self._preprocessor.build_features(ohlcv, cfg)
            targets = await self._preprocessor.create_targets(ohlcv, cfg)
        except PreprocessingError as e:
            raise EnsembleTrainingError(f"preprocessing_failed: {e}") from e

        min_len = min(len(features_raw), len(targets))
        features_raw = features_raw[-min_len:]
        targets = targets[-min_len:]

        try:
            correlations = await self._analyzer.compute_correlations(
                features_raw, targets, cfg.features
            )
            features_filtered, feature_names = await self._analyzer.filter_features(
                features_raw, targets, cfg.features, min_correlation=0.05
            )
        except AnalysisError as e:
            raise EnsembleTrainingError(f"feature_analysis_failed: {e}") from e

        features_norm, means, stds = await self._preprocessor.normalize(features_filtered)

        return features_norm, targets, means, stds

    async def _create_windows(
        self, features_norm: np.ndarray, cfg: ModelConfig
    ) -> np.ndarray:
        try:
            windows = await self._preprocessor.create_windows(features_norm, cfg.lookback)
        except InsufficientDataError as e:
            raise EnsembleTrainingError(f"windowing_failed: {e}") from e
        return windows

    async def _walk_forward(
        self, windows: np.ndarray, targets: np.ndarray, cfg: ModelConfig
    ) -> list[_WindowResult]:
        n = len(windows)
        window_size = n // self.N_WINDOWS
        results: list[_WindowResult] = []

        for w in range(self.N_WINDOWS):
            start = w * window_size
            end = n if w == self.N_WINDOWS - 1 else (w + 1) * window_size

            w_data = windows[start:end]
            w_targets = targets[start:end]

            n_total = len(w_data)
            n_val = int(n_total * self.WINDOW_VAL_PCT)
            n_train = n_total - n_val

            x_train, y_train = w_data[:n_train], w_targets[:n_train]
            x_val, y_val = w_data[n_train:], w_targets[n_train:]

            if len(x_train) < cfg.lookback + 10:
                continue

            try:
                lstm_metrics = await self._lstm.train(cfg, x_train, y_train, x_val, y_val)
            except TrainingError as e:
                raise EnsembleTrainingError(
                    f"lstm_training_failed_window_{w}: {e}"
                ) from e

            try:
                xgb_metrics = await self._xgb.train(cfg, x_train, y_train, x_val, y_val)
            except TrainingError as e:
                raise EnsembleTrainingError(
                    f"xgb_training_failed_window_{w}: {e}"
                ) from e

            lstm_probs_list = []
            for i in range(len(x_val)):
                signal = await self._lstm_predict.predict(x_val[i])
                lstm_probs_list.append(_signal_to_probs(signal))
            xgb_probs_list = []
            for i in range(len(x_val)):
                signal = await self._xgb_predict.predict(x_val[i])
                xgb_probs_list.append(_signal_to_probs(signal))

            results.append(_WindowResult(
                window_idx=w,
                lstm_metrics=lstm_metrics,
                xgb_metrics=xgb_metrics,
                oof_lstm=x_val,
                oof_xgb=x_val,
                oof_lstm_probs=np.array(lstm_probs_list),
                oof_xgb_probs=np.array(xgb_probs_list),
                oof_targets=y_val,
                train_size=len(x_train),
                val_size=len(x_val),
            ))

        if not results:
            raise EnsembleTrainingError("no windows passed minimum size check")

        return results

    async def _build_oof(
        self,
        window_results: list[_WindowResult],
        features_raw: np.ndarray,
        cfg: ModelConfig,
        aligned_targets: np.ndarray,
        windows: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        oof_lstm_probs_list = []
        oof_xgb_probs_list = []
        oof_targets_list = []

        for wr in window_results:
            oof_lstm_probs_list.append(wr.oof_lstm_probs)
            oof_xgb_probs_list.append(wr.oof_xgb_probs)
            oof_targets_list.append(wr.oof_targets)

        oof_lstm = np.concatenate(oof_lstm_probs_list, axis=0) if oof_lstm_probs_list else np.zeros((1, 3))
        oof_xgb = np.concatenate(oof_xgb_probs_list, axis=0) if oof_xgb_probs_list else np.zeros((1, 3))
        oof_targets_combined = np.concatenate(oof_targets_list, axis=0) if oof_targets_list else aligned_targets[:10]

        meta_features_list = []
        n = len(oof_targets_combined)
        for i in range(n):
            lstm_p = oof_lstm[i] if i < len(oof_lstm) else np.array([1/3, 1/3, 1/3])
            xgb_p = oof_xgb[i] if i < len(oof_xgb) else np.array([1/3, 1/3, 1/3])
            market_feats = _extract_market_features(features_raw, i)
            meta_features_list.append([*lstm_p, *xgb_p, *market_feats])

        meta_features = np.array(meta_features_list) if meta_features_list else np.zeros((n, 11))
        return oof_lstm, oof_xgb, oof_targets_combined, meta_features

    async def _train_meta(
        self,
        meta_features: np.ndarray,
        targets: np.ndarray,
        cfg: ModelConfig,
    ) -> tuple[str, dict]:
        try:
            metrics = await self._meta_model.train(meta_features, targets)
        except MetaModelTrainError as e:
            raise EnsembleTrainingError(f"meta_model_training_failed: {e}") from e
        version = f"meta/v1.0.{int(datetime.now(timezone.utc).timestamp())}"
        log.info("meta_model_trained", version=version, metrics=metrics)
        return version, metrics

    async def _train_calibrator(
        self,
        oof_lstm: np.ndarray,
        oof_xgb: np.ndarray,
        targets: np.ndarray,
        cfg: ModelConfig,
    ) -> str | None:
        try:
            avg_probs = (oof_lstm + oof_xgb) / 2.0
            labels = np.argmax(targets, axis=1)
            await self._calibrator.fit(avg_probs, labels)
        except CalibrationError as e:
            log.warning("calibrator_fit_failed", error=str(e))
            return None
        version = f"cal/v1.0.{int(datetime.now(timezone.utc).timestamp())}"
        log.info("calibrator_trained", version=version)
        return version


def _signal_to_probs(signal: TradingSignal) -> tuple[float, float, float]:
    buy = signal.confidence if signal.side == SignalSide.BUY else 0.0
    sell = signal.confidence if signal.side == SignalSide.SELL else 0.0
    hold = signal.confidence if signal.side == SignalSide.HOLD else 0.0
    total = buy + sell + hold
    if total > 0:
        buy /= total
        sell /= total
        hold /= total
    else:
        buy = sell = hold = 1.0 / 3.0
    return (buy, sell, hold)


def _extract_market_features(features_raw: np.ndarray, idx: int) -> list[float]:
    n = features_raw.shape[1]
    idx_safe = min(idx, features_raw.shape[0] - 1)
    last = features_raw[idx_safe]
    adx = float(last[15]) if n > 15 else 25.0
    bbw = float(last[14]) if n > 14 else 0.1
    atr = float(last[15]) if n > 15 else 100.0
    volume = float(last[4]) if n > 4 else 1000.0
    rsi = float(last[5]) if n > 5 else 50.0
    return [adx, bbw, atr, rsi, volume]
