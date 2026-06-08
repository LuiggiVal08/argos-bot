"""Value Object: TradingSignal — resultado de una predicción.

Contiene la dirección (SignalSide), la confianza de la red (0..1),
el timestamp de generación, y metadatos opcionales para trazabilidad
(qué features contribuyeron, versión del modelo, etc.).

Per spec section 5 Historia 6 (NovaQuant):
- confidence threshold >= 0.7 para ejecutar (configurable en ModelConfig).
- Antes de enviar al PlaceOrderUseCase, pasa por confirmación de
  indicadores (RSI, MACD, BB) para reducir falsos positivos.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .signal_side import SignalSide


@dataclass(frozen=True)
class TradingSignal:
    """Señal de trading generada por NovaQuant.

    Attributes:
        side:        Dirección de la señal (BUY, SELL, HOLD).
        confidence:  Probabilidad asignada por la red (0.0 a 1.0).
        timestamp:   Momento de generación de la señal (UTC).
        model_version: Versión del modelo que generó la señal.
        metadata:    Dict opcional con features contribuyentes,
                     indicadores de confirmación, etc.
    """

    side: SignalSide
    confidence: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    model_version: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"confidence must be in [0, 1], got {self.confidence}"
            )

    def is_actionable(self, threshold: float = 0.7) -> bool:
        """True si la confianza supera el umbral y no es HOLD."""
        return self.side != SignalSide.HOLD and self.confidence >= threshold


