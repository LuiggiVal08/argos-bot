/**
 * Latency benchmark for the tick pipeline (H1 invariant #12: < 2ms p99).
 *
 * Usage:
 *   ARGOS_BROKER_URL=redis://localhost:6379 \
 *     ts-node apps/data-engine/benchmark/xadd-latency.ts [N]
 *
 * Defaults: N=10000 ticks. Measures per-tick end-to-end latency from
 * Tick.create() to MessageBus.publish() returning. p50 / p95 / p99
 * reported; the script exits non-zero if p99 > 2ms.
 */

import { performance } from "perf_hooks"
import { RedisProtocolBus } from "../src/infrastructure/messaging/redis-protocol-bus"
import { Tick } from "../src/domain/entities/tick"
import { Price } from "../src/domain/value-objects/price"
import { Symbol } from "../src/domain/value-objects/symbol"
import { StreamName } from "../src/domain/value-objects/stream-name"

const N = Number(process.argv[2] ?? 10_000)
const URL = process.env.ARGOS_BROKER_URL ?? "redis://localhost:6379"
const STREAM_NAME = `bench:ticks:${process.pid}`
const TARGET_P99_MS = 2.0

async function main(): Promise<void> {
  const bus = new RedisProtocolBus({ url: URL, lazyConnect: true })
  await bus.ping() // connect

  const symbol = Symbol.parse("BTC/USDT")
  const stream = StreamName.forTicks(symbol, "ticks:")
  // We use a different stream than the one in STREAM_NAME; STREAM_NAME
  // is just a prefix for the deletion below.

  const latencies: number[] = []
  for (let i = 0; i < N; i++) {
    const tick = Tick.create({
      symbol,
      price: Price.parse("60000.00", 8),
      quantity: 1n,
      side: "buy",
      ts: Date.now(),
      tradeId: String(i),
    })
    const t0 = performance.now()
    await bus.publish(stream, tick)
    const t1 = performance.now()
    latencies.push(t1 - t0)
  }

  latencies.sort((a, b) => a - b)
  const p = (q: number): number => latencies[Math.floor(q * latencies.length)]
  const p50 = p(0.5)
  const p95 = p(0.95)
  const p99 = p(0.99)
  const max = latencies[latencies.length - 1]

  // eslint-disable-next-line no-console
  console.log(
    `XADD p50=${p50.toFixed(3)}ms p95=${p95.toFixed(3)}ms p99=${p99.toFixed(3)}ms max=${max.toFixed(
      3,
    )}ms (N=${N})`,
  )

  // Best-effort cleanup of the bench stream.
  try {
    const anyClient = bus as unknown as { client: { del: (k: string) => Promise<unknown> } }
    await anyClient.client.del(STREAM_NAME + stream.toString().split(":")[1])
  } catch {
    // ignore
  }
  await bus.close()

  if (p99 > TARGET_P99_MS) {
    // eslint-disable-next-line no-console
    console.error(`FAIL: p99 ${p99.toFixed(3)}ms > target ${TARGET_P99_MS}ms`)
    process.exit(1)
  }
}

main().catch((e) => {
  // eslint-disable-next-line no-console
  console.error("benchmark error:", e)
  process.exit(2)
})
