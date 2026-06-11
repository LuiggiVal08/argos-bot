import { BuildCandlesUseCase } from "../use-cases/build-candles.usecase"
import { CandleStore } from "../ports/candle-store.port"
import { CandlePublisher } from "../ports/candle-publisher.port"
import { Candle } from "../../domain/entities/candle"
import { Tick } from "../../domain/entities/tick"
import { Price } from "../../domain/value-objects/price"
import { Symbol } from "../../domain/value-objects/symbol"
import { Timeframe } from "../../domain/value-objects/timeframe"

function makeTick(symbol: Symbol, price: string, qty: string, ts: number): Tick {
  return Tick.create({
    symbol,
    price: Price.parse(price, 8),
    quantity: BigInt(qty),
    side: "buy",
    ts,
    tradeId: String(ts),
  })
}

class MockCandleStore implements CandleStore {
  private data = new Map<string, { current: Candle; previous: Candle | null }>()

  get(symbol: Symbol, timeframe: Timeframe) {
    const k = `${symbol.value}::${timeframe}`
    return this.data.get(k) ?? null
  }

  set(symbol: Symbol, timeframe: Timeframe, state: { current: Candle; previous: Candle | null }) {
    const k = `${symbol.value}::${timeframe}`
    this.data.set(k, state)
  }

  remove(symbol: Symbol, timeframe: Timeframe) {
    const k = `${symbol.value}::${timeframe}`
    this.data.delete(k)
  }

  clear() {
    this.data.clear()
  }
}

class MockCandlePublisher implements CandlePublisher {
  public published: Candle[] = []

  async publishCandle(candle: Candle): Promise<void> {
    this.published.push(candle)
  }

  reset() {
    this.published = []
  }
}

const btcusdt = Symbol.parse("BTC/USDT")

describe("BuildCandlesUseCase", () => {
  let store: MockCandleStore
  let publisher: MockCandlePublisher
  let useCase: BuildCandlesUseCase

  beforeEach(() => {
    store = new MockCandleStore()
    publisher = new MockCandlePublisher()
    useCase = new BuildCandlesUseCase(store, publisher)
  })

  it("creates initial candle on first tick — no publish", async () => {
    const tick = makeTick(btcusdt, "60000.00", "100000000", 0)
    const result = await useCase.execute(tick)

    expect(result.published).toHaveLength(0)
    expect(publisher.published).toHaveLength(0)
  })

  it("publishes completed candle when tick crosses window boundary", async () => {
    const t1 = makeTick(btcusdt, "60000.00", "100000000", 0)
    await useCase.execute(t1)

    const t2 = makeTick(btcusdt, "60500.00", "200000000", 61_000)
    const _result = await useCase.execute(t2)

    const published = _result.published.filter((p) => p.timeframe.equals(Timeframe.ONE_MIN))
    expect(published).toHaveLength(1)

    const candle = published[0].candle
    expect(candle.open.toNumber()).toBe(60000)
    expect(candle.high.toNumber()).toBe(60000)
    expect(candle.low.toNumber()).toBe(60000)
    expect(candle.close.toNumber()).toBe(60000)
    expect(candle.isComplete).toBe(true)
    expect(candle.openTs).toBe(0)
    expect(candle.closeTs).toBe(60_000)
  })

  it("builds candles for all timeframes", async () => {
    const tick = makeTick(btcusdt, "60000.00", "100000000", 0)
    await useCase.execute(tick)

    for (const tf of Timeframe.ALL) {
      const state = store.get(btcusdt, tf)
      expect(state).not.toBeNull()
      expect(state!.current.timeframe.equals(tf)).toBe(true)
    }
  })

  it("publishes 1m candle at 61s, 5m at 301s, 15m at 901s, 1h at 3601s", async () => {
    for (let ts = 0; ts <= 3_602_000; ts += 1_000) {
      const tick = makeTick(btcusdt, String(60000 + Math.random() * 100), "100000000", ts)
      await useCase.execute(tick)
    }

    const byTf = (tf: string) =>
      publisher.published.filter((c) => c.timeframe.toString() === tf)

    expect(byTf("1m").length).toBeGreaterThanOrEqual(59)
    expect(byTf("5m").length).toBeGreaterThanOrEqual(11)
    expect(byTf("15m").length).toBeGreaterThanOrEqual(3)
    expect(byTf("1h").length).toBeGreaterThanOrEqual(1)
  })

  it("publishes 5m candle when 1m candles cross 5m boundary", async () => {
    for (let ts = 0; ts < 360_000; ts += 10_000) {
      const tick = makeTick(btcusdt, String(60000 + Math.random() * 100), "100000000", ts)
      await useCase.execute(tick)
    }

    const tfCounts: Record<string, number> = {}
    for (const p of publisher.published) {
      const key = p.timeframe.toString()
      tfCounts[key] = (tfCounts[key] ?? 0) + 1
    }

    expect(tfCounts["1m"]).toBeGreaterThanOrEqual(5)
    expect(tfCounts["5m"]).toBeGreaterThanOrEqual(1)
  })

  it("updates candle in same window without publishing", async () => {
    const t1 = makeTick(btcusdt, "60000.00", "100000000", 10_000)
    const t2 = makeTick(btcusdt, "60100.00", "100000000", 20_000)
    const t3 = makeTick(btcusdt, "59900.00", "100000000", 30_000)

    await useCase.execute(t1)
    await useCase.execute(t2)
    await useCase.execute(t3)

    const state = store.get(btcusdt, Timeframe.ONE_MIN)
    expect(state).not.toBeNull()
    expect(state!.current.high.toNumber()).toBe(60100)
    expect(state!.current.low.toNumber()).toBe(59900)
    expect(state!.current.close.toNumber()).toBe(59900)
    expect(state!.current.volume.toNumber()).toBe(3)
  })
})
