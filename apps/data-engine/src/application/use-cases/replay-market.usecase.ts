import { EventStore } from "../ports/event-store.port"
import { MessageBus } from "../ports/message-bus.port"
import { StreamName } from "../../domain/value-objects/stream-name"
import { Symbol } from "../../domain/value-objects/symbol"
import { Tick } from "../../domain/entities/tick"

export interface ReplayOptions {
  fromTs: number
  toTs: number
  speed?: number
}

export class ReplayMarketUseCase {
  constructor(
    private readonly store: EventStore,
    private readonly bus: MessageBus,
  ) {}

  async execute(opts: ReplayOptions): Promise<{ ticks: number; candles: number; features: number }> {
    const speed = opts.speed ?? 1
    const counts = { ticks: 0, candles: 0, features: 0 }
    const startWall = Date.now()
    let firstEventTs: number | null = null

    const events: Array<{ ts: number; run: () => Promise<void> }> = []

    for await (const event of this.store.read("tick", opts.fromTs, opts.toTs)) {
      if (event.kind !== "tick") continue
      const ts = event.data.ts
      if (firstEventTs === null) firstEventTs = ts
      events.push({
        ts,
        run: async () => {
          const tick = Tick.fromJSON(event.data)
          const stream = StreamName.forTicks(
            Symbol.parse(event.data.symbol),
            "ticks:",
          )
          await this.bus.publish(stream, tick)
        },
      })
    }
    counts.ticks = events.length

    for await (const event of this.store.read("candle", opts.fromTs, opts.toTs)) {
      if (event.kind !== "candle") continue
      const ts = event.data.closeTs
      if (firstEventTs === null) firstEventTs = ts
      events.push({ ts, run: async () => {} })
    }

    for await (const event of this.store.read("feature", opts.fromTs, opts.toTs)) {
      if (event.kind !== "feature") continue
      const ts = event.data.timestamp
      if (firstEventTs === null) firstEventTs = ts
      events.push({ ts, run: async () => {} })
    }

    events.sort((a, b) => a.ts - b.ts)

    if (firstEventTs === null) return counts

    for (const ev of events) {
      const elapsed = (ev.ts - firstEventTs) / speed
      const now = Date.now() - startWall
      if (elapsed > now) {
        await new Promise<void>((r) => setTimeout(r, elapsed - now))
      }
      await ev.run()
    }

    return counts
  }
}
