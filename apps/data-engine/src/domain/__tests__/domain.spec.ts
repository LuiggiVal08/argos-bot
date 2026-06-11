import { Price } from "../value-objects/price"
import { Symbol } from "../value-objects/symbol"
import { StreamName } from "../value-objects/stream-name"
import { Tick } from "../entities/tick"

describe("Symbol", () => {
  it("parses valid BTC/USDT", () => {
    const s = Symbol.parse("btc/usdt")
    expect(s.value).toBe("BTC/USDT")
    expect(s.base).toBe("BTC")
    expect(s.quote).toBe("USDT")
  })

  it("rejects empty", () => {
    expect(() => Symbol.parse("")).toThrow()
  })

  it("rejects malformed", () => {
    expect(() => Symbol.parse("BTC-USDT")).toThrow()
    expect(() => Symbol.parse("BTC")).toThrow()
  })

  it("toStreamId returns concatenated uppercase", () => {
    expect(Symbol.parse("eth/btc").toStreamId()).toBe("ETHBTC")
  })

  it("equals is value-based", () => {
    expect(Symbol.parse("BTC/USDT").equals(Symbol.parse("btc/usdt"))).toBe(true)
    expect(Symbol.parse("BTC/USDT").equals(null)).toBe(false)
  })
})

describe("Price", () => {
  it("parse keeps precision", () => {
    const p = Price.parse("60000.12345678", 8)
    expect(p.minor).toBe(6000012345678n)
    expect(p.toString()).toBe("60000.12345678")
  })

  it("rejects negative", () => {
    expect(() => Price.parse("-1", 8)).toThrow()
  })

  it("rejects non-numeric", () => {
    expect(() => Price.parse("abc", 8)).toThrow()
  })

  it("rejects bad decimals", () => {
    expect(() => Price.ofMinor(1n, 19)).toThrow()
  })

  it("toJSON roundtrips", () => {
    const original = Price.parse("12345.67", 2)
    const back = Price.fromJSON(original.toJSON())
    expect(back.minor).toBe(original.minor)
    expect(back.decimals).toBe(original.decimals)
  })

  it("toNumber is approximate (lossy for very small fractional)", () => {
    expect(Price.parse("60000.00000001", 8).toNumber()).toBeCloseTo(
      60000.00000001,
      6,
    )
  })
})

describe("StreamName", () => {
  it("forTicks builds from Symbol + prefix", () => {
    const s = Symbol.parse("BTC/USDT")
    const sn = StreamName.forTicks(s, "ticks:")
    expect(sn.toString()).toBe("ticks:btcusdt")
  })

  it("rejects prefix without trailing colon", () => {
    expect(() => StreamName.forTicks(Symbol.parse("BTC/USDT"), "ticks")).toThrow()
  })

  it("parse roundtrips", () => {
    const sn = StreamName.forTicks(Symbol.parse("ETH/USDT"), "ticks:")
    expect(StreamName.parse(sn.toString()).equals(sn)).toBe(true)
  })
})

describe("Tick", () => {
  const baseProps = {
    symbol: Symbol.parse("BTC/USDT"),
    price: Price.parse("60000.00", 8),
    quantity: 100000000n,
    side: "buy" as const,
    ts: 1700000000000,
    tradeId: "42",
  }

  it("creates with valid props", () => {
    const t = Tick.create(baseProps)
    expect(t.tradeId).toBe("42")
    expect(t.side).toBe("buy")
  })

  it("rejects zero quantity", () => {
    expect(() => Tick.create({ ...baseProps, quantity: 0n })).toThrow()
  })

  it("rejects negative ts", () => {
    expect(() => Tick.create({ ...baseProps, ts: -1 })).toThrow()
  })

  it("rejects empty tradeId", () => {
    expect(() => Tick.create({ ...baseProps, tradeId: "" })).toThrow()
  })

  it("toJSON roundtrips", () => {
    const t = Tick.create(baseProps)
    const back = Tick.fromJSON(t.toJSON())
    expect(back.tradeId).toBe(t.tradeId)
    expect(back.ts).toBe(t.ts)
    expect(back.price.equals(t.price)).toBe(true)
    expect(back.symbol.equals(t.symbol)).toBe(true)
    expect(back.quantity).toBe(t.quantity)
  })
})
