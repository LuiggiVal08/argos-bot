"""Estrategias de trading concretas para backtesting."""
from .ema_cross import EmaCrossStrategy
from .rsi_mean_reversion import RsiMeanReversionStrategy
from .registry import StrategyDictRegistry

__all__ = [
    "EmaCrossStrategy",
    "RsiMeanReversionStrategy",
    "StrategyDictRegistry",
]
