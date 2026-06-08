"""SignalConsumer port — fuente de señales de trading."""
from __future__ import annotations

from typing import AsyncIterator, Protocol, runtime_checkable

from ...domain.value_objects.execution_signal import ExecutionSignal


@runtime_checkable
class SignalConsumer(Protocol):
    """Fuente de señales de trading.

    Los adaptadores concretos pueden leer de NovaQuant, de una cola
    de mensajes, de un archivo, etc.
    """

    async def subscribe(self) -> AsyncIterator[ExecutionSignal]:
        """Itera sobre señales entrantes (streaming).

        El caller itera con `async for signal in consumer.subscribe():`.
        """
        ...
