import { Candle } from "../../domain/entities/candle"
import { FeatureVector } from "../../domain/entities/feature-vector"

export interface FeatureCalculator {
  execute(candles: Candle[]): FeatureVector
}
