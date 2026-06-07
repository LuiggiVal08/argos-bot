"""Composition root: wires concrete adapters to the application ports.

This is the only place in the analytics-engine where infrastructure
imports meet application. It selects adapters based on
ENVIRONMENT_MODE:
  - BACKTESTING: in-memory journal + snapshot, no exchange, file
    env-mode writer, no order client.
  - PAPER_TRADING / LIVE: CCXT order client + balance provider,
    file env-mode writer.

The composition is built once at app startup and stored in
`app.state.composition`. FastAPI dependencies fetch it from there
via the `get_*_usecase` helpers in this module.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Awaitable, Callable

import ccxt.async_support as ccxt
import structlog

from fastapi import Request

from .application.ports.min_lot_provider import (
    MarketConstraints,
    MinLotProvider,
)
from .application.ports.trade_journal import (
    TradeJournal,
)
from .application.ports.exchange_order_client import (
    ExchangeOrderClient,
)
from .application.ports.environment_mode_writer import (
    EnvironmentModeWriter,
)
from .application.ports.drawdown_snapshot_repo import (
    DrawdownSnapshotRepo,
)
from .application.use_cases.check_drawdown import CheckDrawdownUseCase
from .application.use_cases.compute_position_size import (
    ComputePositionSizeUseCase,
)
from .application.use_cases.open_day import OpenDayUseCase
from .application.use_cases.trip_circuit_breaker import (
    TripCircuitBreakerUseCase,
)
from .domain.entities.circuit_breaker import CircuitBreaker
from .domain.entities.risk_calculator import RiskCalculator
from .infrastructure.balance.ccxt_balance_provider import CcxtBalanceProvider
from .infrastructure.balance.mock_balance_provider import MockBalanceProvider
from .infrastructure.env_mode.file_env_mode_writer import (
    FileEnvironmentModeWriter,
)
from .infrastructure.exchange.ccxt_order_client import CcxtOrderClient
from .infrastructure.indicators.ta_atr_calculator import TaAtrCalculator
from .infrastructure.journal.in_memory_snapshot_repo import InMemorySnapshotRepo
from .infrastructure.journal.in_memory_trade_journal import InMemoryTradeJournal
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
    check_drawdown: CheckDrawdownUseCase
    open_day: OpenDayUseCase
    trip_circuit_breaker: TripCircuitBreakerUseCase
    trade_journal: TradeJournal
    snapshot_repo: DrawdownSnapshotRepo
    env_writer: EnvironmentModeWriter
    circuit_breaker: CircuitBreaker
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


def _build_h2(mode: str, exchange: ccxt.Exchange | None) -> ComputePositionSizeUseCase:
    risk_calculator = RiskCalculator()
    if mode == "BACKTESTING":
        balance: Any = MockBalanceProvider(Decimal("10000"))
        atr_calc = TaAtrCalculator(source=_dummy_ohlcv_source)
        return ComputePositionSizeUseCase(
            risk_calculator=risk_calculator,
            balance_provider=balance,
            atr_calculator=atr_calc,
            min_lot_provider=_StaticMinLot(),
        )
    if exchange is None:
        raise RuntimeError("exchange is None in non-BACKTESTING mode")
    balance = CcxtBalanceProvider(exchange)
    atr_calc = TaAtrCalculator(
        source=lambda s, t, w: ccxt_ohlcv_source(exchange, s, t, w)
    )
    min_lot = CcxtMinLotProvider(exchange)
    return ComputePositionSizeUseCase(
        risk_calculator=risk_calculator,
        balance_provider=balance,
        atr_calculator=atr_calc,
        min_lot_provider=min_lot,
    )


def _build_h3(
    mode: str,
    exchange: ccxt.Exchange | None,
    trade_journal: TradeJournal,
    snapshot_repo: DrawdownSnapshotRepo,
    env_writer: EnvironmentModeWriter,
) -> tuple[
    CircuitBreaker,
    OpenDayUseCase,
    TripCircuitBreakerUseCase,
    CheckDrawdownUseCase,
]:
    circuit_breaker = CircuitBreaker()

    # OpenDay re-uses the same balance provider logic as H2.
    if mode == "BACKTESTING":
        balance_provider: Any = MockBalanceProvider(Decimal("10000"))
    else:
        if exchange is None:
            raise RuntimeError("exchange is None in non-BACKTESTING mode")
        balance_provider = CcxtBalanceProvider(exchange)

    open_day = OpenDayUseCase(
        balance_provider=balance_provider, snapshot_repo=snapshot_repo
    )

    # Trip use case needs an ExchangeOrderClient only in PAPER/LIVE.
    if mode == "BACKTESTING":
        # In backtesting there are no live orders to cancel. The
        # trip just flips env mode and clears the snapshot.
        order_client: ExchangeOrderClient = _NoopOrderClient()
    else:
        if exchange is None:
            raise RuntimeError("exchange is None in non-BACKTESTING mode")
        order_client = CcxtOrderClient(exchange=exchange)

    trip = TripCircuitBreakerUseCase(
        order_client=order_client,
        env_writer=env_writer,
        snapshot_repo=snapshot_repo,
    )

    check = CheckDrawdownUseCase(
        circuit_breaker=circuit_breaker,
        snapshot_repo=snapshot_repo,
        trade_journal=trade_journal,
        on_trip=lambda _result: trip.execute(),
    )

    return circuit_breaker, open_day, trip, check


class _NoopOrderClient(ExchangeOrderClient):
    """For BACKTESTING: there are no live orders to cancel."""

    async def cancel_all_orders(self) -> int:
        return 0

    async def close_all_positions(self) -> list[Any]:
        return []


def build_composition() -> Composition:
    """Construct the engine's composition for the current mode."""
    mode = _env_mode()
    log.info("composition_mode", mode=mode)

    exchange: ccxt.Exchange | None = None
    if mode != "BACKTESTING":
        exchange = _build_exchange()

    compute_position_size = _build_h2(mode, exchange)

    # H3 wiring
    if mode == "BACKTESTING":
        trade_journal: TradeJournal = InMemoryTradeJournal()
        snapshot_repo: DrawdownSnapshotRepo = InMemorySnapshotRepo()
    else:
        # PAPER/LIVE use the same in-memory adapters for the journal
        # + snapshot (persistent stores are H3-FU1). The order
        # client and env-mode writer differ.
        trade_journal = InMemoryTradeJournal()
        snapshot_repo = InMemorySnapshotRepo()

    env_writer: EnvironmentModeWriter = FileEnvironmentModeWriter()
    (
        circuit_breaker,
        open_day,
        trip,
        check,
    ) = _build_h3(mode, exchange, trade_journal, snapshot_repo, env_writer)

    return Composition(
        compute_position_size=compute_position_size,
        check_drawdown=check,
        open_day=open_day,
        trip_circuit_breaker=trip,
        trade_journal=trade_journal,
        snapshot_repo=snapshot_repo,
        env_writer=env_writer,
        circuit_breaker=circuit_breaker,
        exchange=exchange,
        mode=mode,
    )


# FastAPI dependencies ---------------------------------------------------------
def _comp(request: Request) -> Composition:
    comp: Composition = request.app.state.composition
    return comp


def get_compute_position_size_usecase(
    request: Request,
) -> ComputePositionSizeUseCase:
    return _comp(request).compute_position_size


def get_check_drawdown_usecase(request: Request) -> CheckDrawdownUseCase:
    return _comp(request).check_drawdown


def get_open_day_usecase(request: Request) -> OpenDayUseCase:
    return _comp(request).open_day


def get_trip_circuit_breaker_usecase(
    request: Request,
) -> TripCircuitBreakerUseCase:
    return _comp(request).trip_circuit_breaker
