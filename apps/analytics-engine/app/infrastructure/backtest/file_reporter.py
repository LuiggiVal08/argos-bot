"""FileBacktestReporter — persiste resultados de backtest en JSON."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from ...domain.value_objects.backtest_config import BacktestConfig
from ...domain.value_objects.backtest_metrics import BacktestMetrics
from ...domain.value_objects.backtest_trade import BacktestTrade
from ...domain.entities.backtest_engine import EquityPoint


class _DecimalEncoder(json.JSONEncoder):
    """Serializa Decimal como float."""
    def default(self, o: Any) -> Any:
        if isinstance(o, Decimal):
            return float(o)
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)


class FileBacktestReporter:
    """Guarda reportes de backtest en archivos JSON.

    Los reportes se escriben en reports/backtest/ con nombre
    <strategy>_<symbol>_<timestamp>.json
    """

    def __init__(self, output_dir: str = "reports/backtest") -> None:
        self._output_dir = output_dir

    async def save(
        self,
        config: BacktestConfig,
        metrics: BacktestMetrics,
        trades: list[BacktestTrade],
        equity_curve: list[EquityPoint],
    ) -> str:
        os.makedirs(self._output_dir, exist_ok=True)

        now = datetime.now(timezone.utc)
        ts = now.strftime("%Y%m%d_%H%M%S")
        safe_symbol = config.symbol.replace("/", "_").lower()
        filename = f"{config.strategy_id}_{safe_symbol}_{ts}.json"
        filepath = os.path.join(self._output_dir, filename)

        report = self._build_report(config, metrics, trades, equity_curve, ts)

        with open(filepath, "w") as f:
            json.dump(report, f, cls=_DecimalEncoder, indent=2)

        return os.path.abspath(filepath)

    @staticmethod
    def _build_report(
        config: BacktestConfig,
        metrics: BacktestMetrics,
        trades: list[BacktestTrade],
        equity_curve: list[EquityPoint],
        timestamp: str,
    ) -> dict:
        return {
            "report": {
                "generated_at": timestamp,
                "strategy_id": config.strategy_id,
                "symbol": config.symbol,
                "timeframe": config.timeframe,
                "start": config.start,
                "end": config.end,
                "initial_balance": float(config.initial_balance),
                "risk_pct": float(config.risk_pct),
            },
            "metrics": {
                "sharpe_ratio": metrics.sharpe_ratio,
                "max_drawdown_pct": metrics.max_drawdown_pct,
                "win_rate": metrics.win_rate,
                "total_return_pct": float(metrics.total_return_pct),
                "total_trades": metrics.total_trades,
                "winning_trades": metrics.winning_trades,
                "losing_trades": metrics.losing_trades,
                "avg_pnl_usdt": float(metrics.avg_pnl_usdt),
                "final_balance": float(metrics.final_balance),
                "volatility_pct": metrics.volatility_pct,
                "profit_factor": metrics.profit_factor,
            },
            "trades": [
                {
                    "side": t.side.value,
                    "entry_time": t.entry_time.isoformat(),
                    "entry_price": float(t.entry_price),
                    "exit_time": t.exit_time.isoformat(),
                    "exit_price": float(t.exit_price),
                    "units": float(t.units),
                    "pnl": float(t.pnl),
                    "pnl_pct": float(t.pnl_pct),
                    "entry_reason": t.entry_reason,
                    "exit_reason": t.exit_reason,
                    "duration_min": t.duration_min,
                }
                for t in trades
            ],
            "equity_curve": [
                {"timestamp": ts.isoformat(), "balance": float(bal)}
                for ts, bal in equity_curve
            ],
            "trade_count": len(trades),
            "equity_points": len(equity_curve),
        }
