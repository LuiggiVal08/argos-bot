import { tool } from "@opencode-ai/plugin"
import { execFileSync } from "child_process"
import * as path from "path"
import { fileURLToPath } from "url"
import { dirname } from "path"

const __dirname = dirname(fileURLToPath(import.meta.url))
const SCRIPT = path.join(__dirname, "scripts", "indicators.py")

export default tool({
  description:
    "Calculate a technical indicator (RSI/EMA/SMA/MACD/BB) on OHLCV data via the project's Python helper. Reads local CSV first; falls back to CCXT outside LIVE mode.",
  args: {
    symbol: tool.schema.string().describe("Trading pair, e.g. BTC/USDT"),
    timeframe: tool.schema
      .string()
      .describe("Candle timeframe: 1m, 5m, 15m, 1h, 4h, 1d"),
    indicator: tool.schema
      .string()
      .describe("One of: rsi, ema, sma, macd, bb"),
    period: tool.schema
      .number()
      .describe("Lookback period (e.g. 14 for RSI, 20 for SMA/BB)")
      .default(14),
  },
  async execute(args) {
    const out = execFileSync("python3", [SCRIPT, JSON.stringify(args)], {
      encoding: "utf8",
      maxBuffer: 10 * 1024 * 1024,
    })
    return {
      title: `${args.indicator.toUpperCase()}(${args.period}) ${args.symbol} ${args.timeframe}`,
      output: out,
    }
  },
})
