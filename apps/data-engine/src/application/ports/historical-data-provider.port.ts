import { Candle } from "../../domain/entities/candle"
import { Symbol } from "../../domain/value-objects/symbol"
import { Timeframe } from "../../domain/value-objects/timeframe"

export interface HistoricalDataProvider {
  fetchCandles(
    symbol: Symbol,
    timeframe: Timeframe,
    fromTs: number,
    toTs: number,
  ): Promise<Candle[]>
}
