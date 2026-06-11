"""Value Object: BacktestMetrics — metricas calculadas de una corrida."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class BacktestMetrics:
    """Metricas resultantes de una corrida de backtest.

    Attributes:
        sharpe_ratio: Ratio de Sharpe anualizado.
        max_drawdown_pct: Maximo drawdown porcentual (positivo).
        win_rate: Proporcion de trades ganadores (0..1).
        total_return_pct: Retorno total porcentual.
        total_trades: Numero total de trades ejecutados.
        winning_trades: Trades con pnl > 0.
        losing_trades: Trades con pnl < 0.
        avg_pnl_usdt: PnL promedio por trade en USDT.
        final_balance: Balance final en USDT.
        volatility_pct: Volatilidad diaria del portafolio (%).
        profit_factor: Ganancia bruta / perdida bruta (inf si no hay perdidas).
    """

    sharpe_ratio: float
    max_drawdown_pct: float
    win_rate: float
    total_return_pct: Decimal
    total_trades: int
    winning_trades: int = 0
    losing_trades: int = 0
    avg_pnl_usdt: Decimal = Decimal("0")
    final_balance: Decimal = Decimal("0")
    volatility_pct: float = 0.0
    profit_factor: float | None = None

    def __post_init__(self) -> None:
        if self.total_trades < 0:
            raise ValueError(
                f"total_trades must be >= 0, got {self.total_trades}"
            )
        if not 0.0 <= self.win_rate <= 1.0:
            raise ValueError(
                f"win_rate must be in [0, 1], got {self.win_rate}"
            )
