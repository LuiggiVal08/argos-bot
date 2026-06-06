import { tool } from "@opencode-ai/plugin"
import { readFileSync, writeFileSync, existsSync } from "fs"
import * as path from "path"

const CFG = path.join(process.cwd(), "config.json")

export const read_config = tool({
  description:
    "Read config.json at the project root, or report that it does not exist yet.",
  args: {},
  async execute() {
    if (!existsSync(CFG))
      return {
        title: "config.json missing",
        output:
          "No config.json at project root. Create one with { environment_mode, risk_pct, drawdown_pct, exchanges: [...] }.",
      }
    return { title: "config.json", output: readFileSync(CFG, "utf8") }
  },
})

export const toggle_mode = tool({
  description:
    "Switch ENVIRONMENT_MODE between BACKTESTING, PAPER_TRADING, and LIVE. LIVE always asks and verifies required secret env vars (spec section 5 Historia 5 sad path).",
  args: {
    mode: tool.schema
      .string()
      .describe("BACKTESTING | PAPER_TRADING | LIVE"),
  },
  async execute({ mode }, ctx) {
    const upper = mode.toUpperCase()
    if (!["BACKTESTING", "PAPER_TRADING", "LIVE"].includes(upper))
      return { title: "Invalid mode", output: `Unknown mode: ${mode}` }

    if (upper === "LIVE") {
      const required = [
        "EXCHANGE_API_KEY",
        "EXCHANGE_API_SECRET",
        "EXCHANGE_PASSPHRASE",
      ]
      const missing = required.filter((k) => !process.env[k])
      if (missing.length)
        return {
          title: "Missing secrets",
          output: `Refused: missing env vars ${missing.join(", ")} (spec section 5 Historia 5 sad path).`,
        }
      await ctx.ask({
        permission: "Switch to LIVE mode",
        patterns: ["ENVIRONMENT_MODE=LIVE"],
        always: [],
        metadata: { missing: [] },
      })
    }

    const cfg = existsSync(CFG)
      ? JSON.parse(readFileSync(CFG, "utf8"))
      : {}
    cfg.environment_mode = upper
    writeFileSync(CFG, JSON.stringify(cfg, null, 2))
    return {
      title: `ENVIRONMENT_MODE=${upper}`,
      output: `Updated. Current mode: ${upper}`,
    }
  },
})
