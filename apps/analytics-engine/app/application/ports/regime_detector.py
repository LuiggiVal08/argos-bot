from __future__ import annotations

from typing import Protocol, runtime_checkable

from ...domain.entities.market_context import MarketContext


class RegimeDetectionError(RuntimeError):
    """Raised when regime detection fails due to invalid inputs."""


@runtime_checkable
class RegimeDetector(Protocol):
    """Classifies the current market regime from named feature values.

    The caller extracts and passes the required feature values
    (adx, bbw, atr, ema_slope) from the feature vector.
    """

    def detect(
        self,
        features: dict[str, float],
    ) -> MarketContext:
        """Classify market regime from named feature values.

        Required keys: adx, bbw, atr, ema_slope.

        Args:
            features: dict of named feature values for current timestep.

        Returns:
            MarketContext with classified RegimeType.

        Raises RegimeDetectionError if required keys are missing or invalid.
        """
        ...
