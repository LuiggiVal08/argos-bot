import WebSocket from "ws"
import { Tick } from "../../domain/entities/tick"
import {
  ExchangeConnectionState,
  ExchangeGateway,
} from "../../application/ports/exchange-gateway.port"
import {
  BinanceTradeEvent,
  tickFromBinanceTrade,
} from "./in-memory-tick-buffer"

export interface BinanceWebSocketAdapterOptions {
  /**
   * Binance combined-stream URL. For `btcusdt` trade stream:
   *   wss://stream.binance.com:9443/stream?streams=btcusdt@trade
   * Default points to the public mainnet endpoint.
   */
  url?: string
  /** Ping interval (ms) to keep the connection alive. Default 30000. */
  pingIntervalMs?: number
  /** Reconnect delay (ms) on unexpected close. Default 1000. */
  reconnectDelayMs?: number
  /** Optional logger; if absent, falls back to console. */
  logger?: (msg: string) => void
}

const DEFAULT_URL =
  "wss://stream.binance.com:9443/stream?streams=btcusdt@trade"

/**
 * ExchangeGateway adapter for Binance public market data.
 *
 * Subscribes to one or more combined streams using the
 * `wss://stream.binance.com:9443/stream?streams=...` endpoint and
 * invokes the onTick handler for every trade event.
 *
 * No auth, no trading. Read-only public market data.
 *
 * Lifecycle:
 *  - start(): open WS, begin receiving events.
 *  - close(): orderly close (close frame 1000), no reconnect.
 *  - state(): snapshot of the connection state.
 *
 * The 10s sad-path cutoff is NOT enforced here — that's
 * HealthMonitorUseCase's responsibility, which calls exchange.close().
 */
export class BinanceWebSocketAdapter implements ExchangeGateway {
  private ws: WebSocket | null = null
  private connState: ExchangeConnectionState = "idle"
  private pingTimer: NodeJS.Timeout | null = null
  private readonly log: (msg: string) => void
  private readonly opts: Required<Omit<BinanceWebSocketAdapterOptions, "logger">>

  constructor(opts: BinanceWebSocketAdapterOptions = {}) {
    this.opts = {
      url: opts.url ?? DEFAULT_URL,
      pingIntervalMs: opts.pingIntervalMs ?? 30000,
      reconnectDelayMs: opts.reconnectDelayMs ?? 1000,
    }
    this.log =
      opts.logger ??
      // eslint-disable-next-line no-console
      ((m) => console.log(`[binance-ws] ${m}`))
  }

  async start(onTick: (tick: Tick) => Promise<void>): Promise<void> {
    if (this.connState === "open" || this.connState === "connecting") {
      this.log(`start() ignored — already ${this.connState}`)
      return
    }
    this.connState = "connecting"
    await this.open(onTick)
  }

  private async open(onTick: (tick: Tick) => Promise<void>): Promise<void> {
    await new Promise<void>((resolve, reject) => {
      const ws = new WebSocket(this.opts.url)
      this.ws = ws
      ws.once("open", () => {
        this.connState = "open"
        this.log("connection open")
        this.pingTimer = setInterval(
          () => ws.ping(),
          this.opts.pingIntervalMs,
        )
        resolve()
      })
      ws.once("error", (err) => {
        this.log(`error: ${err.message}`)
        reject(err)
      })
      ws.on("message", (data) => {
        try {
          const msg = JSON.parse(data.toString("utf8")) as {
            stream?: string
            data?: BinanceTradeEvent
          }
          const trade = msg.data
          if (!trade || trade.e !== "trade") return
          const tick = tickFromBinanceTrade(trade)
          void onTick(tick)
        } catch (e) {
          this.log(`parse error: ${(e as Error).message}`)
        }
      })
      ws.on("close", (code, reason) => {
        this.log(`closed code=${code} reason=${reason.toString()}`)
        this.connState = "closed"
        if (this.pingTimer) {
          clearInterval(this.pingTimer)
          this.pingTimer = null
        }
        this.ws = null
      })
    })
  }

  async close(): Promise<void> {
    if (this.connState === "closed" || this.connState === "idle") return
    this.log("close() — sending close frame 1000")
    const ws = this.ws
    if (this.pingTimer) {
      clearInterval(this.pingTimer)
      this.pingTimer = null
    }
    if (ws) {
      try {
        ws.close(1000, "orderly-shutdown")
      } catch {
        ws.terminate()
      }
    }
    this.connState = "closed"
    this.ws = null
  }

  state(): ExchangeConnectionState {
    return this.connState
  }
}
