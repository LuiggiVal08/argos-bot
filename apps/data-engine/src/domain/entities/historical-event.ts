import { FeatureVectorData } from "./feature-vector"

export interface TickData {
  symbol: string
  price: { minor: string; decimals: number }
  quantity: string
  side: "buy" | "sell"
  ts: number
  tradeId: string
}

export interface CandleData {
  symbol: string
  timeframe: string
  open: { minor: string; decimals: number }
  high: { minor: string; decimals: number }
  low: { minor: string; decimals: number }
  close: { minor: string; decimals: number }
  volume: { minor: string; decimals: number }
  openTs: number
  closeTs: number
  isComplete: boolean
}

export type HistoricalEvent =
  | { kind: "tick"; data: TickData }
  | { kind: "candle"; data: CandleData }
  | { kind: "feature"; data: FeatureVectorData }
