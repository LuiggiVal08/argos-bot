import { Injectable, Inject, OnModuleDestroy, OnModuleInit, Logger } from "@nestjs/common"
import Redis from "ioredis"
import { EVENT_STORE } from "../config/tokens"
import { EventStore } from "../../application/ports/event-store.port"
import { TickData, CandleData } from "../../domain/entities/historical-event"
import { FeatureVectorData } from "../../domain/entities/feature-vector"
import { Timeframe } from "../../domain/value-objects/timeframe"

const log = (m: string): void => {
  Logger.log(m, "HistoricalPipelineService")
}

interface StreamSub {
  stream: string
  kind: "tick" | "candle" | "feature"
  parse: (raw: Record<string, unknown>) => {
    tick?: TickData
    candle?: CandleData
    feature?: FeatureVectorData
  }
}

@Injectable()
export class HistoricalPipelineService implements OnModuleInit, OnModuleDestroy {
  private client: Redis | null = null
  private timer: ReturnType<typeof setInterval> | null = null

  private subs: StreamSub[] = [
    {
      stream: "ticks:btcusdt",
      kind: "tick",
      parse: (r) => ({
        tick: r as unknown as TickData,
      }),
    },
    ...Timeframe.ALL.map((tf) => ({
      stream: `candles:btcusdt:${tf}`,
      kind: "candle" as const,
      parse: (r: Record<string, unknown>) => ({
        candle: { ...r, isComplete: true } as unknown as CandleData,
      }),
    })),
    ...Timeframe.ALL.map((tf) => ({
      stream: `features:btcusdt:${tf}`,
      kind: "feature" as const,
      parse: (r: Record<string, unknown>) => ({
        feature: r as unknown as FeatureVectorData,
      }),
    })),
  ]

  constructor(@Inject(EVENT_STORE) private readonly store: EventStore) {}

  async onModuleInit(): Promise<void> {
    const url = process.env.ARGOS_BROKER_URL
    if (!url) {
      log("ARGOS_BROKER_URL not set — historical pipeline disabled")
      return
    }
    this.client = new Redis(url, {
      connectTimeout: 2000,
      maxRetriesPerRequest: 1,
      enableOfflineQueue: false,
    })
    this.poll()
    log("started")
  }

  async onModuleDestroy(): Promise<void> {
    if (this.timer) {
      clearInterval(this.timer)
      this.timer = null
    }
    if (this.client) {
      try { await this.client.quit() } catch { this.client.disconnect() }
      this.client = null
    }
    log("shutdown")
  }

  private poll(): void {
    const lastIds: Record<string, string> = {}
    for (const sub of this.subs) {
      lastIds[sub.stream] = "$"
    }
    this.timer = setInterval(async () => {
      if (!this.client) return
      for (const sub of this.subs) {
        try {
          const res = (await (
            this.client as unknown as {
              xread: (...args: Array<string | number>) => Promise<unknown>
            }
          ).xread(
            "BLOCK", 50,
            "COUNT", 20,
            "STREAMS", sub.stream, lastIds[sub.stream],
          )) as Array<[string, Array<[string, string[]]>]> | null
          if (!res) continue
          for (const [, entries] of res) {
            for (const [id, fields] of entries) {
              lastIds[sub.stream] = id
              const idx = fields.indexOf("p")
              if (idx === -1) continue
              const raw = fields[idx + 1]
              if (!raw) continue
              try {
                const parsed = JSON.parse(raw)
                const { tick, candle, feature } = sub.parse(parsed)
                if (tick) {
                  await this.store.store({ kind: "tick", data: tick })
                } else if (candle) {
                  await this.store.store({ kind: "candle", data: candle })
                } else if (feature) {
                  await this.store.store({ kind: "feature", data: feature })
                }
              } catch (e) {
                log(`error storing event from ${sub.stream}: ${(e as Error).message}`)
              }
            }
          }
        } catch (e) {
          // stream may not exist yet — skip
        }
      }
    }, 2_000)
  }
}
