#!/usr/bin/env python3
"""Backtest runner stub for the opencode `run_backtest` tool.

Forces ENVIRONMENT_MODE=BACKTESTING (the tool also sets this in the
parent process). When the analytics-engine backtest runner exists at
`apps/analytics-engine/app/application/backtest/run.py`, this script
will import and invoke it. Until then, it reports a clear stub result
so the tool is usable in dry-runs.
"""
import json
import os
import sys
from pathlib import Path

os.environ["ENVIRONMENT_MODE"] = "BACKTESTING"

ENGINE_RUNNER = Path(
    "apps/analytics-engine/app/application/backtest/run.py"
)


def main() -> int:
    req = json.loads(sys.argv[1])
    strategy = req["strategy"]
    symbol = req["symbol"]
    start = req["start"]
    end = req["end"]

    if not ENGINE_RUNNER.exists():
        print(
            json.dumps(
                {
                    "status": "stub",
                    "message": (
                        "analytics-engine backtest runner not implemented yet. "
                        "Expected at apps/analytics-engine/app/application/backtest/run.py."
                    ),
                    "request": {
                        "strategy": strategy,
                        "symbol": symbol,
                        "start": start,
                        "end": end,
                    },
                    "metrics": {
                        "sharpe": None,
                        "max_drawdown": None,
                        "win_rate": None,
                        "total_return": None,
                    },
                },
                indent=2,
            )
        )
        return 0

    # Real wiring (deferred):
    # import importlib.util
    # spec = importlib.util.spec_from_file_location("backtest_run", ENGINE_RUNNER)
    # mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    # result = mod.run(strategy, symbol, start, end)
    # print(json.dumps(result, default=str))
    print(json.dumps({"status": "stub", "engine_found": True}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
