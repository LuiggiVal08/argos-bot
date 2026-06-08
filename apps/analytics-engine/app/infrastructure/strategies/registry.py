"""StrategyDictRegistry — registro de estrategias en memoria."""

from __future__ import annotations

from typing import Any

from .ema_cross import EmaCrossStrategy
from .rsi_mean_reversion import RsiMeanReversionStrategy


class StrategyDictRegistry:
    """Registro simple de estrategias basado en dict.

    Las estrategias se instancian con defaults y se registran por ID.
    """

    def __init__(self) -> None:
        self._strategies: dict[str, Any] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        self._strategies["ema_cross"] = EmaCrossStrategy()
        self._strategies["rsi_reversion"] = RsiMeanReversionStrategy()

    def get(self, strategy_id: str) -> Any | None:
        return self._strategies.get(strategy_id)

    def list_ids(self) -> list[str]:
        return list(self._strategies.keys())

    def register(self, strategy_id: str, strategy: Any) -> None:
        """Registra una estrategia adicional."""
        self._strategies[strategy_id] = strategy
