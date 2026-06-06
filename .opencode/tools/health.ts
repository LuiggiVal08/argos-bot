import { tool } from "@opencode-ai/plugin"
import { execFileSync } from "child_process"
import { existsSync } from "fs"
import * as path from "path"

const ROOT = process.cwd()

const tryRun = (cmd: string, args: string[]): string => {
  try {
    return execFileSync(cmd, args, {
      encoding: "utf8",
      cwd: ROOT,
      stdio: ["ignore", "pipe", "pipe"],
      timeout: 5000,
    }).trim()
  } catch (e: any) {
    return `[error: ${(e.stderr ?? e.message ?? "").toString().trim() || "command failed"}]`
  }
}

const fileMarkers: { label: string; rel: string }[] = [
  { label: "spec.md", rel: "spec.md" },
  { label: "config.json", rel: "config.json" },
  { label: ".env.example (data-engine)", rel: "apps/data-engine/.env.example" },
  { label: ".env.example (analytics-engine)", rel: "apps/analytics-engine/.env.example" },
  { label: "package.json (data-engine)", rel: "apps/data-engine/package.json" },
  { label: "pyproject.toml (analytics-engine)", rel: "apps/analytics-engine/pyproject.toml" },
  { label: "docker-compose.yml", rel: "docker-compose.yml" },
  { label: ".gitignore", rel: ".gitignore" },
]

export const health_check = tool({
  description:
    "One-shot diagnostic: git status, docker compose ps, redis ping, ENVIRONMENT_MODE, and presence of base files. Markdown-formatted summary.",
  args: {},
  async execute() {
    const out: string[] = []
    out.push("# Argos-bot health check")
    out.push("")

    out.push("## Git")
    out.push("```")
    out.push(tryRun("git", ["status", "--short"]) || "(clean working tree)")
    out.push("```")
    out.push("")

    out.push("## ENVIRONMENT_MODE")
    out.push("```")
    out.push(process.env.ENVIRONMENT_MODE ?? "(unset, default PAPER_TRADING)")
    out.push("```")
    out.push("")

    out.push("## Docker compose services")
    out.push("```")
    out.push(tryRun("docker", ["compose", "ps"]))
    out.push("```")
    out.push("")

    out.push("## Redis ping")
    out.push("```")
    out.push(tryRun("redis-cli", ["ping"]))
    out.push("```")
    out.push("")

    out.push("## Base files")
    for (const m of fileMarkers) {
      const p = path.join(ROOT, m.rel)
      out.push(`- ${existsSync(p) ? "OK" : "MISSING"}  ${m.label}  (${m.rel})`)
    }
    out.push("")

    return { title: "health_check", output: out.join("\n") }
  },
})

export const tick_rate = tool({
  description:
    "Sample XLEN of a Redis stream 5 times over ~2s and report the items/second rate. Use to gauge tick-pipeline backpressure.",
  args: {
    stream: tool.schema.string().describe("Stream name, e.g. ticks:btcusdt"),
    samples: tool.schema
      .number()
      .describe("Number of samples to take")
      .default(5),
    interval_ms: tool.schema
      .number()
      .describe("Delay between samples in milliseconds")
      .default(500),
  },
  async execute({ stream, samples, interval_ms }) {
    const sleep = (ms: number) =>
      new Promise<void>((r) => setTimeout(r, ms))
    const counts: number[] = []
    for (let i = 0; i < samples; i++) {
      const r = tryRun("redis-cli", ["XLEN", stream])
      const n = Number(r.replace(/[^\d-]/g, ""))
      counts.push(Number.isFinite(n) ? n : 0)
      if (i < samples - 1) await sleep(interval_ms)
    }
    const delta = counts[counts.length - 1] - counts[0]
    const elapsedSec = (interval_ms * (samples - 1)) / 1000
    const rate = elapsedSec > 0 ? delta / elapsedSec : 0
    return {
      title: `XLEN ${stream}`,
      output:
        `Samples: ${counts.join(", ")}\n` +
        `Delta: ${delta} items in ${elapsedSec.toFixed(2)}s\n` +
        `Rate: ${rate.toFixed(2)} items/sec`,
    }
  },
})
