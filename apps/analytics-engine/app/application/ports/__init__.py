"""Application ports (Protocol classes for adapter contracts).

Each port abstracts an I/O concern that the use cases need but must
not couple to. The infrastructure layer provides the concrete
adapters (CCXT, TA, broker).
"""
from .balance_provider import BalanceProvider, BalanceProviderError
from .atr_calculator import AtrCalculator, AtrCalculatorError
from .min_lot_provider import MinLotProvider, MinLotProviderError, MarketConstraints

__all__ = [
    "BalanceProvider",
    "BalanceProviderError",
    "AtrCalculator",
    "AtrCalculatorError",
    "MinLotProvider",
    "MinLotProviderError",
    "MarketConstraints",
]
