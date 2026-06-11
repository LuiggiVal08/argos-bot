from __future__ import annotations

from dataclasses import dataclass


class PromotionVerdict:
    PROMOTE = "PROMOTE"
    DENIED = "DENIED"
    METRICS_INCOMPARABLE = "METRICS_INCOMPARABLE"


@dataclass(frozen=True)
class PromotionRule:
    min_sharpe_improvement: float = 0.05
    min_profit_factor_improvement: float = 0.03
    max_drawdown_increase: float = 0.02
    win_rate_min: float = 0.40

    def __post_init__(self) -> None:
        if self.min_sharpe_improvement < 0:
            raise ValueError("min_sharpe_improvement must be >= 0")
        if self.max_drawdown_increase < 0:
            raise ValueError("max_drawdown_increase must be >= 0")


class PromotionEngine:
    def __init__(self, rules: PromotionRule | None = None) -> None:
        self._rules = rules or PromotionRule()

    @property
    def rules(self) -> PromotionRule:
        return self._rules

    def evaluate(
        self,
        champion_metrics: dict[str, float] | None,
        challenger_metrics: dict[str, float],
    ) -> str:
        required_keys = {"sharpe_ratio", "profit_factor", "max_drawdown", "win_rate"}
        if not required_keys.issubset(challenger_metrics.keys()):
            return PromotionVerdict.METRICS_INCOMPARABLE

        if champion_metrics is None:
            if challenger_metrics.get("win_rate", 0) >= self._rules.win_rate_min:
                return PromotionVerdict.PROMOTE
            return PromotionVerdict.DENIED

        if not required_keys.issubset(champion_metrics.keys()):
            return PromotionVerdict.METRICS_INCOMPARABLE

        champ_sharpe = champion_metrics["sharpe_ratio"]
        champ_pf = champion_metrics["profit_factor"]
        champ_dd = champion_metrics["max_drawdown"]

        chal_sharpe = challenger_metrics["sharpe_ratio"]
        chal_pf = challenger_metrics["profit_factor"]
        chal_dd = challenger_metrics["max_drawdown"]
        chal_wr = challenger_metrics["win_rate"]

        sharpe_ok = chal_sharpe >= champ_sharpe * (1 + self._rules.min_sharpe_improvement)
        pf_ok = chal_pf >= champ_pf * (1 + self._rules.min_profit_factor_improvement)
        dd_ok = chal_dd <= champ_dd * (1 + self._rules.max_drawdown_increase)
        wr_ok = chal_wr >= self._rules.win_rate_min

        if sharpe_ok and pf_ok and dd_ok and wr_ok:
            return PromotionVerdict.PROMOTE
        return PromotionVerdict.DENIED
