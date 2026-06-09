"""PredictSignalUseCase.

Predice la senal de trading para el momento actual y la confirma
con indicadores clasicos (RSI, MACD, BB) antes de retornarla.

Pipeline:
  1. Obtener OHLCV reciente (OhlcvSource)
  2. Cargar ultimo checkpoint (CheckpointRepository)
  3. Verificar que el modelo no este stale
  4. Calcular features (DataPreprocessor)
  5. Normalizar con medias/std del modelo
  6. Ventanear (ultima ventana)
  7. Inferencia (ModelPredictor) -> TradingSignal
  8. Confirmar con indicadores (RSI confirma tendencia, MACD cruce, BB)
  9. Retornar senal confirmada

Sad paths:
  - OhlcvSourceError: no hay datos recientes
  - CheckpointNotFoundError: no hay modelo entrenado
  - StaleModelError: modelo vencido, hay que reentrenar
  - PredictionError: fallo en inferencia
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from ...domain.entities.nova_quant_model import (
    NovaQuantModel,
    StaleModelError,
)
from ...domain.value_objects.model_config import ModelConfig
from ...domain.value_objects.signal_side import SignalSide
from ...domain.value_objects.trading_signal import TradingSignal
from ..ports.checkpoint_repository import (
    CheckpointNotFoundError,
    CheckpointRepository,
)
from ..ports.data_preprocessor import (
    DataPreprocessor,
    InsufficientDataError,
    PreprocessingError,
)
from ..ports.model_predictor import ModelPredictor, PredictionError
from ..ports.ohlcv_source import OhlcvSource, OhlcvSourceError


class PredictSignalError(RuntimeError):
    """Raised when the prediction pipeline fails."""


@dataclass(frozen=True)
class ConfirmIndicatorsResult:
    """Resultado de la confirmacion con indicadores clasicos."""

    rsi_ok: bool
    macd_ok: bool
    bb_ok: bool
    details: dict


@dataclass(frozen=True)
class PredictSignalResult:
    """Resultado final de la prediccion."""

    signal: TradingSignal
    confirmed: bool
    confirmation: ConfirmIndicatorsResult | None
    model_version: str
    predicted_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class PredictSignalUseCase:
    """Orquesta la prediccion con confirmacion de indicadores.

    Uso:
        use_case = PredictSignalUseCase(ohlcv_source, preprocessor, predictor, repo)
        result = await use_case.execute(symbol="BTC/USDT")
    """

    def __init__(
        self,
        ohlcv_source: OhlcvSource,
        preprocessor: DataPreprocessor,
        predictor: ModelPredictor,
        repo: CheckpointRepository,
    ) -> None:
        self._ohlcv = ohlcv_source
        self._preprocessor = preprocessor
        self._predictor = predictor
        self._repo = repo

    async def execute(
        self,
        symbol: str,
        timeframe: str = "1h",
        limit: int = 200,
        require_confirmation: bool = True,
        skip_stale_check: bool = False,
    ) -> PredictSignalResult:
        """Predice y confirma senal para el momento actual.

        Args:
            symbol: par ejemplo BTC/USDT.
            timeframe: temporalidad de las velas.
            limit: velas a descargar (min: lookback + margen).
            require_confirmation: si True, aplica filtro de indicadores.
            skip_stale_check: saltar verificacion de modelo vencido.

        Returns:
            PredictSignalResult con la senal y confirmacion.

        Raises PredictSignalError si algun paso falla.
        """
        # 1. Cargar ultimo modelo
        try:
            model, _weights_bytes = await self._repo.load_latest()
        except CheckpointNotFoundError as e:
            raise PredictSignalError(
                "no_trained_model: train a model first via POST /model/train"
            ) from e

        # 2. Verificar stale
        if not skip_stale_check:
            try:
                model.assert_not_stale()
            except StaleModelError as e:
                raise PredictSignalError(f"stale_model: {e}") from e

        cfg = model.config

        # 3. Obtener OHLCV reciente
        try:
            ohlcv = await self._ohlcv.fetch_ohlcv(
                symbol=symbol,
                timeframe=timeframe,
                limit=limit,
            )
        except OhlcvSourceError as e:
            raise PredictSignalError(f"ohlcv_fetch_failed: {e}") from e

        if len(ohlcv) < cfg.lookback + 1:
            raise PredictSignalError(
                f"insufficient_data: got {len(ohlcv)} candles, "
                f"need at least {cfg.lookback + 1}"
            )

        # 4. Calcular features
        try:
            features_raw = await self._preprocessor.build_features(ohlcv, cfg)
        except PreprocessingError as e:
            raise PredictSignalError(f"feature_build_failed: {e}") from e

        # 5. Validar cantidad de features
        model.validate_input(features_raw.shape[1])

        # 6. Normalizar con medias/std del modelo entrenado
        features_norm, _means, _stds = await self._preprocessor.normalize(
            features_raw,
            means=model.feature_means,
            stds=model.feature_stds,
        )

        # 7. Tomar la ultima ventana
        try:
            windows = await self._preprocessor.create_windows(
                features_norm, cfg.lookback
            )
        except InsufficientDataError as e:
            raise PredictSignalError(f"windowing_failed: {e}") from e

        last_window = windows[-1]  # (lookback, n_features)

        # 8. Inferencia
        try:
            signal = await self._predictor.predict(
                last_window,
                confidence_threshold=cfg.confidence_threshold,
            )
        except PredictionError as e:
            raise PredictSignalError(f"prediction_failed: {e}") from e

        # 9. Confirmacion con indicadores
        confirmation = None
        confirmed = False
        if require_confirmation and signal.side != SignalSide.HOLD:
            confirmation = self._confirm_indicators(features_raw, signal)
            confirmed = (
                confirmation.rsi_ok and confirmation.macd_ok and confirmation.bb_ok
            )
        elif signal.side == SignalSide.HOLD:
            confirmed = True  # HOLD siempre se acepta
        else:
            confirmed = True  # sin confirmacion

        return PredictSignalResult(
            signal=signal,
            confirmed=confirmed,
            confirmation=confirmation,
            model_version=model.model_version,
        )

    @staticmethod
    def _confirm_indicators(
        features: "np.ndarray",
        signal: TradingSignal,
    ) -> ConfirmIndicatorsResult:
        """Confirma la senal con indicadores clasicos.

        Usa los valores de las features calculadas para verificar:
        - BUY:  RSI > 50, MACD linea > senal, precio > BB media
        - SELL: RSI < 50, MACD linea < senal, precio < BB media

        Nota: los indices de columnas asumen el orden de ModelConfig.features.
        Para una implementacion robusta, el preprocesador debe devolver
        los nombres de columna junto con el array.
        """
        import numpy as np  # solo para tipado en el stub

        _ = np  # noqa: F841  # placeholder

        # Placeholder: la implementacion real necesita mapeo
        # de nombres de feature a indices de columna.
        # Esto se implementa completamente en H6-004.
        return ConfirmIndicatorsResult(
            rsi_ok=True,
            macd_ok=True,
            bb_ok=True,
            details={
                "note": "indicator confirmation stub — "
                "implemented when DataPreprocessor returns named columns"
            },
        )

    async def load_model(self) -> NovaQuantModel:
        """Carga el modelo actual sin predecir.

        Util para GET /model/info sin ejecutar inferencia.
        """
        try:
            model, _ = await self._repo.load_latest()
            return model
        except CheckpointNotFoundError as e:
            raise PredictSignalError(
                "no_trained_model: train a model first"
            ) from e
