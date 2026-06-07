import {
  Inject,
  Injectable,
  OnModuleDestroy,
  OnModuleInit,
} from "@nestjs/common"
import { ExchangeGateway } from "../../application/ports/exchange-gateway.port"
import { HealthMonitor } from "../../application/ports/health-monitor.port"
import { IngestTickUseCase } from "../../application/use-cases/ingest-tick.usecase"
import { BufferTickUseCase } from "../../application/use-cases/buffer-tick.usecase"
import { HealthMonitorUseCase } from "../../application/use-cases/health-monitor.usecase"
import { BinanceWebSocketAdapter } from "../messaging/binance-websocket.adapter"
import { BusHealthMonitor } from "../messaging/bus-health-monitor"
import { InMemoryTickBuffer } from "../messaging/in-memory-tick-buffer"
import {
  EXCHANGE_GATEWAY,
  HEALTH_MONITOR,
  TICK_BUFFER,
} from "../config/tokens"

const log = (m: string): void => {
  // eslint-disable-next-line no-console
  console.log(m)
}

/**
 * Wires the WS gateway to the use cases. NestJS lifecycle:
 *  - OnModuleInit: start the gateway and the health monitor.
 *  - OnModuleDestroy: orderly shutdown.
 */
@Injectable()
export class TickPipelineService implements OnModuleInit, OnModuleDestroy {
  private pollHandle: NodeJS.Timeout | null = null

  constructor(
    @Inject(EXCHANGE_GATEWAY)
    private readonly exchange: ExchangeGateway,
    private readonly ingest: IngestTickUseCase,
    private readonly bufferUseCase: BufferTickUseCase,
    @Inject(HEALTH_MONITOR)
    private readonly monitor: HealthMonitor,
    private readonly monitorUc: HealthMonitorUseCase,
    @Inject(TICK_BUFFER)
    private readonly tickBuffer: InMemoryTickBuffer,
  ) {}

  async onModuleInit(): Promise<void> {
    log(
      `[pipeline] starting. buffer=${this.tickBuffer.capacity()} monitor=bus`,
    )
    this.monitor.start()
    this.pollHandle = setInterval(() => {
      void this.monitorUc.tick()
    }, 1000)

    await this.exchange.start(async (tick: import("../../domain/entities/tick").Tick) => {
      const r = await this.ingest.execute(tick)
      if (r.buffered) {
        log(
          `[pipeline] tick ${tick.tradeId} buffered (size=${this.tickBuffer.size()})`,
        )
      }
    })
  }

  async onModuleDestroy(): Promise<void> {
    log("[pipeline] shutting down")
    if (this.pollHandle) {
      clearInterval(this.pollHandle)
      this.pollHandle = null
    }
    if (this.monitor instanceof BusHealthMonitor) {
      await this.monitor.stop()
    }
    if (this.exchange instanceof BinanceWebSocketAdapter) {
      await this.exchange.close()
    }
  }
}
