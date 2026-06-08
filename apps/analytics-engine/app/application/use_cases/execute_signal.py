"""ExecuteSignalUseCase — valida y ejecuta una señal de trading.

Pipeline:
  1. Validar señal (confidence, cooldown, dedup)
  2. Verificar Circuit Breaker (no HALTED)
  3. Obtener balance libre + ATR
  4. Calcular tamaño de posición
  5. Armar orden compuesta (entry + SL + TP)
  6. Colocar orden vía ExchangeOrderClient
  7. Persistir posición
  8. Loggear ejecución
  9. Retornar ExecutionReport
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Callable
from uuid import uuid4

from ...domain.entities.signal_validator import SignalValidator
from ...domain.value_objects.execution_report import ExecutionReport
from ...domain.value_objects.execution_signal import ExecutionSignal
from ...domain.value_objects.live_position import LivePosition
from ...domain.value_objects.order import CompositeOrder, OrderSide
from ..ports.atr_calculator import AtrCalculator
from ..ports.balance_provider import BalanceProvider
from ..ports.exchange_order_client import ExchangeOrderClient
from ..ports.execution_logger import ExecutionLogger
from ..ports.position_repository import PositionRepository

IsHaltedFn = Callable[[], bool]


class ExecuteSignalError(RuntimeError):
    """Raised when signal execution fails irrecoverably."""


@dataclass(frozen=True)
class ExecuteSignalResult:
    report: ExecutionReport
    position: LivePosition | None = None


class ExecuteSignalUseCase:
    """Orquesta la ejecución completa de una señal.

    Args:
        signal_validator:    Valida la señal entrante.
        balance_provider:    Provee el balance libre disponible.
        atr_calculator:      Calcula ATR para SL dinámico.
        exchange_client:     Coloca órdenes en el exchange.
        position_repo:       Persiste posiciones.
        execution_logger:    Registra eventos de ejecución.
        is_halted:           Callable que retorna True si el CB está
                             HALTED.
        risk_pct:            Fracción del balance a arriesgar (default 0.01).
        sl_atr_multiplier:   Multiplicador de ATR para SL (default 1.5).
        tp_atr_multiplier:   Multiplicador de ATR para TP (default 3.0).
    """

    def __init__(
        self,
        signal_validator: SignalValidator,
        balance_provider: BalanceProvider,
        atr_calculator: AtrCalculator,
        exchange_client: ExchangeOrderClient,
        position_repo: PositionRepository,
        execution_logger: ExecutionLogger,
        is_halted: IsHaltedFn,
        risk_pct: float = 0.01,
        sl_atr_multiplier: float = 1.5,
        tp_atr_multiplier: float = 3.0,
    ) -> None:
        self._validator = signal_validator
        self._balance_provider = balance_provider
        self._atr_calculator = atr_calculator
        self._exchange = exchange_client
        self._position_repo = position_repo
        self._logger = execution_logger
        self._is_halted = is_halted
        self._risk_pct = Decimal(str(risk_pct))
        self._sl_mult = Decimal(str(sl_atr_multiplier))
        self._tp_mult = Decimal(str(tp_atr_multiplier))

    async def execute(self, signal: ExecutionSignal) -> ExecuteSignalResult:
        # 1. Validar
        validation = self._validator.validate(signal)
        if not validation.valid:
            await self._logger.log_rejection(signal.signal_id, validation.message)
            raise ExecuteSignalError(
                f"signal {signal.signal_id} rejected: {validation.message}"
            )

        # 2. Circuit Breaker
        if await self._is_halted():
            msg = f"circuit breaker HALTED, rejecting signal {signal.signal_id}"
            await self._logger.log_rejection(signal.signal_id, msg)
            raise ExecuteSignalError(msg)

        # 3. Balance + ATR
        try:
            balance = await self._balance_provider.get_free_balance(signal.symbol)
            atr = await self._atr_calculator.calculate(signal.symbol)
        except Exception as e:
            raise ExecuteSignalError(
                f"failed to fetch market data: {e}"
            ) from e

        # 4. Tamaño de posición
        risk_amount = balance * self._risk_pct
        entry_price = signal.price or atr
        if entry_price <= 0:
            raise ExecuteSignalError("invalid entry_price <= 0")

        sl_distance = max(atr * self._sl_mult, entry_price * Decimal("0.005"))
        units = risk_amount / sl_distance
        if units <= 0:
            raise ExecuteSignalError("computed position size is zero")

        # 5. SL/TP prices
        side = OrderSide.BUY if signal.side.name == "BUY" else OrderSide.SELL
        if side == OrderSide.BUY:
            sl_price = entry_price - sl_distance
            tp_price = entry_price + (atr * self._tp_mult)
        else:
            sl_price = entry_price + sl_distance
            tp_price = entry_price - (atr * self._tp_mult)

        # 6. Place order
        order = CompositeOrder(
            symbol=signal.symbol,
            side=side,
            entry_amount=units,
            entry_price=entry_price,
            sl_price=max(sl_price, Decimal("0")),
            tp_price=max(tp_price, Decimal("0")),
        )
        try:
            order_result = await self._exchange.place_composite_order(order)
        except Exception as e:
            raise ExecuteSignalError(f"order placement failed: {e}") from e

        # 7. Persistir posición
        position = LivePosition(
            position_id=uuid4().hex[:12],
            symbol=signal.symbol,
            side=side,
            units=order_result.filled_amount,
            entry_price=order_result.avg_price or entry_price,
            current_price=order_result.avg_price or entry_price,
            sl_price=sl_price,
            tp_price=tp_price,
        )
        await self._position_repo.save(position)

        # 8. Log + report
        report = ExecutionReport(
            report_id=uuid4().hex[:12],
            signal_id=signal.signal_id,
            symbol=signal.symbol,
            side=side,
            status=order_result.status.value,
            filled_qty=order_result.filled_amount,
            avg_price=order_result.avg_price,
            order_id=order_result.id,
            position_id=position.position_id,
        )
        await self._logger.log_execution(report)

        return ExecuteSignalResult(report=report, position=position)
