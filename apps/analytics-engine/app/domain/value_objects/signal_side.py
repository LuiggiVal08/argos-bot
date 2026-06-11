"""Enum of possible trading signal directions.

BUY  → Go long (entrar en posición larga)
SELL → Go short (entrar en posición corta)
HOLD → No hacer nada / mantenerse fuera

Per spec section 5 Historia 6 (NovaQuant): la red neuronal clasifica
cada ventana de velas en una de estas 3 clases. La decisión final
pasa por un filtro de confianza y confirmación de indicadores antes
de enviarse al PlaceOrderUseCase.
"""
from __future__ import annotations

from enum import Enum


class SignalSide(str, Enum):
    """Dirección de la señal de trading.

    Valores: BUY, SELL, HOLD.
    """

    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
