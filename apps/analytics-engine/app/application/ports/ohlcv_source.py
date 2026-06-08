"""OhlcvSource port.

Proporciona velas historicas OHLCV para entrenamiento o prediccion.
El adapter concreto puede leer de CCXT (exchange), de un archivo CSV
local, o de Redis cache.

Sad paths:
  - OhlcvSourceError: exchange caido, archivo faltante, datos
    insuficientes para el lookback solicitado.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable


class OhlcvSourceError(RuntimeError):
    """Raised when OHLCV data cannot be obtained."""


@runtime_checkable
class OhlcvSource(Protocol):
    """Retorna velas historicas OHLCV como lista de dicts.

    Cada dict debe tener las llaves:
      timestamp, open, high, low, close, volume
    """

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1h",
        limit: int = 1000,
        since: int | None = None,
    ) -> list[dict]:
        """Retorna hasta `limit` velas desde `since` (timestamp ms).

        Raises OhlcvSourceError si no se pueden obtener.
        """
        ...
