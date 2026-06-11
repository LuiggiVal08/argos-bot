from __future__ import annotations

from typing import Any

from ...domain.entities.dashboard_engine import DashboardEngine, DashboardPanel


class GetDashboardUseCase:
    def __init__(self, dashboard: DashboardEngine) -> None:
        self._dashboard = dashboard

    async def execute(self) -> DashboardPanel:
        return self._dashboard.current()


class GetDashboardHistoryUseCase:
    def __init__(self, dashboard: DashboardEngine) -> None:
        self._dashboard = dashboard

    async def execute(self, limit: int = 100) -> list[dict[str, Any]]:
        history = self._dashboard.history(limit=limit)
        return [
            {
                "market": p.market,
                "ai": p.ai,
                "risk": p.risk,
                "training": p.training,
                "updated_at": p.updated_at,
            }
            for p in history
        ]


class UpdateDashboardUseCase:
    def __init__(self, dashboard: DashboardEngine) -> None:
        self._dashboard = dashboard

    async def execute(
        self,
        market: dict[str, Any] | None = None,
        ai: dict[str, Any] | None = None,
        risk: dict[str, Any] | None = None,
        training: dict[str, Any] | None = None,
    ) -> None:
        if market:
            self._dashboard.update_market(
                symbols=market.get("symbols", []),
                volatility=market.get("volatility", 0.0),
                regime=market.get("regime", "UNKNOWN"),
            )
        if ai:
            self._dashboard.update_ai(
                probabilities=ai.get("probabilities"),
                uncertainty=ai.get("uncertainty", 0.0),
                active_model=ai.get("active_model", ""),
            )
        if risk:
            self._dashboard.update_risk(
                drawdown=risk.get("drawdown", 0.0),
                exposure=risk.get("exposure", 0.0),
                portfolio_heat=risk.get("portfolio_heat", 0.0),
            )
        if training:
            self._dashboard.update_training(
                champion=training.get("champion", ""),
                challenger=training.get("challenger", ""),
                historical_metrics=training.get("historical_metrics"),
            )
