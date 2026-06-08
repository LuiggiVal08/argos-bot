"""Value Object: BacktestConfig — configuracion de un backtest."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime


@dataclass(frozen=True)
class BacktestConfig:
    """Configuracion completa de una corrida de backtest.

    Attributes:
        strategy_id: Identificador de la estrategia (ej: 'ema_cross', 'rsi_reversion').
        symbol: Par de trading (ej: 'BTC/USDT').
        timeframe: Temporalidad de velas (ej: '1h', '4h', '1d').
        start: Fecha ISO o timestamp ms de inicio.
        end: Fecha ISO o timestamp ms de fin.
        initial_balance: Balance inicial en USDT.
        risk_pct: % del balance a arriesgar por trade (0.01 = 1%).
        max_trades: Maximo de trades a permitir (0 = ilimitado).
    """

    strategy_id: str
    symbol: str
    timeframe: str = "1h"
    start: str | None = None
    end: str | None = None
    initial_balance: Decimal = Decimal("10000")
    risk_pct: Decimal = Decimal("0.01")
    max_trades: int = 0

    def __post_init__(self) -> None:
        if self.initial_balance <= Decimal("0"):
            raise ValueError(
                f"initial_balance must be positive, got {self.initial_balance}"
            )
        if not Decimal("0") < self.risk_pct <= Decimal("0.02"):
            raise ValueError(
                f"risk_pct must be in (0, 0.02], got {self.risk_pct}"
            )
        if self.max_trades < 0:
            raise ValueError(
                f"max_trades must be >= 0, got {self.max_trades}"
            )
        if not self.strategy_id:
            raise ValueError("strategy_id must not be empty")
        if not self.symbol:
            raise ValueError("symbol must not be empty")
