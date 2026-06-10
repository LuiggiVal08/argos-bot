import { HistoricalEvent } from "../../domain/entities/historical-event"

export interface EventStore {
  store(event: HistoricalEvent): Promise<void>
  read(
    kind: HistoricalEvent["kind"],
    fromTs: number,
    toTs: number,
  ): AsyncIterable<HistoricalEvent>
}
