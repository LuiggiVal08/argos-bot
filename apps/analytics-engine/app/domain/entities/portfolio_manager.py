"""Domain entity: PortfolioManager.

Portfolio-level risk and allocation management (H35).

Responsibilities:
- Total exposure cap (% of balance, default 90%)
- Per-symbol weight limits (default 20%)
- Correlation-based position capping
- Portfolio heat (max 5% drawdown from peak)

Pure domain: receives state and returns decisions. No I/O.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum

from ..value_objects.live_position import LivePosition


class PortfolioVerdict(str, Enum):
    APPROVED = "APPROVED"
    REJECTED_TOTAL_EXPOSURE = "REJECTED_TOTAL_EXPOSURE"
    REJECTED_SYMBOL_WEIGHT = "REJECTED_SYMBOL_WEIGHT"
    REJECTED_CORRELATION_CAP = "REJECTED_CORRELATION_CAP"
    REJECTED_HEAT_CAP = "REJECTED_HEAT_CAP"
    REJECTED_POSITION_LIMIT = "REJECTED_POSITION_LIMIT"


@dataclass(frozen=True)
class PortfolioDecision:
    verdict: PortfolioVerdict
    reason: str = ""
    total_exposure_pct: Decimal = Decimal("0")
    max_exposure_pct: Decimal = Decimal("0.90")
    symbol_weight_pct: Decimal = Decimal("0")
    max_symbol_weight_pct: Decimal = Decimal("0.20")
    correlation: Decimal = Decimal("0")
    max_correlation: Decimal = Decimal("0.70")
    heat_pct: Decimal = Decimal("0")
    max_heat_pct: Decimal = Decimal("0.05")


@dataclass
class PortfolioState:
    positions: list[LivePosition] = field(default_factory=list)
    total_balance: Decimal = Decimal("0")
    correlation_matrix: dict[str, dict[str, Decimal]] = field(default_factory=dict)
    peak_balance: Decimal | None = None

    @property
    def open_count(self) -> int:
        return sum(1 for p in self.positions if p.is_open)

    @property
    def total_exposure(self) -> Decimal:
        return sum(
            (p.units * p.entry_price) for p in self.positions if p.is_open
        )

    @property
    def total_exposure_pct(self) -> Decimal:
        if self.total_balance <= 0:
            return Decimal("0")
        return self.total_exposure / self.total_balance

    def symbol_exposure(self, symbol: str) -> Decimal:
        return sum(
            (p.units * p.entry_price)
            for p in self.positions
            if p.is_open and p.symbol == symbol
        )

    def symbol_weight(self, symbol: str) -> Decimal:
        if self.total_balance <= 0:
            return Decimal("0")
        return self.symbol_exposure(symbol) / self.total_balance

    @property
    def current_heat(self) -> Decimal:
        if self.peak_balance is None or self.peak_balance <= 0:
            return Decimal("0")
        return max(
            Decimal("0"),
            (self.peak_balance - self.total_balance) / self.peak_balance,
        )


class PortfolioManager:
    """Pure-domain entity for portfolio-level checks."""

    def __init__(
        self,
        max_exposure_pct: Decimal = Decimal("0.90"),
        max_symbol_weight_pct: Decimal = Decimal("0.20"),
        max_correlation: Decimal = Decimal("0.70"),
        max_heat_pct: Decimal = Decimal("0.05"),
        max_positions: int = 10,
    ) -> None:
        self._max_exposure_pct = max_exposure_pct
        self._max_symbol_weight_pct = max_symbol_weight_pct
        self._max_correlation = max_correlation
        self._max_heat_pct = max_heat_pct
        self._max_positions = max_positions

    def assess(
        self, state: PortfolioState, symbol: str | None = None
    ) -> PortfolioDecision:
        """Run all portfolio checks. Returns first rejection or APPROVED.

        Order: heat cap → total exposure → max positions →
        per-symbol weight → correlation cap.
        """
        # 1. Portfolio heat cap (drawdown from peak)
        heat = state.current_heat
        if heat >= self._max_heat_pct:
            return PortfolioDecision(
                verdict=PortfolioVerdict.REJECTED_HEAT_CAP,
                reason=f"portfolio_heat_{heat:.2%}_exceeds_{self._max_heat_pct:.0%}",
                heat_pct=heat,
                max_heat_pct=self._max_heat_pct,
                total_exposure_pct=state.total_exposure_pct,
            )

        # 2. Total exposure
        exp_pct = state.total_exposure_pct
        if exp_pct >= self._max_exposure_pct:
            return PortfolioDecision(
                verdict=PortfolioVerdict.REJECTED_TOTAL_EXPOSURE,
                reason=f"total_exp_{exp_pct:.2%}_max_{self._max_exposure_pct:.0%}",
                total_exposure_pct=exp_pct,
                max_exposure_pct=self._max_exposure_pct,
            )

        # 3. Max positions
        if state.open_count >= self._max_positions:
            return PortfolioDecision(
                verdict=PortfolioVerdict.REJECTED_POSITION_LIMIT,
                reason=f"positions_{state.open_count}_max_{self._max_positions}",
                total_exposure_pct=exp_pct,
            )

        # 4. Per-symbol weight
        if symbol is not None:
            weight = state.symbol_weight(symbol)
            if weight >= self._max_symbol_weight_pct:
                return PortfolioDecision(
                    verdict=PortfolioVerdict.REJECTED_SYMBOL_WEIGHT,
                    reason=f"symbol_{symbol}_weight_{weight:.2%}_max_{self._max_symbol_weight_pct:.0%}",
                    symbol_weight_pct=weight,
                    max_symbol_weight_pct=self._max_symbol_weight_pct,
                    total_exposure_pct=exp_pct,
                )

        # 5. Correlation cap
        if symbol is not None and state.correlation_matrix:
            for existing_sym, corr_dict in state.correlation_matrix.items():
                if existing_sym == symbol:
                    continue
                corr = corr_dict.get(symbol, corr_dict.get(existing_sym, Decimal("0")))
                if corr >= self._max_correlation:
                    return PortfolioDecision(
                        verdict=PortfolioVerdict.REJECTED_CORRELATION_CAP,
                        reason=f"corr_{symbol}_{existing_sym}_{corr:.2f}_max_{self._max_correlation:.0%}",
                        correlation=corr,
                        max_correlation=self._max_correlation,
                        total_exposure_pct=exp_pct,
                    )

        return PortfolioDecision(
            verdict=PortfolioVerdict.APPROVED,
            reason="all_checks_passed",
            total_exposure_pct=exp_pct,
            max_exposure_pct=self._max_exposure_pct,
            heat_pct=heat,
            max_heat_pct=self._max_heat_pct,
        )
