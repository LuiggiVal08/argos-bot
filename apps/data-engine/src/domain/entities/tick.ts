import { Price } from "../value-objects/price"
import { Symbol } from "../value-objects/symbol"

export type TickSide = "buy" | "sell"

export interface TickProps {
  symbol: Symbol
  price: Price
  quantity: bigint
  side: TickSide
  /** Exchange event time, ms since epoch. */
  ts: number
  /** Exchange trade id (string to support numeric + alphanumeric). */
  tradeId: string
}

/**
 * One market event emitted by the exchange WebSocket.
 *
 * Immutable. Constructed via `Tick.create()` which performs validation
 * (no NaN, no negative quantity, no future timestamp, no empty tradeId).
 */
export class Tick {
  private constructor(private readonly props: TickProps) {}

  static create(props: TickProps): Tick {
    if (props.quantity <= 0n) {
      throw new Error("Tick.create: quantity must be positive")
    }
    if (!Number.isFinite(props.ts) || props.ts < 0) {
      throw new Error("Tick.create: ts must be a non-negative finite number")
    }
    if (!props.tradeId) {
      throw new Error("Tick.create: tradeId is required")
    }
    return new Tick(props)
  }

  get symbol(): Symbol {
    return this.props.symbol
  }
  get price(): Price {
    return this.props.price
  }
  get quantity(): bigint {
    return this.props.quantity
  }
  get side(): TickSide {
    return this.props.side
  }
  get ts(): number {
    return this.props.ts
  }
  get tradeId(): string {
    return this.props.tradeId
  }

  /** JSON-safe representation (Price is serialized as {minor, decimals}). */
  toJSON(): {
    symbol: string
    price: { minor: string; decimals: number }
    quantity: string
    side: TickSide
    ts: number
    tradeId: string
  } {
    return {
      symbol: this.props.symbol.value,
      price: this.props.price.toJSON(),
      quantity: this.props.quantity.toString(),
      side: this.props.side,
      ts: this.props.ts,
      tradeId: this.props.tradeId,
    }
  }

  static fromJSON(raw: ReturnType<Tick["toJSON"]>): Tick {
    return Tick.create({
      symbol: Symbol.parse(raw.symbol),
      price: Price.fromJSON(raw.price),
      quantity: BigInt(raw.quantity),
      side: raw.side,
      ts: raw.ts,
      tradeId: raw.tradeId,
    })
  }
}
