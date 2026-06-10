import { TechnicalIndicatorCalculator } from "../technical-indicator-calculator"
import { Candle } from "../../../domain/entities/candle"
import { Symbol } from "../../../domain/value-objects/symbol"
import { Timeframe } from "../../../domain/value-objects/timeframe"
import { Price } from "../../../domain/value-objects/price"
import { Volume } from "../../../domain/value-objects/volume"

const btcusdt = Symbol.parse("BTC/USDT")
const tf = Timeframe.ONE_MIN

function makeCandle(
  close: number,
  ts: number,
  high?: number,
  low?: number,
  vol?: number,
): Candle {
  const c = Price.parse(close.toString())
  const h = Price.parse((high ?? close).toString())
  const l = Price.parse((low ?? close).toString())
  return Candle.create({
    symbol: btcusdt,
    timeframe: tf,
    open: c,
    high: h,
    low: l,
    close: c,
    volume: Volume.ofMinor(BigInt((vol ?? 1000) * 1e8), 8),
    openTs: ts,
    closeTs: ts + 60_000,
    isComplete: true,
  })
}

// Generate a bullish series: prices go up steadily
function generateBullishCandles(count: number, startPrice = 50000, step = 10): Candle[] {
  const candles: Candle[] = []
  for (let i = 0; i < count; i++) {
    const p = startPrice + i * step
    const h = p + 5
    const l = p - 3
    candles.push(makeCandle(p, i * 60_000, h, l, 1000 + i * 10))
  }
  return candles
}

describe("TechnicalIndicatorCalculator", () => {
  let calc: TechnicalIndicatorCalculator

  beforeEach(() => {
    calc = new TechnicalIndicatorCalculator()
  })

  it("returns vector with pct_change from 2 candles", () => {
    const candles = [
      makeCandle(50000, 0),
      makeCandle(50100, 60_000),
    ]
    const vector = calc.execute(candles)
    expect(vector.get("pct_change")).toBeCloseTo(0.2, 2)
  })

  it("returns pct_change=0 for flat series", () => {
    const candles = [
      makeCandle(50000, 0),
      makeCandle(50000, 60_000),
    ]
    const vector = calc.execute(candles)
    expect(vector.get("pct_change")).toBeCloseTo(0, 2)
  })

  it("returns vol_sma_20 when enough candles", () => {
    const candles = generateBullishCandles(22)
    const vector = calc.execute(candles)
    expect(vector.get("vol_sma_20")).toBeGreaterThan(0)
  })

  it("returns obv", () => {
    const candles = generateBullishCandles(10)
    const vector = calc.execute(candles)
    expect(vector.get("obv")).toBeGreaterThan(0)
  })

  it("returns ema_9 when >= 9 candles", () => {
    const candles = generateBullishCandles(9)
    const vector = calc.execute(candles)
    expect(vector.get("ema_9")).toBeGreaterThan(0)
  })

  it("skips ema_9 when < 9 candles", () => {
    const candles = generateBullishCandles(8)
    const vector = calc.execute(candles)
    expect(vector.has("ema_9")).toBe(false)
  })

  it("returns ema_21 when >= 21 candles", () => {
    const candles = generateBullishCandles(21)
    const vector = calc.execute(candles)
    expect(vector.get("ema_21")).toBeGreaterThan(0)
  })

  it("returns ema_50 when >= 50 candles", () => {
    const candles = generateBullishCandles(50)
    const vector = calc.execute(candles)
    expect(vector.get("ema_50")).toBeGreaterThan(0)
  })

  it("returns macd when >= 35 candles", () => {
    const candles = generateBullishCandles(40)
    const vector = calc.execute(candles)
    expect(vector.has("macd")).toBe(true)
    expect(vector.has("macd_signal")).toBe(true)
    expect(vector.has("macd_histogram")).toBe(true)
  })

  it("returns rsi_14 when >= 15 candles", () => {
    const candles = generateBullishCandles(15)
    const vector = calc.execute(candles)
    const rsi = vector.get("rsi_14")
    expect(rsi).toBeGreaterThan(50) // bullish series -> RSI > 50
    expect(rsi).toBeLessThanOrEqual(100)
  })

  it("returns rsi_14=100 when consistently up", () => {
    const candles: Candle[] = []
    for (let i = 0; i < 30; i++) {
      const p = 100 + i * 1
      candles.push(makeCandle(p, i * 60_000, p + 1, p - 1))
    }
    const vector = calc.execute(candles)
    expect(vector.get("rsi_14")).toBe(100)
  })

  it("returns rsi_14=0 when consistently down", () => {
    const candles: Candle[] = []
    for (let i = 0; i < 30; i++) {
      const p = 130 - i * 1
      candles.push(makeCandle(p, i * 60_000, p + 1, p - 1))
    }
    const vector = calc.execute(candles)
    expect(vector.get("rsi_14")).toBe(0)
  })

  it("returns atr_14 when >= 15 candles", () => {
    const candles = generateBullishCandles(20, 50000, 10)
    const vector = calc.execute(candles)
    const atr = vector.get("atr_14")
    expect(atr).toBeGreaterThan(0)
    expect(atr).toBeLessThan(50)
  })

  it("returns bbw_20 when >= 20 candles", () => {
    const candles = generateBullishCandles(20)
    const vector = calc.execute(candles)
    const bbw = vector.get("bbw_20")
    expect(bbw).toBeGreaterThan(0)
    expect(bbw).toBeLessThan(1) // reasonable BBW
  })

  it("returns adx_14 when >= 28 candles", () => {
    const candles = generateBullishCandles(30, 50000, 15)
    const vector = calc.execute(candles)
    const adx = vector.get("adx_14")
    expect(adx).toBeGreaterThan(0)
    expect(adx).toBeLessThanOrEqual(100)
  })

  it("adx is higher with strong trend", () => {
    const strongTrend = generateBullishCandles(40, 50000, 100)
    const strongVector = calc.execute(strongTrend)
    const weakCandles: Candle[] = []
    for (let i = 0; i < 40; i++) {
      const p = 50000 + Math.sin(i * 0.5) * 50
      weakCandles.push(makeCandle(p, i * 60_000, p + 10, p - 10))
    }
    const weakVector = calc.execute(weakCandles)
    const strongAdx = strongVector.get("adx_14") ?? 0
    const weakAdx = weakVector.get("adx_14") ?? 0
    expect(strongAdx).toBeGreaterThan(weakAdx)
  })

  it("returns all 11 features with 50+ candles", () => {
    const candles = generateBullishCandles(55)
    const vector = calc.execute(candles)
    const expected = [
      "pct_change",
      "vol_sma_20",
      "obv",
      "ema_9",
      "ema_21",
      "ema_50",
      "macd",
      "macd_signal",
      "macd_histogram",
      "rsi_14",
      "atr_14",
      "adx_14",
      "bbw_20",
    ]
    for (const name of expected) {
      expect(vector.has(name)).toBe(true)
    }
  })

  it("no NaN values when data is sufficient", () => {
    const candles = generateBullishCandles(55)
    const vector = calc.execute(candles)
    expect(vector.isCorrupted).toBe(false)
  })

  it("handles division by zero gracefully (flat price at 0)", () => {
    const candles: Candle[] = []
    for (let i = 0; i < 55; i++) {
      candles.push(makeCandle(0, i * 60_000, 0, 0))
    }
    const vector = calc.execute(candles)
    expect(vector.get("pct_change")).toBe(0)
  })
})
