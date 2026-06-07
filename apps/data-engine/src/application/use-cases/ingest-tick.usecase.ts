import { Tick } from "../../domain/entities/tick"
import { StreamName } from "../../domain/value-objects/stream-name"
import { MessageBus } from "../ports/message-bus.port"
import { TickBuffer } from "../ports/tick-buffer.port"

/**
 * Happy path: try to publish to the broker; on failure, fall back to
 * the in-memory buffer. The application never blocks the data-engine's
 * WebSocket reception on broker latency (spec §5 Historia 1).
 */
export class IngestTickUseCase {
  constructor(
    private readonly bus: MessageBus,
    private readonly buffer: TickBuffer,
    private readonly stream: StreamName,
  ) {}

  async execute(tick: Tick): Promise<{ published: boolean; buffered: boolean }> {
    try {
      await this.bus.publish(this.stream, tick)
      return { published: true, buffered: false }
    } catch {
      // Spec: NestJS intercepts the failure in its infrastructure layer
      // and stores ticks in a buffer. We abstract the broker failure
      // here as a port-level error and route to the buffer.
      await this.buffer.push(tick)
      return { published: false, buffered: true }
    }
  }
}
