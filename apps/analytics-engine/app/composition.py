"""Composition root: wires concrete adapters to the application ports.

This is the only place in the analytics-engine where infrastructure
imports meet application. It selects adapters based on
ENVIRONMENT_MODE:
  - BACKTESTING: MockBalanceProvider (no network), TaAtrCalculator
    reading from a static local DataFrame, default market
    constraints (no min lot check).
  - PAPER_TRADING / LIVE: CcxtBalanceProvider, CcxtMinLotProvider,
    TaAtrCalculator reading from ccxt OHLCV.

The composition is built once at app startup and stored in
`app.state.composition`. FastAPI dependencies fetch it from there
via the `get_compute_position_size_usecase` helper in this module.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Awaitable, Callable

import ccxt.async_support as ccxt
import structlog

from .application.ports.min_lot_provider import (
    MarketConstraints,
    MinLotProvider,
)
from .application.use_cases.compute_position_size import (
    ComputePositionSizeUseCase,
)
from .domain.entities.risk_calculator import RiskCalculator
from .infrastructure.balance.ccxt_balance_provider import CcxtBalanceProvider
from .infrastructure.balance.mock_balance_provider import MockBalanceProvider
from .infrastructure.indicators.ta_atr_calculator import TaAtrCalculator
from .infrastructure.market.ccxt_min_lot_provider import CcxtMinLotProvider
from .infrastructure.ohlcv.ccxt_ohlcv_source import ccxt_ohlcv_source

if TYPE_CHECKING:
    import pandas as pd
    from fastapi import Request

log = structlog.get_logger()

OhlcvSource = Callable[[str, str, int], Awaitable["pd.DataFrame"]]


@dataclass
class Composition:
    compute_position_size: ComputePositionSizeUseCase
    exchange: ccxt.Exchange | None
    mode: str


def _env_mode() -> str:
    return os.environ.get("ENVIRONMENT_MODE", "PAPER_TRADING").upper()


def _build_exchange() -> ccxt.Exchange:
    """Build a single CCXT exchange instance for the engine.

    The exchange id is read from `EXCHANGE_ID` (default: binanceusdm
    for USDT-margined perpetuals, the canonical venue for H2 testing).
    Credentials are pulled from env vars; the constructor raises if
    they're missing in LIVE mode (see spec sad path).
    """
    ex_id = os.environ.get("EXCHANGE_ID", "binanceusdm")
    klass: Any = getattr(ccxt, ex_id, None)
    if klass is None:
        raise RuntimeError(
            f"unknown_exchange: {ex_id} not a valid ccxt exchange id"
        )
    api_key = os.environ.get("EXCHANGE_API_KEY")
    api_secret = os.environ.get("EXCHANGE_API_SECRET")
    return klass({
        "apiKey": api_key,
        "secret": api_secret,
        "enableRateLimit": True,
    })


async def _dummy_ohlcv_source(
    symbol: str, timeframe: str, window: int
) -> "pd.DataFrame":
    """Stand-in OHLCV source for BACKTESTING.

    Returns an empty DataFrame so TaAtrCalculator raises
    'insufficient_candles'. H2's BACKTESTING flow doesn't actually
    compute position size from ATR; that's a future history.
    """
    import pandas as pd
    return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])


class _StaticMinLot(MinLotProvider):
    """Min-lot provider for BACKTESTING: no min constraints."""

    async def get_constraints(self, symbol: str) -> MarketConstraints:
        return MarketConstraints(
            min_qty=0.0, qty_step=1e-8, min_notional=0.0
        )


def build_composition() -> Composition:
    """Construct the engine's composition for the current mode."""
    mode = _env_mode()
    risk_calculator = RiskCalculator()

    if mode == "BACKTESTING":
        log.info("composition_mode", mode=mode)
        balance: Any = MockBalanceProvider(Decimal("10000"))
        atr_calc = TaAtrCalculator(source=_dummy_ohlcv_source)
        return Composition(
            compute_position_size=ComputePositionSizeUseCase(
                risk_calculator=risk_calculator,
                balance_provider=balance,
                atr_calculator=atr_calc,
                min_lot_provider=_StaticMinLot(),
            ),
            exchange=None,
            mode=mode,
        )

    exchange = _build_exchange()
    balance = CcxtBalanceProvider(exchange)
    atr_calc = TaAtrCalculator(
        source=lambda s, t, w: ccxt_ohlcv_source(exchange, s, t, w)
    )
    min_lot = CcxtMinLotProvider(exchange)
    log.info("composition_mode", mode=mode, exchange=exchange.id)
    return Composition(
        compute_position_size=ComputePositionSizeUseCase(
            risk_calculator=risk_calculator,
            balance_provider=balance,
            atr_calculator=atr_calc,
            min_lot_provider=min_lot,
        ),
        exchange=exchange,
        mode=mode,
    )


# FastAPI dependency ---------------------------------------------------------
def get_compute_position_size_usecase(
    request: "Request",
) -> ComputePositionSizeUseCase:
    """FastAPI dependency that returns the singleton use case built
    by the composition root at app startup."""
    comp: Composition = request.app.state.composition
    return comp.compute_position_size
