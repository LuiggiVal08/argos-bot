import { Symbol } from "../value-objects/symbol"
import { Timeframe } from "../value-objects/timeframe"

export interface FeatureVectorData {
  symbol: string
  timeframe: string
  timestamp: number
  features: Record<string, number>
}

export class FeatureVector {
  private constructor(
    public readonly symbol: Symbol,
    public readonly timeframe: Timeframe,
    public readonly timestamp: number,
    private readonly features: ReadonlyMap<string, number>,
  ) {}

  static create(
    symbol: Symbol,
    timeframe: Timeframe,
    timestamp: number,
  ): FeatureVector {
    return new FeatureVector(symbol, timeframe, timestamp, new Map())
  }

  add(name: string, value: number): FeatureVector {
    if (typeof value !== "number" || !Number.isFinite(value)) {
      throw new Error(
        `FeatureVector.add: ${name} value must be finite, got ${value}`,
      )
    }
    const map = new Map(this.features)
    map.set(name, value)
    return new FeatureVector(this.symbol, this.timeframe, this.timestamp, map)
  }

  has(name: string): boolean {
    return this.features.has(name)
  }

  get(name: string): number | undefined {
    return this.features.get(name)
  }

  get size(): number {
    return this.features.size
  }

  get names(): string[] {
    return Array.from(this.features.keys())
  }

  get isCorrupted(): boolean {
    for (const v of this.features.values()) {
      if (!Number.isFinite(v)) return true
    }
    return false
  }

  toJSON(): FeatureVectorData {
    const obj: Record<string, number> = {}
    for (const [k, v] of this.features) {
      obj[k] = v
    }
    return {
      symbol: this.symbol.value,
      timeframe: this.timeframe.toString(),
      timestamp: this.timestamp,
      features: obj,
    }
  }

  static fromJSON(raw: FeatureVectorData): FeatureVector {
    const symbol = Symbol.parse(raw.symbol)
    const timeframe = Timeframe.parse(raw.timeframe)
    const map = new Map(Object.entries(raw.features))
    return new FeatureVector(symbol, timeframe, raw.timestamp, map)
  }
}
