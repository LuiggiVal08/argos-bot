import { Symbol } from "./symbol"

/**
 * Stream name as it appears in the broker (e.g. `ticks:btcusdt`).
 *
 * Constructed from a Symbol + the configured stream prefix.
 * Domain knows the SHAPE of a tick stream; it does NOT know the
 * broker implementation.
 */
export class StreamName {
  private constructor(public readonly value: string) {}

  static forTicks(symbol: Symbol, prefix: string): StreamName {
    if (!prefix || !prefix.endsWith(":")) {
      throw new Error(
        `StreamName.forTicks: prefix must be non-empty and end with ':', got '${prefix}'`,
      )
    }
    return new StreamName(`${prefix}${symbol.toStreamId().toLowerCase()}`)
  }

  static parse(raw: string): StreamName {
    if (!/^[a-z][a-z0-9_-]*:[a-z0-9_-]+$/.test(raw)) {
      throw new Error(`StreamName.parse: invalid format '${raw}'`)
    }
    return new StreamName(raw)
  }

  toString(): string {
    return this.value
  }

  equals(other: StreamName | null | undefined): boolean {
    return !!other && other.value === this.value
  }
}
