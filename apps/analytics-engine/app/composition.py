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
from .application.ports.ohlcv_source import OhlcvSource
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
from .application.ports.atr_calculator import AtrCalculator
from .application.ports.backtest_reporter import BacktestReporter, MetricsCalculator
from .application.ports.execution_logger import ExecutionLogger
from .application.ports.incident_reporter import IncidentReporter
from .application.ports.notifier import Notifier
from .application.ports.incident_repository import IncidentRepository
from .application.ports.position_repository import PositionRepository
from .application.use_cases.check_drawdown import CheckDrawdownUseCase
from .application.use_cases.compute_position_size import (
    ComputePositionSizeUseCase,
)
from .application.use_cases.execute_signal import ExecuteSignalUseCase
from .application.use_cases.execution_engine import ExecutionEngine
from .application.use_cases.list_incidents import ListIncidentsUseCase
from .application.use_cases.monitor_positions import MonitorPositionsUseCase
from .application.use_cases.notify_on_event import NotifyOnEventUseCase
from .application.use_cases.open_day import OpenDayUseCase
from .application.use_cases.place_order import PlaceOrderUseCase
from .application.use_cases.predict_signal import PredictSignalUseCase
from .application.use_cases.report_incident import ReportIncidentUseCase
from .application.use_cases.run_backtest import RunBacktestUseCase
from .application.use_cases.train_model import TrainModelUseCase
from .application.use_cases.trip_circuit_breaker import (
    TripCircuitBreakerUseCase,
)
from .domain.entities.circuit_breaker import CircuitBreaker
from .domain.entities.risk_calculator import RiskCalculator
from .domain.entities.signal_validator import SignalValidator
from .infrastructure.balance.ccxt_balance_provider import CcxtBalanceProvider
from .infrastructure.balance.mock_balance_provider import MockBalanceProvider
from .infrastructure.env_mode.file_env_mode_writer import (
    FileEnvironmentModeWriter,
)
from .infrastructure.exchange.ccxt_order_client import CcxtOrderClient
from .infrastructure.trading.ccxt_binance_adapter import (
    CcxtBinanceTestnetAdapter,
)
from .domain.value_objects.atr import Atr
from .infrastructure.indicators.ta_atr_calculator import TaAtrCalculator
from .infrastructure.backtest.file_reporter import FileBacktestReporter
from .infrastructure.backtest.metrics_calculator import SimpleMetricsCalculator
from .infrastructure.execution.in_memory_position_repo import InMemoryPositionRepository
from .infrastructure.execution.structlog_execution_logger import StructlogExecutionLogger
from .infrastructure.journal.in_memory_snapshot_repo import InMemorySnapshotRepo
from .infrastructure.journal.in_memory_trade_journal import InMemoryTradeJournal
from .infrastructure.market.ccxt_min_lot_provider import CcxtMinLotProvider
from .infrastructure.monitoring.in_memory_incident_repo import (
    InMemoryIncidentRepository,
)
from .infrastructure.monitoring.logging_incident_reporter import (
    LoggingIncidentReporter,
)
from .infrastructure.notification.composite_notifier import (
    CompositeNotifier,
)
from .infrastructure.notification.logging_notifier import LoggingNotifier
from .infrastructure.ohlcv.ccxt_ohlcv_source import ccxt_ohlcv_source
from .infrastructure.strategies.registry import StrategyDictRegistry

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
    place_order: PlaceOrderUseCase
    report_incident: ReportIncidentUseCase
    list_incidents: ListIncidentsUseCase
    trip_circuit_breaker: TripCircuitBreakerUseCase
    incident_repo: IncidentRepository
    incident_reporter: IncidentReporter
    trade_journal: TradeJournal
    snapshot_repo: DrawdownSnapshotRepo
    env_writer: EnvironmentModeWriter
    circuit_breaker: CircuitBreaker
    exchange: ccxt.Exchange | None
    mode: str
    notifier: Notifier
    notify_on_event: NotifyOnEventUseCase


def _env_mode() -> str:
    return os.environ.get("ENVIRONMENT_MODE", "PAPER_TRADING").upper()


def _is_testnet() -> bool:
    return os.environ.get("BINANCE_TESTNET", "false").lower() == "true"


def _build_order_client(exchange: ccxt.Exchange) -> ExchangeOrderClient:
    """Return the appropriate order client based on testnet mode.

    In testnet mode, uses CcxtBinanceTestnetAdapter (Spot).
    Otherwise uses CcxtOrderClient (futures)."""
    if _is_testnet():
        return CcxtBinanceTestnetAdapter(exchange=exchange)
    return CcxtOrderClient(exchange=exchange)


def _build_exchange() -> ccxt.Exchange:
    """Build a single CCXT exchange instance for the engine.

    The exchange id is read from `EXCHANGE_ID` (default: binanceusdm
    for USDT-margined perpetuals). Credentials are pulled from env vars;
    the constructor raises if they're missing in LIVE mode.

    When BINANCE_TESTNET=true, creates a Binance Spot exchange with
    sandbox mode enabled, reading BINANCE_TESTNET_API_KEY / _SECRET.
    """
    if _is_testnet():
        api_key = os.environ["BINANCE_TESTNET_API_KEY"]
        api_secret = os.environ["BINANCE_TESTNET_SECRET"]
        ex: ccxt.Exchange = getattr(ccxt, "binance")({
            "apiKey": api_key,
            "secret": api_secret,
            "enableRateLimit": True,
        })
        ex.set_sandbox_mode(True)
        return ex

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
        order_client = _build_order_client(exchange)

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

    async def close_position(self, symbol: str) -> Any:
        from .application.ports.exchange_order_client import PositionSummary
        return PositionSummary(
            symbol=symbol, side="long", quantity=Decimal("0"),
            entry_price=Decimal("0"),
        )

    async def place_composite_order(
        self, order: Any
    ) -> Any:
        from .domain.value_objects.order import OrderResult, OrderStatus, OrderType
        return OrderResult(
            id="noop-1",
            symbol=order.symbol,
            side=order.side,
            type=OrderType.MARKET,
            filled_amount=order.entry_amount,
            status=OrderStatus.FILLED,
        )

    async def place_emergency_market(
        self, symbol: str, side: Any, amount: Any
    ) -> Any:
        from .domain.value_objects.order import OrderResult, OrderStatus, OrderType
        return OrderResult(
            id="noop-emergency-1",
            symbol=symbol,
            side=side,
            type=OrderType.MARKET,
            filled_amount=amount,
            status=OrderStatus.FILLED,
        )


def build_composition() -> Composition:
    """Construct the engine's composition for the current mode."""
    mode = _env_mode()
    log.info("composition_mode", mode=mode)

    # H5: preflight check aborts LIVE mode if secrets are missing.
    from .preflight import abort_if_missing
    abort_if_missing(mode)

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

    # H4 wiring — PlaceOrderUseCase
    if mode == "BACKTESTING":
        order_client_for_placement: ExchangeOrderClient = _NoopOrderClient()
    else:
        if exchange is None:
            raise RuntimeError("exchange is None in non-BACKTESTING mode")
        order_client_for_placement = _build_order_client(exchange)
    place_order_uc = PlaceOrderUseCase(
        order_client=order_client_for_placement
    )

    # H4-B wiring — Incident monitoring
    incident_repo: IncidentRepository = InMemoryIncidentRepository()
    incident_reporter: IncidentReporter = LoggingIncidentReporter()
    report_incident_uc = ReportIncidentUseCase(
        reporter=incident_reporter, repo=incident_repo
    )
    list_incidents_uc = ListIncidentsUseCase(repo=incident_repo)

    # H6 wiring — Notifications (publish events to Redis stream)
    if mode == "BACKTESTING":
        notifier: Notifier = LoggingNotifier()
    else:
        from .infrastructure.notification.redis_notifier import RedisNotifier
        channels: list[Notifier] = [LoggingNotifier()]
        redis_url = os.environ.get("ARGOS_BROKER_URL", "redis://localhost:6379")
        channels.append(RedisNotifier(redis_url=redis_url))
        notifier = CompositeNotifier(channels)
    notify_on_event_uc = NotifyOnEventUseCase(notifier=notifier)

    return Composition(
        compute_position_size=compute_position_size,
        check_drawdown=check,
        open_day=open_day,
        place_order=place_order_uc,
        report_incident=report_incident_uc,
        list_incidents=list_incidents_uc,
        trip_circuit_breaker=trip,
        incident_repo=incident_repo,
        incident_reporter=incident_reporter,
        trade_journal=trade_journal,
        snapshot_repo=snapshot_repo,
        env_writer=env_writer,
        circuit_breaker=circuit_breaker,
        exchange=exchange,
        mode=mode,
        notifier=notifier,
        notify_on_event=notify_on_event_uc,
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


def get_place_order_usecase(request: Request) -> PlaceOrderUseCase:
    return _comp(request).place_order


def get_report_incident_usecase(
    request: Request,
) -> ReportIncidentUseCase:
    return _comp(request).report_incident


def get_list_incidents_usecase(
    request: Request,
) -> ListIncidentsUseCase:
    return _comp(request).list_incidents


def get_notify_on_event_usecase(
    request: Request,
) -> NotifyOnEventUseCase:
    return _comp(request).notify_on_event


# H8 — Backtest use cases (cached in app.state) --------------------------------


def get_backtest_usecase(request: Request) -> RunBacktestUseCase:
    """Return the RunBacktestUseCase, cached in app.state."""
    cached: RunBacktestUseCase | None = getattr(request.app.state, "backtest_usecase", None)
    if cached is not None:
        return cached

    comp = _comp(request)

    if comp.mode == "BACKTESTING":
        ohlcv_source: OhlcvSource = _FakeOhlcvSource()  # type: ignore[arg-type]
    else:
        exchange = comp.exchange
        if exchange is None:
            raise RuntimeError("exchange is None in non-BACKTESTING mode")
        ohlcv_source = _CcxtOhlcvAdapter(exchange)

    registry = StrategyDictRegistry()
    metrics_calc = SimpleMetricsCalculator()
    reporter: BacktestReporter = FileBacktestReporter()

    use_case = RunBacktestUseCase(
        ohlcv_source=ohlcv_source,
        strategy_registry=registry,
        metrics_calculator=metrics_calc,
        reporter=reporter,
    )
    request.app.state.backtest_usecase = use_case
    request.app.state.backtest_registry = registry
    return use_case


def get_backtest_registry(request: Request) -> StrategyDictRegistry:
    """Return the singleton strategy registry."""
    cached: StrategyDictRegistry | None = getattr(request.app.state, "backtest_registry", None)
    if cached is not None:
        return cached
    get_backtest_usecase(request)
    cached = getattr(request.app.state, "backtest_registry", None)
    assert cached is not None
    return cached


# H6 — NovaQuant model use cases (built on demand, cached in app.state) -------

@dataclass
class _ModelUseCases:
    train: TrainModelUseCase
    predict: PredictSignalUseCase


async def get_model_use_cases(request: Request) -> _ModelUseCases:
    """Return the NovaQuant model use cases.

    Built once and cached in `app.state.model_use_cases`. Uses either
    PyTorch (USE_PYTORCH=true) or TensorFlow/Keras (default).

    For PyTorch mode:
      - Expects model files in models/best_argos_lstm.pt and
        models/scaler_argos.pkl, OR a checkpoint in the
        FsCheckpointRepository.
      - The model is loaded once at first call and cached.
    """
    cached: _ModelUseCases | None = getattr(request.app.state, "model_use_cases", None)
    if cached is not None:
        return cached

    comp = _comp(request)
    use_pytorch = os.environ.get("USE_PYTORCH", "false").lower() == "true"

    # OHLCV source for training — uses the same exchange as the rest
    if comp.mode == "BACKTESTING":
        ohlcv_source: Any = _FakeOhlcvSource()
    else:
        exchange = comp.exchange
        if exchange is None:
            raise RuntimeError("exchange is None in non-BACKTESTING mode")
        ohlcv_source = _CcxtOhlcvAdapter(exchange)

    # NovaQuant adapters
    from .infrastructure.training.data_preprocessor import TaDataPreprocessor
    from .infrastructure.training.feature_analyzer_impl import CorrelationFeatureAnalyzer
    from .infrastructure.models.checkpoint_repo_fs import FsCheckpointRepository

    preprocessor = TaDataPreprocessor()
    analyzer = CorrelationFeatureAnalyzer()
    repo = FsCheckpointRepository()

    if use_pytorch:
        from .infrastructure.models.nova_quant_pytorch import NovaQuantPyTorchModel
        predictor = NovaQuantPyTorchModel()
        await _load_pytorch_checkpoint(predictor, repo)
        train_uc = TrainModelUseCase(
            ohlcv_source=ohlcv_source,
            preprocessor=preprocessor,
            analyzer=analyzer,
            trainer=predictor,
            repo=repo,
        )
        predict_uc = PredictSignalUseCase(
            ohlcv_source=ohlcv_source,
            preprocessor=preprocessor,
            predictor=predictor,
            repo=repo,
        )
    else:
        from .infrastructure.models.nova_quant_keras import NovaQuantKerasModel
        keras_model = NovaQuantKerasModel()
        train_uc = TrainModelUseCase(
            ohlcv_source=ohlcv_source,
            preprocessor=preprocessor,
            analyzer=analyzer,
            trainer=keras_model,
            repo=repo,
        )
        predict_uc = PredictSignalUseCase(
            ohlcv_source=ohlcv_source,
            preprocessor=preprocessor,
            predictor=keras_model,
            repo=repo,
        )

    use_cases = _ModelUseCases(train=train_uc, predict=predict_uc)
    request.app.state.model_use_cases = use_cases
    return use_cases


async def _load_pytorch_checkpoint(
    model: Any,
    repo: Any,
) -> None:
    """Carga pesos PyTorch desde checkpoint repo o archivos raw.

    Prioridad:
      1. Checkpoint repo (load_latest)
      2. Archivos .pt + .pkl en models/ (fallback para import reciente)
    """
    from pathlib import Path

    pt_path = Path("models/best_argos_lstm.pt")
    scaler_path = Path("models/scaler_argos.pkl")

    # Intentar checkpoint repo primero
    try:
        domain_model, weights_bytes = await repo.load_latest()
        scaler_bytes = _load_scaler_from_repo(repo, domain_model)
        model.load_weights_from_bytes(
            pt_bytes=weights_bytes,
            n_features=len(domain_model.config.features),
            config=domain_model.config,
            scaler_bytes=scaler_bytes,
        )
        log.info("pytorch_model_loaded_from_checkpoint",
                 version=domain_model.model_version)
        return
    except Exception:
        log.info("pytorch_checkpoint_not_found_trying_files")

    # Fallback: archivos raw (modelos recien importados de Colab)
    if pt_path.exists():
        model.load_checkpoint(pt_path, scaler_path if scaler_path.exists() else None)
        log.info("pytorch_model_loaded_from_files",
                 pt=str(pt_path), scaler=str(scaler_path) if scaler_path.exists() else None)
        return

    log.warning("pytorch_model_not_loaded",
                hint="place best_argos_lstm.pt in models/ or use import script")


def _load_scaler_from_repo(repo: Any, domain_model: Any) -> bytes | None:
    """Intenta cargar scaler desde el directorio del checkpoint."""
    from pathlib import Path
    version = domain_model.model_version
    scaler_path = repo.base_dir / version / "scaler.pkl"
    if scaler_path.exists():
        return scaler_path.read_bytes()
    return None


class _CcxtOhlcvAdapter:
    """Adapta ccxt_ohlcv_source (funcion que retorna DataFrame) al port OhlcvSource."""

    def __init__(self, exchange: ccxt.Exchange) -> None:
        self._exchange = exchange

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1h",
        limit: int = 1000,
        since: int | None = None,
    ) -> list[dict]:
        df = await ccxt_ohlcv_source(self._exchange, symbol, timeframe, limit)
        return df.to_dict("records")


# H7 — Live Execution Engine (cached in app.state) ----------------------------


def get_execute_signal_usecase(request: Request) -> ExecuteSignalUseCase:
    """Return the ExecuteSignalUseCase, cached in app.state."""
    cached: ExecuteSignalUseCase | None = getattr(
        request.app.state, "execute_signal_usecase", None
    )
    if cached is not None:
        return cached

    comp = _comp(request)

    validator = SignalValidator()

    if comp.mode == "BACKTESTING":
        balance_provider: BalanceProvider = MockBalanceProvider(Decimal("10000"))
        atr_calc: AtrCalculator = _FakeAtrCalculator()
    else:
        balance_provider = CcxtBalanceProvider(exchange=comp.exchange)
        atr_calc = TaAtrCalculator(
            source=lambda s, t, w: ccxt_ohlcv_source(comp.exchange, s, t, w)
        )

    import asyncio

    if comp.mode == "BACKTESTING":
        exchange_client: ExchangeOrderClient = _NoopOrderClient()
        async def _not_halted() -> bool:
            return False
        drawdown_checker = _not_halted
    else:
        exchange_client = _build_order_client(comp.exchange)
        async def _check_halted() -> bool:
            return comp.check_drawdown.is_halted()
        drawdown_checker = _check_halted

    position_repo = get_position_repo(request)
    execution_logger = StructlogExecutionLogger()

    use_case = ExecuteSignalUseCase(
        signal_validator=validator,
        balance_provider=balance_provider,
        atr_calculator=atr_calc,
        exchange_client=exchange_client,
        position_repo=position_repo,
        execution_logger=execution_logger,
        is_halted=drawdown_checker,
    )
    request.app.state.execute_signal_usecase = use_case
    return use_case


def get_execution_engine_usecase(request: Request) -> ExecutionEngine:
    """Return the ExecutionEngine (Signal→Risk→Portfolio→Execute), cached."""
    cached: ExecutionEngine | None = getattr(
        request.app.state, "execution_engine_usecase", None
    )
    if cached is not None:
        return cached

    comp = _comp(request)

    from .domain.entities.risk_engine import RiskEngine
    from .domain.entities.portfolio_manager import PortfolioManager
    from .domain.entities.position_manager import PositionManager

    validator = SignalValidator()

    if comp.mode == "BACKTESTING":
        balance_provider: BalanceProvider = MockBalanceProvider(Decimal("10000"))
        atr_calc: AtrCalculator = _FakeAtrCalculator()
    else:
        balance_provider = CcxtBalanceProvider(exchange=comp.exchange)
        atr_calc = TaAtrCalculator(
            source=lambda s, t, w: ccxt_ohlcv_source(comp.exchange, s, t, w)
        )

    if comp.mode == "BACKTESTING":
        exchange_client: ExchangeOrderClient = _NoopOrderClient()
        async def _ee_not_halted() -> bool:
            return False
        drawdown_checker = _ee_not_halted
    else:
        exchange_client = _build_order_client(comp.exchange)
        async def _ee_check_halted() -> bool:
            return comp.check_drawdown.is_halted()
        drawdown_checker = _ee_check_halted

    position_repo = get_position_repo(request)
    execution_logger = StructlogExecutionLogger()

    engine = ExecutionEngine(
        signal_validator=validator,
        balance_provider=balance_provider,
        atr_calculator=atr_calc,
        exchange_client=exchange_client,
        position_repo=position_repo,
        execution_logger=execution_logger,
        is_halted=drawdown_checker,
        risk_engine=RiskEngine(),
        portfolio_manager=PortfolioManager(),
        position_manager=PositionManager(),
    )
    request.app.state.execution_engine_usecase = engine
    return engine


def get_monitor_positions_usecase(request: Request) -> MonitorPositionsUseCase:
    """Return the MonitorPositionsUseCase, cached in app.state."""
    cached: MonitorPositionsUseCase | None = getattr(
        request.app.state, "monitor_positions_usecase", None
    )
    if cached is not None:
        return cached

    position_repo = get_position_repo(request)
    execution_logger = StructlogExecutionLogger()

    comp = _comp(request)
    if comp.mode == "BACKTESTING":
        exchange_client: ExchangeOrderClient = _NoopOrderClient()
    else:
        exchange_client = _build_order_client(comp.exchange)

    if _is_testnet() and hasattr(exchange_client, "get_price"):
        price_provider = exchange_client.get_price  # type: ignore[union-attr]
    else:
        async def _fake_price(symbol: str) -> Decimal:
            return Decimal("0")
        price_provider = _fake_price

    use_case = MonitorPositionsUseCase(
        position_repo=position_repo,
        exchange_client=exchange_client,
        execution_logger=execution_logger,
        price_provider=price_provider,
    )
    request.app.state.monitor_positions_usecase = use_case
    return use_case


def get_position_repo(request: Request) -> PositionRepository:
    """Return the PositionRepository, cached in app.state."""
    cached: PositionRepository | None = getattr(
        request.app.state, "position_repo", None
    )
    if cached is not None:
        return cached

    repo = InMemoryPositionRepository()
    request.app.state.position_repo = repo
    return repo


class _FakeAtrCalculator(AtrCalculator):
    """Fixed ATR for BACKTESTING mode."""
    async def get_atr(
        self, symbol: str, timeframe: str = "1m", window: int = 14
    ) -> Atr:
        return Atr(500)


class _FakeOhlcvSource:
    """OHLCV source for BACKTESTING: returns empty list."""

    async def fetch_ohlcv(
        self, symbol: str, timeframe: str = "1h", limit: int = 1000, since: int | None = None
    ) -> list[dict]:
        return []
