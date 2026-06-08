"""BacktestReporter port — salida de resultados de backtest."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ...domain.value_objects.backtest_config import BacktestConfig
from ...domain.value_objects.backtest_metrics import BacktestMetrics
from ...domain.value_objects.backtest_trade import BacktestTrade
from ...domain.entities.backtest_engine import EquityPoint


@runtime_checkable
class BacktestReporter(Protocol):
    """Persiste los resultados de una corrida de backtest."""

    async def save(
        self,
        config: BacktestConfig,
        metrics: BacktestMetrics,
        trades: list[BacktestTrade],
        equity_curve: list[EquityPoint],
    ) -> str:
        """Guarda el reporte y retorna la ruta/identificador del mismo."""
        ...


@runtime_checkable
class MetricsCalculator(Protocol):
    """Calcula metricas de performance a partir de trades y equity."""

    def compute(
        self,
        trades: list[BacktestTrade],
        equity_curve: list[EquityPoint],
        initial_balance: object,
    ) -> BacktestMetrics:
        """Computa metricas de la corrida.

        Args:
            trades: Lista de trades ejecutados.
            equity_curve: Curva de equity (timestamp, balance).
            initial_balance: Balance inicial.

        Returns:
            BacktestMetrics con Sharpe, drawdown, win rate, etc.
        """
        ...
