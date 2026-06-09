from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from .order import OrderSide


@dataclass(frozen=True)
class LivePosition:
    """Posición abierta en el exchange, trackeada por el execution engine.

    Attributes:
        position_id:   ID único de la posición.
        symbol:        Par operado.
        side:          BUY (long) o SELL (short).
        units:         Cantidad de contratos/unidades.
        entry_price:   Precio de entrada promedio.
        current_price: Último precio conocido (se actualiza vía tick).
        sl_price:      Stop Loss actual.
        tp_price:      Take Profit actual.
        unrealized_pnl: P&L no realizado en USD (aprox).
        opened_at:     Timestamp de apertura (UTC).
        closed_at:     Timestamp de cierre (UTC), None si abierta.
        realized_pnl:  P&L realizado al cierre (None si abierta).
        status:        "OPEN", "CLOSED", "SL_HIT", "TP_HIT".
        metadata:      Dict opcional.
    """

    position_id: str
    symbol: str
    side: OrderSide
    units: Decimal
    entry_price: Decimal
    current_price: Decimal
    sl_price: Decimal | None = None
    tp_price: Decimal | None = None
    unrealized_pnl: Decimal = Decimal("0")
    opened_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    closed_at: datetime | None = None
    realized_pnl: Decimal | None = None
    status: str = "OPEN"
    metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.units <= 0:
            raise ValueError(f"units must be > 0, got {self.units}")
        if self.entry_price <= 0:
            raise ValueError(f"entry_price must be > 0, got {self.entry_price}")
        if self.current_price <= 0:
            raise ValueError(f"current_price must be > 0, got {self.current_price}")
        if self.status not in ("OPEN", "CLOSED", "SL_HIT", "TP_HIT"):
            raise ValueError(
                f"status must be OPEN/CLOSED/SL_HIT/TP_HIT, got {self.status!r}"
            )
        if self.sl_price is not None and self.sl_price <= 0:
            raise ValueError(f"sl_price must be > 0 or None, got {self.sl_price}")

    @property
    def is_open(self) -> bool:
        return self.status == "OPEN"

    @property
    def pnl_pct(self) -> Decimal:
        if self.entry_price == 0:
            return Decimal("0")
        if self.side == OrderSide.BUY:
            return (self.current_price - self.entry_price) / self.entry_price
        return (self.entry_price - self.current_price) / self.entry_price

    def is_sl_hit(self, price: Decimal) -> bool:
        if self.sl_price is None:
            return False
        if self.side == OrderSide.BUY:
            return price <= self.sl_price
        return price >= self.sl_price

    def compute_pnl_at(self, price: Decimal) -> Decimal:
        """Compute P&L if position were closed at `price`."""
        if self.side == OrderSide.BUY:
            return (price - self.entry_price) * self.units
        return (self.entry_price - price) * self.units

    def is_tp_hit(self, price: Decimal) -> bool:
        if self.tp_price is None:
            return False
        if self.side == OrderSide.BUY:
            return price >= self.tp_price
        return price <= self.tp_price
