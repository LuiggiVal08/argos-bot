import { Injectable, OnModuleDestroy, OnModuleInit, Inject, Logger } from "@nestjs/common"
import { MessageBus } from "../../application/ports/message-bus.port"
import { BuildCandlesUseCase } from "../../application/use-cases/build-candles.usecase"
import { StreamName } from "../../domain/value-objects/stream-name"
import { Tick } from "../../domain/entities/tick"
import { BUS, STREAM_NAME } from "../config/tokens"

const log = (m: string): void => {
  Logger.log(m, "CandlePipelineService")
}

@Injectable()
export class CandlePipelineService implements OnModuleInit, OnModuleDestroy {
  private unsubscribe: (() => Promise<void>) | null = null

  constructor(
    @Inject(BUS) private readonly bus: MessageBus,
    @Inject(STREAM_NAME) private readonly tickStreamName: StreamName,
    private readonly buildCandles: BuildCandlesUseCase,
  ) {}

  async onModuleInit(): Promise<void> {
    this.unsubscribe = await this.bus.subscribe(
      this.tickStreamName,
      async (tick: Tick) => {
        try {
          const result = await this.buildCandles.execute(tick)
          for (const { candle, timeframe } of result.published) {
            log(
              `candle ${candle.symbol} ${timeframe} ` +
                `O=${candle.open.toNumber()} H=${candle.high.toNumber()} ` +
                `L=${candle.low.toNumber()} C=${candle.close.toNumber()} ` +
                `V=${candle.volume.toNumber()} ts=${candle.openTs}`,
            )
          }
        } catch (e) {
          log(`error building candles: ${(e as Error).message}`)
        }
      },
    )
    log(`subscribed to ${this.tickStreamName}`)
  }

  async onModuleDestroy(): Promise<void> {
    if (this.unsubscribe) {
      await this.unsubscribe()
      this.unsubscribe = null
    }
    log("shutdown")
  }
}
