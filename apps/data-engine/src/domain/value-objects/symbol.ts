export class Symbol {
  private constructor(public readonly value: string) {}

  static parse(value: string): Symbol {
    if (!value || typeof value !== "string") {
      throw new Error("Symbol: value must be a non-empty string")
    }
    const upper = value.toUpperCase().trim()
    if (!Symbol.SHAPE.test(upper)) {
      throw new Error(
        `Symbol: invalid format '${value}' (expected e.g. BTC/USDT)`,
      )
    }
    return new Symbol(upper)
  }

  get base(): string {
    return this.value.split("/")[0]
  }

  get quote(): string {
    return this.value.split("/")[1] ?? ""
  }

  /** Stream-friendly form: BTC/USDT -> BTCUSDT */
  toStreamId(): string {
    return this.value.replace("/", "")
  }

  toString(): string {
    return this.value
  }

  equals(other: Symbol | null | undefined): boolean {
    return !!other && other.value === this.value
  }

  private static readonly SHAPE = /^[A-Z0-9]{2,10}\/[A-Z0-9]{2,10}$/
}
