"""Backtest API: ejecucion de backtests sobre datos historicos.

POST /backtest/run  -> ejecuta un backtest con la configuracion dada
GET  /backtest/strategies -> lista las estrategias disponibles

Sad paths (todas retornan 422 con detalle en texto):
  - Strategy not found
  - OhlcvSourceError / datos insuficientes
  - Error interno del motor
"""
from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, HTTPException, Request

from ..application.use_cases.run_backtest import (
    RunBacktestError,
    RunBacktestUseCase,
)
from ..composition import get_backtest_registry, get_backtest_usecase
from ..domain.value_objects.backtest_config import BacktestConfig

router = APIRouter(prefix="/backtest", tags=["backtest"])


@router.post(
    "/run",
    summary="Run a backtest with the given configuration.",
)
async def run_backtest(
    request: Request,
    strategy_id: str = "ema_cross",
    symbol: str = "BTC/USDT",
    timeframe: str = "1h",
    start: str | None = None,
    end: str | None = None,
    initial_balance: float = 10_000.0,
    risk_pct: float = 0.01,
    max_trades: int = 0,
) -> dict:
    """Ejecuta un backtest sobre datos historicos.

    Args:
        request: FastAPI request (para DI).
        strategy_id: Estrategia a usar (default: ema_cross).
        symbol: Par de trading (default: BTC/USDT).
        timeframe: Temporalidad (default: 1h).
        start: Fecha ISO inicio (opcional).
        end: Fecha ISO fin (opcional).
        initial_balance: Balance inicial en USDT (default: 10000).
        risk_pct: % de riesgo por trade (default: 0.01).
        max_trades: Max trades (0 = ilimitado).

    Returns:
        Dict con metricas, trades, y ruta del reporte.
    """
    try:
        config = BacktestConfig(
            strategy_id=strategy_id,
            symbol=symbol,
            timeframe=timeframe,
            start=start,
            end=end,
            initial_balance=Decimal(str(initial_balance)),
            risk_pct=Decimal(str(risk_pct)),
            max_trades=max_trades,
        )
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    use_case: RunBacktestUseCase = get_backtest_usecase(request)
    try:
        result = await use_case.execute(config)
    except RunBacktestError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    return {
        "status": "ok",
        "strategy_id": result.config.strategy_id,
        "symbol": result.config.symbol,
        "timeframe": result.config.timeframe,
        "metrics": {
            "sharpe_ratio": result.metrics.sharpe_ratio,
            "max_drawdown_pct": result.metrics.max_drawdown_pct,
            "win_rate": result.metrics.win_rate,
            "total_return_pct": float(result.metrics.total_return_pct),
            "total_trades": result.metrics.total_trades,
            "winning_trades": result.metrics.winning_trades,
            "losing_trades": result.metrics.losing_trades,
            "avg_pnl_usdt": float(result.metrics.avg_pnl_usdt),
            "final_balance": float(result.metrics.final_balance),
            "volatility_pct": result.metrics.volatility_pct,
            "profit_factor": result.metrics.profit_factor,
        },
        "trade_count": result.trade_count,
        "report_path": result.report_path,
        "duration_seconds": result.duration_seconds,
    }


@router.get(
    "/strategies",
    summary="List available backtest strategies.",
)
async def list_strategies(request: Request) -> dict:
    """Retorna la lista de estrategias disponibles."""
    registry = get_backtest_registry(request)
    return {
        "status": "ok",
        "strategies": registry.list_ids(),
    }
