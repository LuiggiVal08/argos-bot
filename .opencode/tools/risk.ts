import { tool } from "@opencode-ai/plugin"

export const position_size = tool({
  description:
    "Compute position size so the stop-loss distance (= ATR) equals at most 1% of free balance. Implements spec section 5 Historia 2.",
  args: {
    free_balance: tool.schema
      .number()
      .describe("Free margin in quote currency"),
    atr: tool.schema
      .number()
      .describe("Current ATR in quote currency per unit"),
    risk_pct: tool.schema
      .number()
      .describe("Risk per trade as decimal")
      .default(0.01),
  },
  async execute({ free_balance, atr, risk_pct }) {
    if (free_balance <= 0)
      return { title: "Invalid balance", output: "ERROR: free_balance must be > 0" }
    if (atr <= 0)
      return { title: "Invalid ATR", output: "ERROR: atr must be > 0" }
    if (risk_pct > 0.02)
      return {
        title: "Risk cap exceeded",
        output: "ERROR: risk_pct > 2% violates spec section 5 Historia 2",
      }
    const size = (free_balance * risk_pct) / atr
    return {
      title: "Position size",
      output: JSON.stringify(
        {
          size_units: size,
          notional_at_stop: free_balance * risk_pct,
        },
        null,
        2,
      ),
    }
  },
})

export const drawdown_check = tool({
  description:
    "Compare daily P&L against the 5% drawdown circuit-breaker threshold. Implements spec section 5 Historia 3.",
  args: {
    starting_balance: tool.schema
      .number()
      .describe("Balance at UTC 00:00"),
    current_balance: tool.schema.number().describe("Current free balance"),
    threshold_pct: tool.schema
      .number()
      .describe("Trip threshold as decimal")
      .default(0.05),
  },
  async execute({ starting_balance, current_balance, threshold_pct }) {
    if (starting_balance <= 0)
      return { title: "Invalid start", output: "ERROR: starting_balance must be > 0" }
    const dd = (starting_balance - current_balance) / starting_balance
    const verdict = dd >= threshold_pct ? "TRIP" : dd >= threshold_pct * 0.6 ? "WARN" : "SAFE"
    return {
      title: `Drawdown ${(dd * 100).toFixed(2)}%`,
      output: JSON.stringify(
        {
          drawdown_pct: dd,
          verdict,
          action:
            verdict === "TRIP"
              ? "halt + cancel all orders + set ENVIRONMENT_MODE=PASIVO"
              : "continue",
        },
        null,
        2,
      ),
    }
  },
})
