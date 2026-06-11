import { Candle } from "../../domain/entities/candle"
import { Tick } from "../../domain/entities/tick"
import { Timeframe } from "../../domain/value-objects/timeframe"
import { CandleStore } from "../ports/candle-store.port"
import { CandlePublisher } from "../ports/candle-publisher.port"

export interface PublishedCandle {
  candle: Candle
  timeframe: Timeframe
}

export interface BuildCandlesResult {
  published: PublishedCandle[]
}

export class BuildCandlesUseCase {
  constructor(
    private readonly store: CandleStore,
    private readonly publisher: CandlePublisher,
  ) {}

  async execute(tick: Tick): Promise<BuildCandlesResult> {
    const published: PublishedCandle[] = []

    for (const tf of Timeframe.ALL) {
      const result = await this.processTimeframe(tick, tf)
      published.push(...result)
    }

    return { published }
  }

  private async processTimeframe(
    tick: Tick,
    timeframe: Timeframe,
  ): Promise<PublishedCandle[]> {
    const published: PublishedCandle[] = []
    const state = this.store.get(tick.symbol, timeframe)
    const current = state?.current ?? null
    const windowStart = Candle.windowStartFor(tick, timeframe)

    if (!current || windowStart >= current.closeTs) {
      const prev = current && current.openTs < windowStart ? current : null
      if (prev) {
        const complete = prev.markComplete()
        this.store.set(tick.symbol, timeframe, {
          current: Candle.fromTick(tick, timeframe),
          previous: complete,
        })
        await this.publisher.publishCandle(complete)
        published.push({ candle: complete, timeframe })
      } else {
        this.store.set(tick.symbol, timeframe, {
          current: Candle.fromTick(tick, timeframe),
          previous: null,
        })
      }
    } else {
      const updated = current.withTick(tick)
      this.store.set(tick.symbol, timeframe, {
        current: updated,
        previous: state!.previous,
      })
    }

    return published
  }
}
