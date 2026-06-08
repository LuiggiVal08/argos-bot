"""Unit tests for H3 application use cases.

Each use case is exercised against in-memory adapters (no
network, no filesystem). The trip use case is tested with a
fake order client + a temp-dir FileEnvironmentModeWriter so
the file write is observable.
"""
from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.application.ports.balance_provider import (
    BalanceProvider,
    BalanceProviderError,
)
from app.application.ports.drawdown_snapshot_repo import (
    DrawdownSnapshotRepo,
)
from app.application.ports.environment_mode_writer import (
    EnvironmentMode,
    EnvironmentModeError,
    EnvironmentModeWriter,
)
from app.application.ports.exchange_order_client import (
    ExchangeOrderClient,
    ExchangeOrderClientError,
    PositionSummary,
)
from app.application.ports.trade_journal import (
    TradeJournal,
    TradeJournalError,
    TradeRecord,
)
from app.application.use_cases.check_drawdown import (
    CheckDrawdownError,
    CheckDrawdownUseCase,
)
from app.application.use_cases.open_day import OpenDayError, OpenDayUseCase
from app.application.use_cases.trip_circuit_breaker import (
    TripCircuitBreakerError,
    TripCircuitBreakerUseCase,
)
from app.domain.entities.circuit_breaker import CircuitBreaker
from app.domain.value_objects.drawdown_snapshot import DrawdownSnapshot
from app.domain.value_objects.drawdown_state import DrawdownState
from app.domain.value_objects.trip_action import TripAction, TripStep
from app.infrastructure.env_mode.file_env_mode_writer import (
    FileEnvironmentModeWriter,
)
from app.infrastructure.journal.in_memory_snapshot_repo import InMemorySnapshotRepo
from app.infrastructure.journal.in_memory_trade_journal import InMemoryTradeJournal


# --- Fakes ---


class FakeBalanceProvider(BalanceProvider):
    def __init__(self, balance: Decimal | Exception) -> None:
        self._balance = balance

    async def get_free_balance(self) -> Decimal:
        if isinstance(self._balance, Exception):
            raise self._balance
        return self._balance


class FakeOrderClient(ExchangeOrderClient):
    def __init__(
        self,
        cancel_count: int = 2,
        positions_to_close: list[PositionSummary] | Exception = None,
        cancel_raises: Exception | None = None,
    ) -> None:
        self._cancel = cancel_count
        self._positions = positions_to_close or []
        self._cancel_raises = cancel_raises
        self.cancel_called = 0
        self.close_called = 0

    async def cancel_all_orders(self) -> int:
        self.cancel_called += 1
        if self._cancel_raises is not None:
            raise self._cancel_raises
        return self._cancel

    async def close_all_positions(self) -> list[PositionSummary]:
        self.close_called += 1
        if isinstance(self._positions, Exception):
            raise self._positions
        return list(self._positions)


class FailingEnvWriter(EnvironmentModeWriter):
    async def write(self, mode: EnvironmentMode) -> None:
        raise EnvironmentModeError("disk full")

    async def read(self) -> EnvironmentMode:
        return EnvironmentMode.PAPER_TRADING


class TmpFileEnvWriter(FileEnvironmentModeWriter):
    """FileEnvironmentModeWriter bound to a tmp file path. Has
    a `cleanup()` helper for test teardown."""

    def __init__(self) -> None:
        fd, self._tmp_path = tempfile.mkstemp(prefix="env_mode_", suffix=".json")
        os.close(fd)
        super().__init__(path=self._tmp_path)
        self.tmp_path = self._tmp_path

    def cleanup(self) -> None:
        if os.path.exists(self.tmp_path):
            os.unlink(self.tmp_path)


# --- OpenDayUseCase ---


class TestOpenDayUseCase:
    async def test_happy_path(self) -> None:
        repo = InMemorySnapshotRepo()
        use_case = OpenDayUseCase(
            balance_provider=FakeBalanceProvider(Decimal("10000")),
            snapshot_repo=repo,
        )
        snap = await use_case.execute()
        assert snap.starting_balance == Decimal("10000")
        loaded = await repo.load()
        assert loaded is not None
        assert loaded.starting_balance == Decimal("10000")

    async def test_refuses_to_overwrite_without_force(self) -> None:
        repo = InMemorySnapshotRepo()
        await repo.save(DrawdownSnapshot.at_open(Decimal("10000")))
        use_case = OpenDayUseCase(
            balance_provider=FakeBalanceProvider(Decimal("20000")),
            snapshot_repo=repo,
        )
        with pytest.raises(OpenDayError, match="snapshot_exists"):
            await use_case.execute()

    async def test_force_overwrites(self) -> None:
        repo = InMemorySnapshotRepo()
        await repo.save(DrawdownSnapshot.at_open(Decimal("10000")))
        use_case = OpenDayUseCase(
            balance_provider=FakeBalanceProvider(Decimal("20000")),
            snapshot_repo=repo,
        )
        snap = await use_case.execute(force=True)
        assert snap.starting_balance == Decimal("20000")

    async def test_balance_error_propagates(self) -> None:
        repo = InMemorySnapshotRepo()
        use_case = OpenDayUseCase(
            balance_provider=FakeBalanceProvider(
                BalanceProviderError("ccxt timeout")
            ),
            snapshot_repo=repo,
        )
        with pytest.raises(OpenDayError, match="balance_unavailable"):
            await use_case.execute()


# --- CheckDrawdownUseCase ---


class TestCheckDrawdownUseCase:
    async def _opened(self, balance: Decimal = Decimal("10000")) -> InMemorySnapshotRepo:
        repo = InMemorySnapshotRepo()
        await repo.save(DrawdownSnapshot.at_open(balance))
        return repo

    async def test_safe(self) -> None:
        repo = await self._opened()
        journal = InMemoryTradeJournal()
        cb = CircuitBreaker()
        use_case = CheckDrawdownUseCase(
            circuit_breaker=cb, snapshot_repo=repo, trade_journal=journal
        )
        result = await use_case.execute()
        assert result.state is DrawdownState.SAFE
        assert result.intraday_pnl == Decimal("0")
        assert result.trip_action is None

    async def test_trip_dispatches_handler(self) -> None:
        repo = await self._opened()
        # Realise a 6% loss by adding -600 to the journal.
        journal = InMemoryTradeJournal()
        await journal.add(
            TradeRecord(
                symbol="BTC/USDT",
                realized_pnl=Decimal("-600"),
                closed_at=datetime.now(tz=timezone.utc),
                reference="t-1",
            )
        )
        cb = CircuitBreaker()
        trip_called: list[DrawdownSnapshot] = []
        trip = TripCircuitBreakerUseCase(
            order_client=FakeOrderClient(cancel_count=1, positions_to_close=[]),
            env_writer=TmpFileEnvWriter(),
            snapshot_repo=repo,
        )

        async def on_trip(_r) -> None:
            trip_called.append(_r.snapshot)
            await trip.execute()

        use_case = CheckDrawdownUseCase(
            circuit_breaker=cb,
            snapshot_repo=repo,
            trade_journal=journal,
            on_trip=on_trip,
        )
        result = await use_case.execute()
        assert result.state is DrawdownState.TRIP
        assert result.trip_action is not None
        assert result.trip_action.steps[0] is TripStep.CANCEL_ORDERS
        assert len(trip_called) == 1

    async def test_missing_snapshot_raises(self) -> None:
        repo = InMemorySnapshotRepo()
        use_case = CheckDrawdownUseCase(
            circuit_breaker=CircuitBreaker(),
            snapshot_repo=repo,
            trade_journal=InMemoryTradeJournal(),
        )
        with pytest.raises(CheckDrawdownError, match="snapshot_missing"):
            await use_case.execute()

    async def test_journal_error_propagates(self) -> None:
        repo = await self._opened()

        class FailingJournal(TradeJournal):
            async def add(self, record: TradeRecord) -> None: ...
            async def realized_pnl_since(self, since_utc):
                raise TradeJournalError("disk full")

        use_case = CheckDrawdownUseCase(
            circuit_breaker=CircuitBreaker(),
            snapshot_repo=repo,
            trade_journal=FailingJournal(),
        )
        with pytest.raises(CheckDrawdownError, match="journal_unavailable"):
            await use_case.execute()

    async def test_load_current_snapshot_no_trip(self) -> None:
        repo = await self._opened()
        trip_called = False

        async def on_trip(_r) -> None:
            nonlocal trip_called
            trip_called = True

        use_case = CheckDrawdownUseCase(
            circuit_breaker=CircuitBreaker(),
            snapshot_repo=repo,
            trade_journal=InMemoryTradeJournal(),
            on_trip=on_trip,
        )
        snap = await use_case.load_current_snapshot()
        assert snap is not None
        assert snap.starting_balance == Decimal("10000")
        # The trip must NOT fire on a load-only call.
        assert not trip_called


# --- TripCircuitBreakerUseCase ---


class TestTripCircuitBreakerUseCase:
    async def test_full_trip_happy_path(self) -> None:
        repo = InMemorySnapshotRepo()
        await repo.save(DrawdownSnapshot.at_open(Decimal("10000")))
        env = TmpFileEnvWriter()
        try:
            order_client = FakeOrderClient(
                cancel_count=3,
                positions_to_close=[
                    PositionSummary(
                        symbol="BTC/USDT",
                        side="long",
                        quantity=Decimal("0.1"),
                        entry_price=Decimal("60000"),
                    )
                ],
            )
            use_case = TripCircuitBreakerUseCase(
                order_client=order_client, env_writer=env, snapshot_repo=repo
            )
            result = await use_case.execute()
            assert result.fully_succeeded
            assert result.orders_cancelled == 3
            assert len(result.positions_closed) == 1
            assert result.env_mode is EnvironmentMode.PASIVO
            # Snapshot was cleared.
            assert await repo.load() is None
            # File was written.
            mode_read = await env.read()
            assert mode_read is EnvironmentMode.PASIVO
        finally:
            env.cleanup()

    async def test_trip_order_matters(self) -> None:
        """The four steps must execute in the canonical order: cancel,
        close, set PASIVO, halt (clear snapshot)."""
        calls: list[str] = []

        class RecordingOrder(ExchangeOrderClient):
            async def cancel_all_orders(self) -> int:
                calls.append("cancel")
                return 0

            async def close_all_positions(self) -> list[PositionSummary]:
                calls.append("close")
                return []

        class RecordingEnv(EnvironmentModeWriter):
            async def write(self, mode: EnvironmentMode) -> None:
                calls.append(f"env:{mode.value}")

            async def read(self) -> EnvironmentMode:
                return EnvironmentMode.PAPER_TRADING

        class RecordingRepo(DrawdownSnapshotRepo):
            async def save(self, snapshot: DrawdownSnapshot) -> None: ...
            async def load(self) -> DrawdownSnapshot | None:
                return None
            async def clear(self) -> None:
                calls.append("clear")

        use_case = TripCircuitBreakerUseCase(
            order_client=RecordingOrder(),
            env_writer=RecordingEnv(),
            snapshot_repo=RecordingRepo(),
        )
        await use_case.execute()
        assert calls == ["cancel", "close", "env:PASIVO", "clear"]

    async def test_cancel_failure_raises_incomplete(self) -> None:
        repo = InMemorySnapshotRepo()
        await repo.save(DrawdownSnapshot.at_open(Decimal("10000")))
        env = TmpFileEnvWriter()
        try:
            use_case = TripCircuitBreakerUseCase(
                order_client=FakeOrderClient(
                    cancel_raises=ExchangeOrderClientError("auth expired")
                ),
                env_writer=env,
                snapshot_repo=repo,
            )
            with pytest.raises(TripCircuitBreakerError, match="trip_incomplete"):
                await use_case.execute()
        finally:
            env.cleanup()

    async def test_env_write_failure_raises_incomplete(self) -> None:
        repo = InMemorySnapshotRepo()
        await repo.save(DrawdownSnapshot.at_open(Decimal("10000")))
        use_case = TripCircuitBreakerUseCase(
            order_client=FakeOrderClient(),
            env_writer=FailingEnvWriter(),
            snapshot_repo=repo,
        )
        with pytest.raises(TripCircuitBreakerError, match="trip_incomplete"):
            await use_case.execute()
