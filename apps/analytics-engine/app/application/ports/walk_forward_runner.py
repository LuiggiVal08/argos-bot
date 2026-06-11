from __future__ import annotations

from typing import Any, Protocol


class WalkForwardRunner(Protocol):
    async def run(
        self,
        train_data: Any,
        test_data: Any,
        model_config: Any,
    ) -> dict[str, float]:
        ...
