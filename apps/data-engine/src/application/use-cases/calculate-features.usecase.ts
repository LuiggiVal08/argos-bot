import { Candle } from "../../domain/entities/candle"
import { FeatureCalculator } from "../ports/feature-calculator.port"
import { FeaturePublisher } from "../ports/feature-publisher.port"

export class CalculateFeaturesUseCase {
  constructor(
    private readonly calculator: FeatureCalculator,
    private readonly publisher: FeaturePublisher,
  ) {}

  async execute(candles: Candle[]): Promise<void> {
    if (candles.length < 2) return

    const vector = this.calculator.execute(candles)

    if (vector.size === 0) return

    await this.publisher.publish(vector)
  }
}
