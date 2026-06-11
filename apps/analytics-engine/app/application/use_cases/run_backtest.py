"""RunBacktestUseCase — orquesta una corrida de backtest completa.

Pipeline:
  1. Resolver estrategia por ID desde el registro
  2. Obtener OHLCV historico
  3. Construir SignalFn via la estrategia
  4. Ejecutar BacktestEngine.run()
  5. Calcular metricas
  6. Guardar reporte
  7. Retornar resultados
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..ports.backtest_reporter import BacktestReporter, MetricsCalculator
    from ..ports.ohlcv_source import OhlcvSource
    from ..ports.strategy import StrategyRegistry

from ...domain.entities.backtest_engine import BacktestEngine
from ...domain.value_objects.backtest_config import BacktestConfig
from ...domain.value_objects.backtest_metrics import BacktestMetrics
from ...domain.value_objects.backtest_trade import BacktestTrade


class RunBacktestError(RuntimeError):
    """Raised when backtest execution fails."""


@dataclass(frozen=True)
class RunBacktestResult:
    """Resultado completo de una corrida de backtest."""

    config: BacktestConfig
    metrics: BacktestMetrics
    trades: list[BacktestTrade]
    trade_count: int
    equity_points: int
    report_path: str
    duration_seconds: float
    started_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class RunBacktestUseCase:
    """Orquesta una corrida de backtest.

    Uso:
        use_case = RunBacktestUseCase(ohlcv_source, registry, calc, reporter)
        result = await use_case.execute(config)
    """

    def __init__(
        self,
        ohlcv_source: OhlcvSource,
        strategy_registry: StrategyRegistry,
        metrics_calculator: MetricsCalculator,
        reporter: BacktestReporter,
    ) -> None:
        self._ohlcv = ohlcv_source
        self._registry = strategy_registry
        self._metrics = metrics_calculator
        self._reporter = reporter

    async def execute(
        self,
        config: BacktestConfig,
    ) -> RunBacktestResult:
        """Ejecuta el backtest.

        Args:
            config: Configuracion del backtest.

        Returns:
            RunBacktestResult con metricas, trades y ruta del reporte.

        Raises:
            RunBacktestError: si la estrategia no existe, faltan datos,
                              o el motor falla.
        """
        import time
        started = time.monotonic()

        # 1. Resolver estrategia
        strategy = self._registry.get(config.strategy_id)
        if strategy is None:
            raise RunBacktestError(
                f"unknown_strategy: '{config.strategy_id}' not found. "
                f"Available: {self._registry.list_ids()}"
            )

        # 2. Obtener OHLCV
        try:
            from ..ports.ohlcv_source import OhlcvSourceError
            ohlcv = await self._ohlcv.fetch_ohlcv(
                symbol=config.symbol,
                timeframe=config.timeframe,
                limit=10_000,
            )
        except OhlcvSourceError as e:
            raise RunBacktestError(f"ohlcv_fetch_failed: {e}") from e

        if len(ohlcv) < 50:
            raise RunBacktestError(
                f"insufficient_candles: got {len(ohlcv)}, need at least 50"
            )

        # 3. Construir signal_fn
        signal_fn = strategy.build(config)

        # 4. Ejecutar motor
        engine = BacktestEngine()
        try:
            trades, equity_curve = engine.run(ohlcv, config, signal_fn)
        except BacktestError as e:
            raise RunBacktestError(f"engine_failed: {e}") from e

        # 5. Calcular metricas
        metrics = self._metrics.compute(trades, equity_curve, config.initial_balance)

        # 6. Guardar reporte
        report_path = await self._reporter.save(config, metrics, trades, equity_curve)

        elapsed = time.monotonic() - started

        return RunBacktestResult(
            config=config,
            metrics=metrics,
            trades=trades,
            trade_count=len(trades),
            equity_points=len(equity_curve),
            report_path=report_path,
            duration_seconds=round(elapsed, 3),
        )
