from __future__ import annotations

import structlog

from ...application.ports.regime_detector import RegimeDetectionError
from ...domain.entities.market_context import MarketContext
from ...domain.value_objects.market_regime import RegimeType

log = structlog.get_logger()

# Thresholds derived from technical analysis standards
ADX_TRENDING_THRESHOLD = 25.0
BBW_HIGH_PERCENTILE = 0.7
BBW_LOW_PERCENTILE = 0.3
ATR_HIGH_PERCENTILE = 0.7
ATR_LOW_PERCENTILE = 0.3


class RuleBasedRegimeDetector:
    """Rule-based market regime classifier.

    Classifies market state using ADX, BBW, ATR, and EMA slope.

    Rules:
        ADX > 25  → TRENDING (directional movement)
        ADX <= 25 → RANGING (no strong trend)

        BBW high + ATR high → HIGH_VOLATILITY overlay
        BBW low  + ATR low  → LOW_VOLATILITY overlay

        If features are invalid → UNKNOWN

    Note: BBW and ATR percentiles are computed dynamically from a
    rolling history window. When no history is available, median
    thresholds are used as fallback.
    """

    def __init__(
        self,
        bbw_history_window: int = 100,
        atr_history_window: int = 100,
    ) -> None:
        self._bbw_history: list[float] = []
        self._atr_history: list[float] = []
        self._bbw_window = bbw_history_window
        self._atr_window = atr_history_window

    def detect(
        self,
        features: dict[str, float],
    ) -> MarketContext:
        REQUIRED = {"adx", "bbw", "atr", "ema_slope"}
        missing = REQUIRED - set(features.keys())
        if missing:
            raise RegimeDetectionError(
                f"missing required features: {missing}"
            )

        adx = features["adx"]
        bbw = features["bbw"]
        atr = features["atr"]
        ema_slope = features["ema_slope"]

        if any(
            v is None or (isinstance(v, float) and (v != v or v < 0))
            for v in [adx, bbw, atr]
        ):
            return MarketContext(
                regime=RegimeType.UNKNOWN,
                adx=adx if isinstance(adx, (int, float)) and adx == adx else 0.0,
                bbw=bbw if isinstance(bbw, (int, float)) and bbw == bbw else 0.0,
                atr=atr if isinstance(atr, (int, float)) and atr == atr else 0.0,
                ema_slope=ema_slope if isinstance(ema_slope, (int, float)) and ema_slope == ema_slope else 0.0,
            )

        # Track rolling history for percentile-based thresholds
        self._bbw_history.append(bbw)
        self._atr_history.append(atr)
        if len(self._bbw_history) > self._bbw_window:
            self._bbw_history.pop(0)
        if len(self._atr_history) > self._atr_window:
            self._atr_history.pop(0)

        # Step 1: Directional bias (ADX)
        is_trending = adx >= ADX_TRENDING_THRESHOLD

        # Step 2: Volatility overlay (BBW + ATR)
        bbw_high = self._is_high_bbw(bbw)
        bbw_low = self._is_low_bbw(bbw)
        atr_high = self._is_high_atr(atr)
        atr_low = self._is_low_atr(atr)

        if is_trending:
            if bbw_high or atr_high:
                regime = RegimeType.TRENDING
            elif bbw_low and atr_low:
                regime = RegimeType.LOW_VOLATILITY
            else:
                regime = RegimeType.TRENDING
        else:
            if bbw_high or atr_high:
                regime = RegimeType.HIGH_VOLATILITY
            elif bbw_low and atr_low:
                regime = RegimeType.LOW_VOLATILITY
            else:
                regime = RegimeType.RANGING

        return MarketContext(
            regime=regime,
            adx=adx,
            bbw=bbw,
            atr=atr,
            ema_slope=ema_slope,
        )

    def reset(self) -> None:
        self._bbw_history.clear()
        self._atr_history.clear()

    def _is_high_bbw(self, bbw: float) -> bool:
        if len(self._bbw_history) < 10:
            return bbw > 0.5
        sorted_vals = sorted(self._bbw_history)
        threshold = sorted_vals[int(len(sorted_vals) * BBW_HIGH_PERCENTILE)]
        return bbw >= threshold

    def _is_low_bbw(self, bbw: float) -> bool:
        if len(self._bbw_history) < 10:
            return bbw <= 0.05
        sorted_vals = sorted(self._bbw_history)
        threshold = sorted_vals[int(len(sorted_vals) * BBW_LOW_PERCENTILE)]
        return bbw <= threshold

    def _is_high_atr(self, atr: float) -> bool:
        if len(self._atr_history) < 10:
            return False
        sorted_vals = sorted(self._atr_history)
        threshold = sorted_vals[int(len(sorted_vals) * ATR_HIGH_PERCENTILE)]
        return atr >= threshold

    def _is_low_atr(self, atr: float) -> bool:
        if len(self._atr_history) < 10:
            return False
        sorted_vals = sorted(self._atr_history)
        threshold = sorted_vals[int(len(sorted_vals) * ATR_LOW_PERCENTILE)]
        return atr <= threshold
