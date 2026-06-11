import { FeatureVector } from "../../domain/entities/feature-vector"

export interface FeaturePublisher {
  publish(vector: FeatureVector): Promise<void>
}
