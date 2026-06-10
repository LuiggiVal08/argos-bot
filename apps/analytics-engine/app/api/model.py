"""NovaQuant model API: training and prediction endpoints.

POST /model/train      -> entrena un nuevo modelo desde velas historicas
POST /model/predict    -> predice senal para el momento actual
GET  /model/info       -> informacion del modelo actual (version, metricas, features)
GET  /model/features   -> analisis de correlacion de features

Sad paths (todas retornan 422 con detalle en texto):
  - OhlcvSourceError: no se pudieron obtener velas
  - InsufficientDataError: pocos datos para el lookback
  - CheckpointNotFoundError: no hay modelo entrenado
  - StaleModelError: modelo vencido
  - TrainingError: fallo en entrenamiento
  - PredictionError: fallo en inferencia
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from ..application.use_cases.predict_signal import (
    PredictSignalError,
    PredictSignalUseCase,
)
from ..application.use_cases.train_model import (
    TrainModelError,
    TrainModelUseCase,
)
from ..composition import get_model_use_cases

router = APIRouter(prefix="/model", tags=["model"])


@router.post(
    "/train",
    summary="Train a new NovaQuant LSTM model from historical OHLCV.",
)
async def train_model(
    request: Request,
    symbol: str = "BTC/USDT",
    timeframe: str = "1h",
    limit: int = 5000,
) -> dict:
    """Entrena un modelo LSTM con velas historicas.

    Args:
        symbol: par de trading (default BTC/USDT).
        timeframe: temporalidad de velas (default 1h).
        limit: max velas a descargar (default 5000).

    Returns:
        Dict con metricas de entrenamiento.
    """
    use_cases = await get_model_use_cases(request)
    try:
        result = await use_cases.train.execute(
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
        )
    except TrainModelError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    return {
        "status": "ok",
        "model_version": result.model.model_version,
        "features_used": list(result.features_used),
        "metrics": result.metrics,
        "train_samples": result.train_samples,
        "val_samples": result.val_samples,
        "test_samples": result.test_samples,
    }


@router.post(
    "/predict",
    summary="Predict trading signal for the current moment.",
)
async def predict_signal(
    request: Request,
    symbol: str = "BTC/USDT",
    timeframe: str = "1h",
    require_confirmation: bool = True,
) -> dict:
    """Predice la senal de trading actual y la confirma con indicadores.

    Args:
        symbol: par de trading (default BTC/USDT).
        timeframe: temporalidad de velas (default 1h).
        require_confirmation: si True, aplica filtro RSI+MACD+BB.

    Returns:
        Dict con senal, confianza, y confirmacion.
    """
    use_cases = await get_model_use_cases(request)
    try:
        result = await use_cases.predict.execute(
            symbol=symbol,
            timeframe=timeframe,
        )
    except PredictSignalError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    return {
        "status": "ok",
        "signal": result.signal.side.value,
        "confidence": result.signal.confidence,
        "actionable": result.signal.is_actionable(),
        "confirmed": result.confirmed,
        "model_version": result.model_version,
        "confirmation": {
            "rsi_ok": result.confirmation.rsi_ok if result.confirmation else None,
            "macd_ok": result.confirmation.macd_ok if result.confirmation else None,
            "bb_ok": result.confirmation.bb_ok if result.confirmation else None,
        }
        if result.confirmation
        else None,
    }


@router.get(
    "/info",
    summary="Get current model info (version, metrics, features).",
)
async def model_info(request: Request) -> dict:
    """Retorna informacion del modelo actualmente cargado."""
    use_cases = await get_model_use_cases(request)
    try:
        model = await use_cases.predict.load_model()
    except PredictSignalError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    return {
        "status": "ok",
        "model_version": model.model_version,
        "trained_at": model.trained_at.isoformat(),
        "age_days": round(model.age_days, 2),
        "is_stale": model.is_stale,
        "features": list(model.config.features),
        "lookback": model.config.lookback,
        "confidence_threshold": model.config.confidence_threshold,
        "metrics": model.metrics,
    }


@router.get(
    "/features",
    summary="Analyze feature correlations with the target.",
)
async def analyze_features(
    request: Request,
    symbol: str = "BTC/USDT",
    timeframe: str = "1h",
    limit: int = 1000,
) -> dict:
    """Analiza correlacion de features con el target (BUY/SELL/HOLD).

    Args:
        symbol: par de trading (default BTC/USDT).
        timeframe: temporalidad de velas (default 1h).
        limit: velas a analizar (default 1000).

    Returns:
        Dict con correlaciones y features filtradas.
    """
    use_cases = await get_model_use_cases(request)
    try:
        result = await use_cases.train.execute(
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
        )
    except TrainModelError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    return {
        "status": "ok",
        "features_used": list(result.features_used),
        "correlations": result.correlations,
        "train_samples": result.train_samples,
    }
