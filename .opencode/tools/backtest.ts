import { tool } from "@opencode-ai/plugin"
import { execFileSync } from "child_process"
import * as path from "path"
import { fileURLToPath } from "url"
import { dirname } from "path"

const __dirname = dirname(fileURLToPath(import.meta.url))
const SCRIPT = path.join(__dirname, "scripts", "backtest.py")

export default tool({
  description:
    "Run a backtest for a named strategy over historical OHLCV. Returns Sharpe, max drawdown, win rate, total return. Forces ENVIRONMENT_MODE=BACKTESTING.",
  args: {
    strategy: tool.schema
      .string()
      .describe(
        "Strategy id matching apps/analytics-engine/app/domain/strategies/<id>.py",
      ),
    symbol: tool.schema.string().describe("Trading pair, e.g. BTC/USDT"),
    start: tool.schema.string().describe("ISO date YYYY-MM-DD"),
    end: tool.schema.string().describe("ISO date YYYY-MM-DD"),
  },
  async execute(args) {
    const env = { ...process.env, ENVIRONMENT_MODE: "BACKTESTING" }
    const out = execFileSync("python3", [SCRIPT, JSON.stringify(args)], {
      env,
      encoding: "utf8",
      maxBuffer: 50 * 1024 * 1024,
    })
    return {
      title: `Backtest ${args.strategy} ${args.symbol} ${args.start}..${args.end}`,
      output: out,
    }
  },
})
