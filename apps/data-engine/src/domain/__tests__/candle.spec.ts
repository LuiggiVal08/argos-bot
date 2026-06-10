import { Timeframe } from "../value-objects/timeframe"
import { Volume } from "../value-objects/volume"
import { Candle } from "../entities/candle"
import { Tick } from "../entities/tick"
import { Price } from "../value-objects/price"
import { Symbol } from "../value-objects/symbol"

describe("Timeframe", () => {
  it("parses valid timeframes", () => {
    expect(Timeframe.parse("1m").toString()).toBe("1m")
    expect(Timeframe.parse("5m").toString()).toBe("5m")
    expect(Timeframe.parse("15m").toString()).toBe("15m")
    expect(Timeframe.parse("1h").toString()).toBe("1h")
  })

  it("rejects invalid format", () => {
    expect(() => Timeframe.parse("1d")).toThrow()
    expect(() => Timeframe.parse("abc")).toThrow()
    expect(() => Timeframe.parse("")).toThrow()
  })

  it("toMilliseconds returns correct values", () => {
    expect(Timeframe.ONE_MIN.toMilliseconds()).toBe(60_000)
    expect(Timeframe.FIVE_MIN.toMilliseconds()).toBe(300_000)
    expect(Timeframe.FIFTEEN_MIN.toMilliseconds()).toBe(900_000)
    expect(Timeframe.ONE_HOUR.toMilliseconds()).toBe(3_600_000)
  })

  it("ALL contains all timeframes in order", () => {
    expect(Timeframe.ALL.map((t) => t.toString())).toEqual(["1m", "5m", "15m", "1h"])
  })

  it("equals is value-based", () => {
    expect(Timeframe.ONE_MIN.equals(Timeframe.parse("1m"))).toBe(true)
    expect(Timeframe.ONE_MIN.equals(Timeframe.FIVE_MIN)).toBe(false)
    expect(Timeframe.ONE_MIN.equals(null)).toBe(false)
  })
})

describe("Volume", () => {
  it("creates zero volume", () => {
    const v = Volume.zero()
    expect(v.toNumber()).toBe(0)
  })

  it("adds volumes with different decimals", () => {
    const a = Volume.ofMinor(1000n, 8)
    const b = Volume.ofMinor(2000n, 8)
    const sum = a.add(b)
    expect(sum.toNumber()).toBe(0.00003)
  })

  it("equals is value-based", () => {
    expect(Volume.ofMinor(100n, 8).equals(Volume.ofMinor(100n, 8))).toBe(true)
    expect(Volume.ofMinor(100n, 8).equals(Volume.ofMinor(101n, 8))).toBe(false)
  })

  it("roundtrips through JSON", () => {
    const v = Volume.ofMinor(123456789n, 8)
    const json = v.toJSON()
    expect(Volume.fromJSON(json).equals(v)).toBe(true)
  })
})

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

const btcusdt = Symbol.parse("BTC/USDT")

describe("Candle", () => {
  it("creates from first tick", () => {
    const tick = makeTick(btcusdt, "60000.00", "100000000", 0)
    const candle = Candle.fromTick(tick, Timeframe.ONE_MIN)
    expect(candle.symbol.equals(btcusdt)).toBe(true)
    expect(candle.timeframe.equals(Timeframe.ONE_MIN)).toBe(true)
    expect(candle.open.toNumber()).toBe(60000)
    expect(candle.high.toNumber()).toBe(60000)
    expect(candle.low.toNumber()).toBe(60000)
    expect(candle.close.toNumber()).toBe(60000)
    expect(candle.volume.toNumber()).toBe(1)
    expect(candle.openTs).toBe(0)
    expect(candle.closeTs).toBe(60_000)
    expect(candle.isComplete).toBe(false)
  })

  it("updates with subsequent tick", () => {
    const t1 = makeTick(btcusdt, "60000.00", "100000000", 1000)
    const t2 = makeTick(btcusdt, "60100.00", "200000000", 2000)
    const t3 = makeTick(btcusdt, "59900.00", "50000000", 3000)

    let candle = Candle.fromTick(t1, Timeframe.ONE_MIN)
    candle = candle.withTick(t2)
    candle = candle.withTick(t3)

    expect(candle.open.toNumber()).toBe(60000)
    expect(candle.high.toNumber()).toBe(60100)
    expect(candle.low.toNumber()).toBe(59900)
    expect(candle.close.toNumber()).toBe(59900)
    expect(candle.volume.toNumber()).toBe(3.5)
  })

  it("aligns timestamp to timeframe boundary", () => {
    const tick = makeTick(btcusdt, "60000.00", "100000000", 65_000)
    const candle = Candle.fromTick(tick, Timeframe.ONE_MIN)
    expect(candle.openTs).toBe(60_000)
    expect(candle.closeTs).toBe(120_000)
  })

  it("detects if tick belongs to window", () => {
    const tick = makeTick(btcusdt, "60000.00", "100000000", 30_000)
    const candle = Candle.fromTick(tick, Timeframe.ONE_MIN)
    const later = makeTick(btcusdt, "60100.00", "100000000", 90_000)
    expect(Candle.belongsToWindow(later, candle)).toBe(false)
    const same = makeTick(btcusdt, "60100.00", "100000000", 45_000)
    expect(Candle.belongsToWindow(same, candle)).toBe(true)
  })

  it("windowStartFor returns correct boundary", () => {
    const tick = makeTick(btcusdt, "60000.00", "100000000", 125_000)
    expect(Candle.windowStartFor(tick, Timeframe.ONE_MIN)).toBe(120_000)
    expect(Candle.windowStartFor(tick, Timeframe.FIVE_MIN)).toBe(0)
    expect(Candle.windowStartFor(tick, Timeframe.ONE_HOUR)).toBe(0)
  })

  it("markComplete toggles flag", () => {
    const tick = makeTick(btcusdt, "60000.00", "100000000", 0)
    const candle = Candle.fromTick(tick, Timeframe.ONE_MIN)
    expect(candle.isComplete).toBe(false)
    expect(candle.markComplete().isComplete).toBe(true)
    expect(candle.isComplete).toBe(false)
  })

  it("roundtrips through JSON", () => {
    const tick = makeTick(btcusdt, "60000.12345678", "123456789", 42_000)
    const candle = Candle.fromTick(tick, Timeframe.ONE_MIN)
    const json = candle.toJSON()
    const restored = Candle.fromJSON(json)
    expect(restored.equals(candle)).toBe(true)
    expect(restored.open.toNumber()).toBe(candle.open.toNumber())
    expect(restored.high.toNumber()).toBe(candle.high.toNumber())
    expect(restored.low.toNumber()).toBe(candle.low.toNumber())
    expect(restored.close.toNumber()).toBe(candle.close.toNumber())
    expect(restored.volume.toNumber()).toBe(candle.volume.toNumber())
    expect(restored.openTs).toBe(candle.openTs)
    expect(restored.closeTs).toBe(candle.closeTs)
    expect(restored.isComplete).toBe(candle.isComplete)
  })

  it("rejects invalid openTs >= closeTs", () => {
    const tick = makeTick(btcusdt, "60000.00", "100000000", 0)
    const candle = Candle.fromTick(tick, Timeframe.ONE_MIN)
    expect(() =>
      Candle.create({
        ...candle["props"],
        openTs: 100,
        closeTs: 50,
      }),
    ).toThrow()
  })
})
