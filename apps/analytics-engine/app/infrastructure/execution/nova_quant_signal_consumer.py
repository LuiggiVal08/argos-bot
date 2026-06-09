"""NovaQuantSignalConsumer — adapta señales de NovaQuant al port SignalConsumer.

Toma la salida de NovaQuant (TradingSignal) y la convierte en
ExecutionSignal para el pipeline de ejecución H7.

En lugar de acoplarse a un predictor concreto, recibe un AsyncIterator
de TradingSignal (inyectado por composición).
"""
from __future__ import annotations

from typing import AsyncIterator

from ...domain.value_objects.execution_signal import ExecutionSignal
from ...domain.value_objects.trading_signal import TradingSignal
from ...application.ports.signal_consumer import SignalConsumer


class NovaQuantSignalConsumer:
    """Consume TradingSignals y los adapta a ExecutionSignal.

    Args:
        signal_stream: AsyncIterator que produce TradingSignals.
                       Típicamente el output de PredictSignalUseCase.
        min_confidence: Confianza mínima (default 0.7).
    """

    def __init__(
        self,
        signal_stream: AsyncIterator[TradingSignal],
        min_confidence: float = 0.7,
    ) -> None:
        self._stream = signal_stream
        self._min_confidence = min_confidence

    async def subscribe(self) -> AsyncIterator[ExecutionSignal]:
        async for ts in self._stream:
            if not ts.is_actionable(self._min_confidence):
                continue
            yield ExecutionSignal(
                side=ts.side,
                confidence=ts.confidence,
                symbol=ts.metadata.get("symbol", "UNKNOWN"),
                strategy_id="novaquant",
                price=None,
                timestamp=ts.timestamp,
                metadata=ts.metadata,
            )
