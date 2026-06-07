"""ComputePositionSizeUseCase.

Orchestrates H2: given a trading signal, fetch the current free
balance (BalanceProvider) and ATR (AtrCalculator), invoke the
pure-domain RiskCalculator to compute the size, and verify the
result meets the exchange's minimum lot (MinLotProvider).

Sad path handling (per spec section 5 Historia 2):
  - BalanceProviderError (CCXT timeout, 5xx, auth, network) →
    `ComputePositionSizeError("balance_unavailable")` — the caller
    aborts the trade and logs a critical error.
  - AtrCalculatorError (insufficient candles, network) →
    `ComputePositionSizeError("atr_unavailable")` — same.
  - Calculated units < min_qty OR notional < min_notional →
    `PositionSizeBelowMinLotError` — the caller discards the
    signal with a warning log.

Happy path: returns a `PositionSizeResult` with the
PositionSize value object and the entry price used.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from ...domain.entities.risk_calculator import RiskCalculator
from ...domain.value_objects.position_size import PositionSize
from ...domain.value_objects.risk_pct import RiskPct
from ..ports.atr_calculator import AtrCalculator
from ..ports.balance_provider import BalanceProvider
from ..ports.min_lot_provider import MinLotProvider, MarketConstraints


class ComputePositionSizeError(RuntimeError):
    """Raised when a required input cannot be obtained (balance
    or ATR provider failure). The caller must abort the trade."""


class PositionSizeBelowMinLotError(RuntimeError):
    """Raised when the calculated units are below the exchange
    minimum lot. The caller discards the signal per spec."""


@dataclass(frozen=True)
class PositionSizeInput:
    """The use case's input contract."""
    symbol: str
    entry_price: Decimal
    risk_pct: RiskPct = RiskPct.default()
    timeframe: str = "1m"
    atr_window: int = 14


@dataclass(frozen=True)
class PositionSizeResult:
    """The use case's output contract on the happy path."""
    position: PositionSize
    constraints: MarketConstraints


class ComputePositionSizeUseCase:
    def __init__(
        self,
        risk_calculator: RiskCalculator,
        balance_provider: BalanceProvider,
        atr_calculator: AtrCalculator,
        min_lot_provider: MinLotProvider,
    ) -> None:
        self._calc = risk_calculator
        self._balances = balance_provider
        self._atrs = atr_calculator
        self._min_lots = min_lot_provider

    async def execute(self, inp: PositionSizeInput) -> PositionSizeResult:
        # 1. Fetch inputs. Any provider failure aborts the trade.
        try:
            free_balance = await self._balances.get_free_balance()
        except Exception as e:  # BalanceProviderError or any I/O
            raise ComputePositionSizeError(
                f"balance_unavailable: {e}"
            ) from e

        try:
            atr = await self._atrs.get_atr(
                inp.symbol, timeframe=inp.timeframe, window=inp.atr_window
            )
        except Exception as e:
            raise ComputePositionSizeError(f"atr_unavailable: {e}") from e

        # 2. Fetch market constraints (min lot, step, min notional).
        # Failure here is also fatal: without constraints we cannot
        # tell whether the signal is tradable.
        try:
            constraints = await self._min_lots.get_constraints(inp.symbol)
        except Exception as e:
            raise ComputePositionSizeError(
                f"min_lot_unavailable: {e}"
            ) from e

        # 3. Compute size (pure domain).
        position = self._calc.calculate(
            free_balance=free_balance,
            atr=atr,
            entry_price=inp.entry_price,
            risk_pct=inp.risk_pct,
        )

        # 4. Min-lot check (sad path from spec).
        if float(position.units) < constraints.min_qty:
            raise PositionSizeBelowMinLotError(
                f"computed units {position.units} below market min_qty "
                f"{constraints.min_qty} for {inp.symbol}"
            )
        if float(position.notional_value) < constraints.min_notional:
            raise PositionSizeBelowMinLotError(
                f"computed notional {position.notional_value} below market "
                f"min_notional {constraints.min_notional} for {inp.symbol}"
            )

        return PositionSizeResult(position=position, constraints=constraints)
