import { Price } from "../value-objects/price"
import { Symbol } from "../value-objects/symbol"
import { Timeframe } from "../value-objects/timeframe"
import { Volume } from "../value-objects/volume"
import { Tick } from "./tick"

export interface CandleProps {
  symbol: Symbol
  timeframe: Timeframe
  open: Price
  high: Price
  low: Price
  close: Price
  volume: Volume
  openTs: number
  closeTs: number
  isComplete: boolean
}

export class Candle {
  private constructor(private readonly props: CandleProps) {}

  static create(props: CandleProps): Candle {
    if (props.openTs >= props.closeTs) {
      throw new Error("Candle.create: openTs must be before closeTs")
    }
    return new Candle(props)
  }

  static fromTick(tick: Tick, timeframe: Timeframe): Candle {
    const openTs = Candle.alignTimestamp(tick.ts, timeframe)
    const closeTs = openTs + timeframe.toMilliseconds()
    return new Candle({
      symbol: tick.symbol,
      timeframe,
      open: tick.price,
      high: tick.price,
      low: tick.price,
      close: tick.price,
      volume: Volume.ofMinor(tick.quantity, 8),
      openTs,
      closeTs,
      isComplete: false,
    })
  }

  get symbol(): Symbol {
    return this.props.symbol
  }
  get timeframe(): Timeframe {
    return this.props.timeframe
  }
  get open(): Price {
    return this.props.open
  }
  get high(): Price {
    return this.props.high
  }
  get low(): Price {
    return this.props.low
  }
  get close(): Price {
    return this.props.close
  }
  get volume(): Volume {
    return this.props.volume
  }
  get openTs(): number {
    return this.props.openTs
  }
  get closeTs(): number {
    return this.props.closeTs
  }
  get isComplete(): boolean {
    return this.props.isComplete
  }

  withTick(tick: Tick): Candle {
    const newHigh = tick.price.minor > this.props.high.minor ? tick.price : this.props.high
    const newLow = tick.price.minor < this.props.low.minor ? tick.price : this.props.low
    return new Candle({
      ...this.props,
      high: newHigh,
      low: newLow,
      close: tick.price,
      volume: this.props.volume.add(Volume.ofMinor(tick.quantity, 8)),
    })
  }

  markComplete(): Candle {
    return new Candle({ ...this.props, isComplete: true })
  }

  markIncomplete(): Candle {
    return new Candle({ ...this.props, isComplete: false })
  }

  static belongsToWindow(tick: Tick, candle: Candle): boolean {
    return tick.ts >= candle.props.openTs && tick.ts < candle.props.closeTs
  }

  static windowStartFor(tick: Tick, timeframe: Timeframe): number {
    return Candle.alignTimestamp(tick.ts, timeframe)
  }

  static timeframeFor(tick: Tick, timeframe: Timeframe): Timeframe {
    return timeframe
  }

  private static alignTimestamp(ts: number, tf: Timeframe): number {
    const interval = tf.toMilliseconds()
    return Math.floor(ts / interval) * interval
  }

  equals(other: Candle | null | undefined): boolean {
    if (!other) return false
    return (
      this.props.symbol.equals(other.props.symbol) &&
      this.props.timeframe.equals(other.props.timeframe) &&
      this.props.openTs === other.props.openTs &&
      this.props.closeTs === other.props.closeTs
    )
  }

  toJSON(): {
    symbol: string
    timeframe: string
    open: { minor: string; decimals: number }
    high: { minor: string; decimals: number }
    low: { minor: string; decimals: number }
    close: { minor: string; decimals: number }
    volume: { minor: string; decimals: number }
    openTs: number
    closeTs: number
    isComplete: boolean
  } {
    return {
      symbol: this.props.symbol.value,
      timeframe: this.props.timeframe.toString(),
      open: this.props.open.toJSON(),
      high: this.props.high.toJSON(),
      low: this.props.low.toJSON(),
      close: this.props.close.toJSON(),
      volume: this.props.volume.toJSON(),
      openTs: this.props.openTs,
      closeTs: this.props.closeTs,
      isComplete: this.props.isComplete,
    }
  }

  static fromJSON(raw: ReturnType<Candle["toJSON"]>): Candle {
    return Candle.create({
      symbol: Symbol.parse(raw.symbol),
      timeframe: Timeframe.parse(raw.timeframe),
      open: Price.fromJSON(raw.open),
      high: Price.fromJSON(raw.high),
      low: Price.fromJSON(raw.low),
      close: Price.fromJSON(raw.close),
      volume: Volume.fromJSON(raw.volume),
      openTs: raw.openTs,
      closeTs: raw.closeTs,
      isComplete: raw.isComplete,
    })
  }
}
