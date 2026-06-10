import { Injectable, OnModuleDestroy, OnModuleInit, Logger } from "@nestjs/common"
import Redis from "ioredis"
import { Candle } from "../../domain/entities/candle"
import { Symbol as SymbolVo } from "../../domain/value-objects/symbol"
import { Timeframe } from "../../domain/value-objects/timeframe"
import { CalculateFeaturesUseCase } from "../../application/use-cases/calculate-features.usecase"

const log = (m: string): void => {
  Logger.log(m, "FeaturePipelineService")
}

interface Subscription {
  stream: string
  symbol: SymbolVo
  timeframe: Timeframe
}

@Injectable()
export class FeaturePipelineService implements OnModuleInit, OnModuleDestroy {
  private client: Redis | null = null
  private timer: ReturnType<typeof setInterval> | null = null
  private readonly buffer = new Map<string, Candle[]>()
  private readonly maxCandles = 100

  private readonly subscriptions: Subscription[] = [
    { stream: "candles:btcusdt:1m", symbol: SymbolVo.parse("BTC/USDT"), timeframe: Timeframe.ONE_MIN },
    { stream: "candles:btcusdt:5m", symbol: SymbolVo.parse("BTC/USDT"), timeframe: Timeframe.FIVE_MIN },
    { stream: "candles:btcusdt:15m", symbol: SymbolVo.parse("BTC/USDT"), timeframe: Timeframe.FIFTEEN_MIN },
    { stream: "candles:btcusdt:1h", symbol: SymbolVo.parse("BTC/USDT"), timeframe: Timeframe.ONE_HOUR },
  ]

  constructor(
    private readonly calculateFeatures: CalculateFeaturesUseCase,
  ) {}

  async onModuleInit(): Promise<void> {
    const url = process.env.ARGOS_BROKER_URL
    if (!url) {
      log("ARGOS_BROKER_URL not set — feature pipeline disabled")
      return
    }
    this.client = new Redis(url, {
      connectTimeout: 2000,
      maxRetriesPerRequest: 1,
      enableOfflineQueue: false,
    })
    this.poll()
    log("started — polling candle streams every 1s")
  }

  async onModuleDestroy(): Promise<void> {
    if (this.timer) {
      clearInterval(this.timer)
      this.timer = null
    }
    if (this.client) {
      try {
        await this.client.quit()
      } catch {
        this.client.disconnect()
      }
      this.client = null
    }
    log("shutdown")
  }

  private poll(): void {
    const lastIds: Record<string, string> = {}
    for (const sub of this.subscriptions) {
      lastIds[sub.stream] = "$"
    }
    this.timer = setInterval(async () => {
      if (!this.client) return
      try {
        for (const sub of this.subscriptions) {
          const blockMs = 100
          const count = 10
          const result = await this.client.xread(
            "COUNT", count,
            "BLOCK", blockMs,
            "STREAMS",
            sub.stream,
            lastIds[sub.stream],
          )
          if (!result) continue
          for (const [, messages] of result) {
            for (const [id, fields] of messages) {
              const tuple = fields as unknown as string[]
              const payload = tuple[tuple.indexOf("p") + 1]
              if (!payload) continue
              try {
                const raw = JSON.parse(payload)
                const candle = Candle.fromJSON(raw)
                if (candle.isComplete) {
                  this.addCandle(sub.symbol, sub.timeframe, candle)
                  await this.calculateFeatures.execute(
                    this.getBuffer(sub.symbol, sub.timeframe),
                  )
                }
              } catch (e) {
                log(`error processing candle: ${(e as Error).message}`)
              }
              lastIds[sub.stream] = id
            }
          }
        }
      } catch (e) {
        log(`poll error: ${(e as Error).message}`)
      }
    }, 1_000)
  }

  private key(symbol: SymbolVo, timeframe: Timeframe): string {
    return `${symbol.value}:${timeframe.toString()}`
  }

  private getBuffer(symbol: SymbolVo, timeframe: Timeframe): Candle[] {
    return this.buffer.get(this.key(symbol, timeframe)) ?? []
  }

  private addCandle(symbol: SymbolVo, timeframe: Timeframe, candle: Candle): void {
    const k = this.key(symbol, timeframe)
    const arr = this.buffer.get(k) ?? []
    arr.push(candle)
    if (arr.length > this.maxCandles) {
      arr.splice(0, arr.length - this.maxCandles)
    }
    this.buffer.set(k, arr)
  }
}
