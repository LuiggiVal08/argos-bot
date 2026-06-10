export enum EventStream {
  TICKS = "ticks",
  CANDLES = "candles",
  FEATURES = "features",
  SIGNALS = "signals",
  ORDERS = "orders",
  POSITIONS = "positions",
  NOTIFICATIONS = "notifications",
  METRICS = "metrics",
}

export function streamName(prefix: EventStream, symbol: string, timeframe?: string): string {
  return timeframe
    ? `${prefix}:${symbol.toLowerCase()}:${timeframe}`
    : `${prefix}:${symbol.toLowerCase()}`
}
