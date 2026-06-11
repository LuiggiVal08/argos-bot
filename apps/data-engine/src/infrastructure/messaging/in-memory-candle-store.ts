import { Symbol } from "../../domain/value-objects/symbol"
import { Timeframe } from "../../domain/value-objects/timeframe"
import { CandleStore, CandleState } from "../../application/ports/candle-store.port"

type Key = string

function key(symbol: Symbol, timeframe: Timeframe): Key {
  return `${symbol.value}::${timeframe.toString()}`
}

export class InMemoryCandleStore implements CandleStore {
  private readonly map = new Map<Key, CandleState>()

  get(symbol: Symbol, timeframe: Timeframe): CandleState | null {
    return this.map.get(key(symbol, timeframe)) ?? null
  }

  set(symbol: Symbol, timeframe: Timeframe, state: CandleState): void {
    this.map.set(key(symbol, timeframe), state)
  }

  remove(symbol: Symbol, timeframe: Timeframe): void {
    this.map.delete(key(symbol, timeframe))
  }

  clear(): void {
    this.map.clear()
  }

  snapshot(): Array<{ symbol: string; timeframe: string; state: CandleState }> {
    const result: Array<{ symbol: string; timeframe: string; state: CandleState }> = []
    for (const [k, state] of this.map) {
      const [sym, tf] = k.split("::")
      result.push({ symbol: sym, timeframe: tf, state })
    }
    return result
  }
}
