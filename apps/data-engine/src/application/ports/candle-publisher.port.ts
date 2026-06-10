import { Candle } from "../../domain/entities/candle"

export interface CandlePublisher {
  publishCandle(candle: Candle): Promise<void>
}
