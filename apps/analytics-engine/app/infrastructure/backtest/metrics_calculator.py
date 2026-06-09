"""SimpleMetricsCalculator — computa metricas de backtest."""

from __future__ import annotations

from decimal import Decimal
from math import log, sqrt

from ...domain.value_objects.backtest_metrics import BacktestMetrics
from ...domain.value_objects.backtest_trade import BacktestTrade
from ...domain.entities.backtest_engine import EquityPoint


class SimpleMetricsCalculator:
    """Calcula metricas de performance a partir de trades y equity curve.

    Sharpe ratio: anualizado, asumiendo RF rate = 0.
    Max drawdown: maximo decremento pico-a-valle de la equity curve.
    Win rate: trades con PnL > 0 / total trades.
    """

    def compute(
        self,
        trades: list[BacktestTrade],
        equity_curve: list[EquityPoint],
        initial_balance: object,
    ) -> BacktestMetrics:
        if not isinstance(initial_balance, Decimal):
            initial_balance = Decimal(str(initial_balance))

        total_trades = len(trades)
        if total_trades == 0:
            return BacktestMetrics(
                sharpe_ratio=0.0,
                max_drawdown_pct=0.0,
                win_rate=0.0,
                total_return_pct=Decimal("0"),
                total_trades=0,
                final_balance=initial_balance,
            )

        winning = [t for t in trades if t.pnl > 0]
        losing = [t for t in trades if t.pnl < 0]
        win_rate = len(winning) / total_trades

        total_pnl = sum(t.pnl for t in trades)
        final_balance = initial_balance + total_pnl
        total_return_pct = (total_pnl / initial_balance * 100) if initial_balance > 0 else Decimal("0")

        avg_pnl = (total_pnl / total_trades) if total_trades > 0 else Decimal("0")

        # Profit factor
        gross_profit = sum(t.pnl for t in winning)
        gross_loss = abs(sum(t.pnl for t in losing))
        profit_factor: float | None = (
            float(gross_profit / gross_loss) if gross_loss > 0 else None
        )

        # Equity curve returns for Sharpe
        returns = self._compute_returns(equity_curve)
        sharpe = self._compute_sharpe(returns)

        # Max drawdown
        max_dd = self._compute_max_drawdown(equity_curve)

        # Volatility
        vol = self._compute_volatility(returns)

        return BacktestMetrics(
            sharpe_ratio=round(sharpe, 4),
            max_drawdown_pct=round(max_dd, 4),
            win_rate=round(win_rate, 4),
            total_return_pct=total_return_pct.quantize(Decimal("0.01")),
            total_trades=total_trades,
            winning_trades=len(winning),
            losing_trades=len(losing),
            avg_pnl_usdt=avg_pnl.quantize(Decimal("0.01")),
            final_balance=final_balance.quantize(Decimal("0.01")),
            volatility_pct=round(vol, 4),
            profit_factor=round(profit_factor, 4) if profit_factor is not None else None,
        )

    @staticmethod
    def _compute_returns(equity: list[EquityPoint]) -> list[float]:
        """Retorna returns porcentuales entre puntos consecutivos."""
        if len(equity) < 2:
            return []
        returns: list[float] = []
        for i in range(1, len(equity)):
            prev = float(equity[i - 1][1])
            curr = float(equity[i][1])
            if prev > 0:
                returns.append((curr - prev) / prev)
        return returns

    @staticmethod
    def _compute_sharpe(returns: list[float]) -> float:
        """Sharpe ratio anualizado (RF=0)."""
        if len(returns) < 2:
            return 0.0
        mean_r = sum(returns) / len(returns)
        variance = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
        if variance <= 0:
            return 0.0
        std = sqrt(variance)
        # Assuming daily returns -> annualize by sqrt(365)
        # For other timeframes, this is approximate
        annualized = mean_r / std * sqrt(365) if std > 0 else 0.0
        return annualized

    @staticmethod
    def _compute_max_drawdown(equity: list[EquityPoint]) -> float:
        """Maximo drawdown pico-a-valle como porcentaje."""
        if len(equity) < 2:
            return 0.0
        peak = float(equity[0][1])
        max_dd = 0.0
        for _ts, bal in equity:
            bal_f = float(bal)
            if bal_f > peak:
                peak = bal_f
            dd = (peak - bal_f) / peak if peak > 0 else 0.0
            if dd > max_dd:
                max_dd = dd
        return max_dd * 100

    @staticmethod
    def _compute_volatility(returns: list[float]) -> float:
        """Volatilidad diaria como desviacion estandar de returns."""
        if len(returns) < 2:
            return 0.0
        mean_r = sum(returns) / len(returns)
        variance = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
        return sqrt(variance) * 100
