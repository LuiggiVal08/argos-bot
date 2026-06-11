from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class DashboardPanel:
    market: dict[str, Any] = field(default_factory=dict)
    ai: dict[str, Any] = field(default_factory=dict)
    risk: dict[str, Any] = field(default_factory=dict)
    training: dict[str, Any] = field(default_factory=dict)
    updated_at: str = ""

    def __post_init__(self) -> None:
        if not self.updated_at:
            self.updated_at = datetime.now(timezone.utc).isoformat()


class DashboardEngine:
    def __init__(self) -> None:
        self._panel = DashboardPanel()
        self._history: list[DashboardPanel] = []
        self._max_history = 1000

    def update_market(
        self,
        symbols: list[str],
        volatility: float = 0.0,
        regime: str = "UNKNOWN",
    ) -> None:
        self._panel.market.update({
            "symbols": symbols,
            "volatility": volatility,
            "regime": regime,
        })
        self._snapshot()

    def update_ai(
        self,
        probabilities: dict[str, float] | None = None,
        uncertainty: float = 0.0,
        active_model: str = "",
    ) -> None:
        self._panel.ai.update({
            "probabilities": probabilities or {},
            "uncertainty": uncertainty,
            "active_model": active_model,
        })
        self._snapshot()

    def update_risk(
        self,
        drawdown: float = 0.0,
        exposure: float = 0.0,
        portfolio_heat: float = 0.0,
    ) -> None:
        self._panel.risk.update({
            "drawdown": drawdown,
            "exposure": exposure,
            "portfolio_heat": portfolio_heat,
        })
        self._snapshot()

    def update_training(
        self,
        champion: str = "",
        challenger: str = "",
        historical_metrics: dict[str, list[float]] | None = None,
    ) -> None:
        self._panel.training.update({
            "champion": champion,
            "challenger": challenger,
            "historical_metrics": historical_metrics or {},
        })
        self._snapshot()

    def _snapshot(self) -> None:
        self._panel.updated_at = datetime.now(timezone.utc).isoformat()
        self._history.append(DashboardPanel(
            market=dict(self._panel.market),
            ai=dict(self._panel.ai),
            risk=dict(self._panel.risk),
            training=dict(self._panel.training),
        ))
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

    def current(self) -> DashboardPanel:
        return self._panel

    def history(self, limit: int = 100) -> list[DashboardPanel]:
        return self._history[-limit:]

    def clear(self) -> None:
        self._panel = DashboardPanel()
        self._history.clear()
