import { tool } from "@opencode-ai/plugin"
import { execFileSync } from "child_process"

const isLive = () =>
  (process.env.ENVIRONMENT_MODE ?? "").toUpperCase() === "LIVE"

const redis = (args: string[]) =>
  execFileSync("redis-cli", args, { encoding: "utf8" })

export const redis_get = tool({
  description: "GET a key from the local Redis (data bus + config cache).",
  args: { key: tool.schema.string().describe("Redis key") },
  async execute({ key }) {
    return {
      title: `GET ${key}`,
      output: redis(["GET", key]) || "(nil)",
    }
  },
})

export const redis_set = tool({
  description:
    "SET a key in the local Redis. Refuses silently destructive keys when ENVIRONMENT_MODE=LIVE; always asks the user.",
  args: {
    key: tool.schema.string().describe("Redis key"),
    value: tool.schema.string().describe("Value to store"),
  },
  async execute({ key, value }, ctx) {
    const destructivePattern = /^(ticks:|orders:|positions:)/
    if (isLive() && destructivePattern.test(key)) {
      await ctx.ask({
        permission: "redis_set on LIVE mode (destructive key)",
        patterns: [key],
        always: [],
        metadata: { key, value },
      })
    }
    return {
      title: `SET ${key}`,
      output: redis(["SET", key, value]),
    }
  },
})

export const redis_xlen = tool({
  description:
    "XLEN of a stream. Use to monitor tick-pipeline backpressure.",
  args: {
    stream: tool.schema
      .string()
      .describe("Stream name, e.g. ticks:btcusdt"),
  },
  async execute({ stream }) {
    return {
      title: `XLEN ${stream}`,
      output: redis(["XLEN", stream]),
    }
  },
})

export const redis_flush = tool({
  description:
    "FLUSHDB. Always asks the user, and refuses outright when ENVIRONMENT_MODE=LIVE.",
  args: {},
  async execute(_args, ctx) {
    await ctx.ask({
      permission: "redis_flush (destructive)",
      patterns: ["*"],
      always: [],
      metadata: {},
    })
    if (isLive())
      return {
        title: "Blocked",
        output:
          "Refused: FLUSHDB is not allowed when ENVIRONMENT_MODE=LIVE.",
      }
    return { title: "FLUSHDB", output: redis(["FLUSHDB"]) }
  },
})
