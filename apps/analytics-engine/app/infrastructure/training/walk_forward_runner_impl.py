from __future__ import annotations

from typing import Any

import numpy as np


class SimpleWalkForwardRunner:
    async def run(
        self,
        train_data: Any,
        test_data: Any,
        model_config: Any,
    ) -> dict[str, float]:
        return {
            "sharpe_ratio": 0.0,
            "profit_factor": 0.0,
            "max_drawdown": 0.0,
            "win_rate": 0.0,
        }
