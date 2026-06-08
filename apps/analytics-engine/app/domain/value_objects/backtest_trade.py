"""Value Object: BacktestTrade — registro de un trade simulado."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime

from .signal_side import SignalSide


@dataclass(frozen=True)
class BacktestTrade:
    """Registro de un trade ejecutado durante el backtest.

    Attributes:
        side: Direccion del trade (BUY/SELL).
        entry_time: Timestamp de entrada (UTC).
        entry_price: Precio de entrada en USDT.
        exit_time: Timestamp de salida (UTC).
        exit_price: Precio de salida en USDT.
        units: Cantidad de unidades del activo.
        pnl: PnL del trade en USDT (positivo = ganancia).
        pnl_pct: PnL porcentual respecto al capital invertido.
        entry_reason: Señal que genero la entrada.
        exit_reason: Señal que genero la salida (o 'stop_loss').
        duration_min: Duracion del trade en minutos.
    """

    side: SignalSide
    entry_time: datetime
    entry_price: Decimal
    exit_time: datetime
    exit_price: Decimal
    units: Decimal
    pnl: Decimal
    pnl_pct: Decimal
    entry_reason: str = ""
    exit_reason: str = ""
    duration_min: int = 0

    def __post_init__(self) -> None:
        if self.units <= Decimal("0"):
            raise ValueError(f"units must be positive, got {self.units}")
        if self.entry_price <= Decimal("0"):
            raise ValueError(
                f"entry_price must be positive, got {self.entry_price}"
            )
        if self.exit_price <= Decimal("0"):
            raise ValueError(
                f"exit_price must be positive, got {self.exit_price}"
            )
