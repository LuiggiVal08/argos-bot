import { Module, Provider } from "@nestjs/common"
import { ConfigModule } from "@nestjs/config"
import { HealthController } from "./infrastructure/http/health.controller"
import { HealthControllerBus } from "./infrastructure/http/health-bus.controller"
import {
  BUS,
  EXCHANGE_GATEWAY,
  HEALTH_MONITOR,
  STREAM_NAME,
  TICK_BUFFER,
} from "./infrastructure/config/tokens"
import { RedisProtocolBus } from "./infrastructure/messaging/redis-protocol-bus"
import { BinanceWebSocketAdapter } from "./infrastructure/messaging/binance-websocket.adapter"
import { InMemoryTickBuffer } from "./infrastructure/messaging/in-memory-tick-buffer"
import { BusHealthMonitor } from "./infrastructure/messaging/bus-health-monitor"
import { Symbol } from "./domain/value-objects/symbol"
import { StreamName } from "./domain/value-objects/stream-name"
import { IngestTickUseCase } from "./application/use-cases/ingest-tick.usecase"
import { BufferTickUseCase } from "./application/use-cases/buffer-tick.usecase"
import { FlushBufferUseCase } from "./application/use-cases/flush-buffer.usecase"
import { HealthMonitorUseCase } from "./application/use-cases/health-monitor.usecase"
import { NotificationConsumer } from "./infrastructure/notification/notification-consumer"
import { TickPipelineService } from "./infrastructure/services/tick-pipeline.service"

const log = (m: string): void => {
  // eslint-disable-next-line no-console
  console.log(m)
}

const streamNameProvider: Provider = {
  provide: STREAM_NAME,
  useFactory: (): StreamName => {
    const symbol = process.env.SYMBOL ?? "BTC/USDT"
    const prefix = process.env.STREAM_PREFIX ?? "ticks:"
    return StreamName.forTicks(Symbol.parse(symbol), prefix)
  },
}

const busProvider: Provider = {
  provide: BUS,
  useFactory: (): RedisProtocolBus => {
    const url = process.env.ARGOS_BROKER_URL
    if (!url) {
      throw new Error(
        "AppModule: ARGOS_BROKER_URL is required (set in .env or environment)",
      )
    }
    return new RedisProtocolBus({ url })
  },
}

const tickBufferProvider: Provider = {
  provide: TICK_BUFFER,
  useFactory: (): InMemoryTickBuffer => {
    const cap = Number(process.env.TICK_BUFFER_CAP ?? 100)
    return new InMemoryTickBuffer(cap)
  },
}

const exchangeProvider: Provider = {
  provide: EXCHANGE_GATEWAY,
  useFactory: (): BinanceWebSocketAdapter =>
    new BinanceWebSocketAdapter({ logger: log }),
}

const healthMonitorProvider: Provider = {
  provide: HEALTH_MONITOR,
  inject: [BUS],
  useFactory: (bus: RedisProtocolBus): BusHealthMonitor =>
    new BusHealthMonitor(bus, { intervalMs: 1000 }),
}

const ingestProvider: Provider = {
  provide: IngestTickUseCase,
  inject: [BUS, TICK_BUFFER, STREAM_NAME],
  useFactory: (
    bus: RedisProtocolBus,
    buffer: InMemoryTickBuffer,
    stream: StreamName,
  ): IngestTickUseCase => new IngestTickUseCase(bus, buffer, stream),
}

const bufferUseCaseProvider: Provider = {
  provide: BufferTickUseCase,
  inject: [TICK_BUFFER],
  useFactory: (buffer: InMemoryTickBuffer): BufferTickUseCase =>
    new BufferTickUseCase(buffer),
}

const flushProvider: Provider = {
  provide: FlushBufferUseCase,
  inject: [BUS, TICK_BUFFER, STREAM_NAME],
  useFactory: (
    bus: RedisProtocolBus,
    buffer: InMemoryTickBuffer,
    stream: StreamName,
  ): FlushBufferUseCase => new FlushBufferUseCase(bus, buffer, stream),
}

const healthMonitorUseCaseProvider: Provider = {
  provide: HealthMonitorUseCase,
  inject: [HEALTH_MONITOR, EXCHANGE_GATEWAY, FlushBufferUseCase],
  useFactory: (
    monitor: BusHealthMonitor,
    exchange: BinanceWebSocketAdapter,
    flush: FlushBufferUseCase,
  ): HealthMonitorUseCase =>
    new HealthMonitorUseCase(monitor, exchange, flush, {
      cutoffMs: 10_000,
      onLog: log,
    }),
}

@Module({
  imports: [ConfigModule.forRoot({ isGlobal: true })],
  controllers: [HealthController, HealthControllerBus],
  providers: [
    streamNameProvider,
    busProvider,
    tickBufferProvider,
    exchangeProvider,
    healthMonitorProvider,
    ingestProvider,
    bufferUseCaseProvider,
    flushProvider,
    healthMonitorUseCaseProvider,
    TickPipelineService,
    NotificationConsumer,
  ],
})
export class AppModule {}
