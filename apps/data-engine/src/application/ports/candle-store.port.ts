import { Candle } from "../../domain/entities/candle"
import { Symbol } from "../../domain/value-objects/symbol"
import { Timeframe } from "../../domain/value-objects/timeframe"

export interface CandleState {
  current: Candle
  previous: Candle | null
}

export interface CandleStore {
  get(symbol: Symbol, timeframe: Timeframe): CandleState | null
  set(symbol: Symbol, timeframe: Timeframe, state: CandleState): void
  remove(symbol: Symbol, timeframe: Timeframe): void
}
