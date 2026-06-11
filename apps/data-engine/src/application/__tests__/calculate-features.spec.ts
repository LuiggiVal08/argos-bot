import { CalculateFeaturesUseCase } from "../use-cases/calculate-features.usecase"
import { FeatureCalculator } from "../ports/feature-calculator.port"
import { FeaturePublisher } from "../ports/feature-publisher.port"
import { Candle } from "../../domain/entities/candle"
import { Symbol } from "../../domain/value-objects/symbol"
import { Timeframe } from "../../domain/value-objects/timeframe"
import { Price } from "../../domain/value-objects/price"
import { Volume } from "../../domain/value-objects/volume"
import { FeatureVector } from "../../domain/entities/feature-vector"

const btcusdt = Symbol.parse("BTC/USDT")
const tf = Timeframe.ONE_MIN

function makeCandle(
  close: number,
  ts: number,
  high?: number,
  low?: number,
  vol?: number,
): Candle {
  const p = Price.parse(close.toString())
  const h = Price.parse((high ?? close).toString())
  const l = Price.parse((low ?? close).toString())
  return Candle.create({
    symbol: btcusdt,
    timeframe: tf,
    open: p,
    high: h,
    low: l,
    close: p,
    volume: Volume.ofMinor(BigInt((vol ?? 1000) * 1e8), 8),
    openTs: ts,
    closeTs: ts + 60_000,
    isComplete: true,
  })
}

class FakeCalculator implements FeatureCalculator {
  calledWith: Candle[][] = []
  result: FeatureVector = FeatureVector.create(btcusdt, tf, 0)

  execute(candles: Candle[]): FeatureVector {
    this.calledWith.push(candles)
    return this.result
  }
}

class FakePublisher implements FeaturePublisher {
  published: FeatureVector[] = []

  async publish(vector: FeatureVector): Promise<void> {
    this.published.push(vector)
  }
}

describe("CalculateFeaturesUseCase", () => {
  let calculator: FakeCalculator
  let publisher: FakePublisher
  let useCase: CalculateFeaturesUseCase

  beforeEach(() => {
    calculator = new FakeCalculator()
    publisher = new FakePublisher()
    useCase = new CalculateFeaturesUseCase(calculator, publisher)
  })

  it("skips when fewer than 2 candles", async () => {
    await useCase.execute([makeCandle(60000, 0)])
    expect(calculator.calledWith).toHaveLength(0)
    expect(publisher.published).toHaveLength(0)
  })

  it("publishes when calculator returns a valid vector", async () => {
    const vector = FeatureVector.create(btcusdt, tf, 60_000)
      .add("rsi_14", 42)
      .add("ema_9", 60000)
    calculator.result = vector

    const candles = [
      makeCandle(60000, 0),
      makeCandle(60100, 60_000),
    ]
    await useCase.execute(candles)

    expect(publisher.published).toHaveLength(1)
    expect(publisher.published[0].get("rsi_14")).toBe(42)
    expect(publisher.published[0].get("ema_9")).toBe(60000)
  })

  it("skips publish when vector is empty", async () => {
    calculator.result = FeatureVector.create(btcusdt, tf, 60_000)

    const candles = [
      makeCandle(60000, 0),
      makeCandle(60100, 60_000),
    ]
    await useCase.execute(candles)

    expect(publisher.published).toHaveLength(0)
  })
})
