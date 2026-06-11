"""Domain entity: RiskEngine.

Comprehensive risk validation for trade execution (H32).

Validates:
- Consecutive losses (< configurable max, default 3)
- Max open positions (< configurable max, default 5)
- Per-symbol exposure (% of balance, default max 20%)
- Daily drawdown (< 5% circuit breaker)
- Total portfolio exposure (% of balance, default max 90%)

Pure domain: receives current state as arguments, returns decisions.
No I/O, no side effects.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum

from ..value_objects.live_position import LivePosition


class RiskVerdict(str, Enum):
    APPROVED = "APPROVED"
    REJECTED_MAX_LOSSES = "REJECTED_MAX_LOSSES"
    REJECTED_MAX_POSITIONS = "REJECTED_MAX_POSITIONS"
    REJECTED_SYMBOL_EXPOSURE = "REJECTED_SYMBOL_EXPOSURE"
    REJECTED_DAILY_DRAWDOWN = "REJECTED_DAILY_DRAWDOWN"
    REJECTED_TOTAL_EXPOSURE = "REJECTED_TOTAL_EXPOSURE"


@dataclass(frozen=True)
class RiskAssessment:
    verdict: RiskVerdict
    reason: str = ""
    current_losses: int = 0
    max_losses: int = 3
    open_positions: int = 0
    max_positions: int = 5
    symbol_exposure_pct: Decimal = Decimal("0")
    max_symbol_exposure_pct: Decimal = Decimal("0.20")
    total_exposure_pct: Decimal = Decimal("0")
    max_total_exposure_pct: Decimal = Decimal("0.90")
    daily_drawdown_pct: Decimal = Decimal("0")
    max_daily_drawdown_pct: Decimal = Decimal("0.05")


@dataclass
class PortfolioState:
    """Snapshot of current portfolio for risk checks."""
    total_balance: Decimal
    positions: list[LivePosition] = field(default_factory=list)
    consecutive_losses: int = 0
    daily_starting_balance: Decimal | None = None

    @property
    def open_count(self) -> int:
        return sum(1 for p in self.positions if p.is_open)

    @property
    def total_exposure(self) -> Decimal:
        return sum(
            (p.units * p.entry_price) for p in self.positions if p.is_open
        )

    @property
    def current_balance(self) -> Decimal:
        if self.daily_starting_balance is not None:
            return self.daily_starting_balance
        return self.total_balance

    def symbol_exposure(self, symbol: str) -> Decimal:
        return sum(
            (p.units * p.entry_price)
            for p in self.positions
            if p.is_open and p.symbol == symbol
        )


class RiskEngine:
    """Pure-domain entity. Validates trade proposals against risk rules.

    Stateless — receives state and returns assessment.
    """

    def __init__(
        self,
        max_consecutive_losses: int = 3,
        max_open_positions: int = 5,
        max_symbol_exposure_pct: Decimal = Decimal("0.20"),
        max_total_exposure_pct: Decimal = Decimal("0.90"),
        max_daily_drawdown_pct: Decimal = Decimal("0.05"),
    ) -> None:
        self._max_consecutive_losses = max_consecutive_losses
        self._max_open_positions = max_open_positions
        self._max_symbol_exposure_pct = max_symbol_exposure_pct
        self._max_total_exposure_pct = max_total_exposure_pct
        self._max_daily_drawdown_pct = max_daily_drawdown_pct

    def assess(self, state: PortfolioState, symbol: str | None = None) -> RiskAssessment:
        """Run all risk checks against the portfolio state.

        Order: daily drawdown → consecutive losses → max positions →
        per-symbol exposure → total exposure.
        Returns first rejection or APPROVED.
        """
        # 1. Daily drawdown check
        if state.daily_starting_balance is not None and state.daily_starting_balance > 0:
            current_total = state.total_balance
            dd_pct = (state.daily_starting_balance - current_total) / state.daily_starting_balance
            if dd_pct > 0:
                if dd_pct >= self._max_daily_drawdown_pct:
                    return RiskAssessment(
                        verdict=RiskVerdict.REJECTED_DAILY_DRAWDOWN,
                        reason=f"daily_drawdown_{dd_pct:.2%}_exceeds_{self._max_daily_drawdown_pct:.0%}",
                        daily_drawdown_pct=dd_pct,
                        max_daily_drawdown_pct=self._max_daily_drawdown_pct,
                        open_positions=state.open_count,
                        total_exposure_pct=state.total_exposure / state.total_balance
                        if state.total_balance > 0 else Decimal("0"),
                    )

        # 2. Consecutive losses
        if state.consecutive_losses >= self._max_consecutive_losses:
            return RiskAssessment(
                verdict=RiskVerdict.REJECTED_MAX_LOSSES,
                reason=f"consecutive_losses_{state.consecutive_losses}_max_{self._max_consecutive_losses}",
                current_losses=state.consecutive_losses,
                max_losses=self._max_consecutive_losses,
                open_positions=state.open_count,
                total_exposure_pct=state.total_exposure / state.total_balance
                if state.total_balance > 0 else Decimal("0"),
            )

        # 3. Max open positions
        if state.open_count >= self._max_open_positions:
            return RiskAssessment(
                verdict=RiskVerdict.REJECTED_MAX_POSITIONS,
                reason=f"open_positions_{state.open_count}_max_{self._max_open_positions}",
                open_positions=state.open_count,
                max_positions=self._max_open_positions,
                total_exposure_pct=state.total_exposure / state.total_balance
                if state.total_balance > 0 else Decimal("0"),
            )

        # 4. Per-symbol exposure
        if symbol is not None:
            sym_exp = state.symbol_exposure(symbol)
            sym_pct = sym_exp / state.total_balance if state.total_balance > 0 else Decimal("0")
            if sym_pct >= self._max_symbol_exposure_pct:
                return RiskAssessment(
                    verdict=RiskVerdict.REJECTED_SYMBOL_EXPOSURE,
                    reason=f"symbol_{symbol}_exposure_{sym_pct:.2%}_max_{self._max_symbol_exposure_pct:.0%}",
                    symbol_exposure_pct=sym_pct,
                    max_symbol_exposure_pct=self._max_symbol_exposure_pct,
                    open_positions=state.open_count,
                    total_exposure_pct=state.total_exposure / state.total_balance
                    if state.total_balance > 0 else Decimal("0"),
                )

        # 5. Total portfolio exposure
        total_exp_pct = state.total_exposure / state.total_balance if state.total_balance > 0 else Decimal("0")
        if total_exp_pct >= self._max_total_exposure_pct:
            return RiskAssessment(
                verdict=RiskVerdict.REJECTED_TOTAL_EXPOSURE,
                reason=f"total_exposure_{total_exp_pct:.2%}_max_{self._max_total_exposure_pct:.0%}",
                total_exposure_pct=total_exp_pct,
                max_total_exposure_pct=self._max_total_exposure_pct,
                open_positions=state.open_count,
            )

        return RiskAssessment(
            verdict=RiskVerdict.APPROVED,
            reason="all_checks_passed",
            open_positions=state.open_count,
            max_positions=self._max_open_positions,
            total_exposure_pct=total_exp_pct,
            max_total_exposure_pct=self._max_total_exposure_pct,
        )
