"""Strategy port — interfaz para estrategias de trading backtesteables.

Cada estrategia recibe la configuracion del backtest y un callable
de progreso, y retorna una funcion de senal compatible con BacktestEngine.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ...domain.value_objects.backtest_config import BacktestConfig
from ...domain.value_objects.signal_side import SignalSide
from ...domain.entities.backtest_engine import SignalFn


SignalSideLike = SignalSide | str
"""Acepta SignalSide nativo o string 'BUY'/'SELL'/'HOLD'."""


@runtime_checkable
class Strategy(Protocol):
    """Protocolo que toda estrategia de trading debe implementar.

    El metodo `build` retorna una SignalFn que el BacktestEngine
    usa para generar senales en cada vela.
    """

    def build(self, config: BacktestConfig) -> SignalFn:
        """Construye la funcion de senal para este backtest.

        Args:
            config: Configuracion del backtest (strategy_id, timeframe, etc).

        Returns:
            SignalFn: (idx, ohlcv, config) -> (side, confidence) | None
        """
        ...


@runtime_checkable
class StrategyRegistry(Protocol):
    """Registro de estrategias disponibles para backtesting."""

    def get(self, strategy_id: str) -> Strategy | None:
        """Retorna la estrategia por su ID, o None si no existe."""
        ...

    def list_ids(self) -> list[str]:
        """Lista los IDs de estrategias registradas."""
        ...
